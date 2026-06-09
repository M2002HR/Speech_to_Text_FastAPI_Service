from __future__ import annotations

import asyncio
import json
import subprocess
import time
import traceback
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .live_analysis import LiveSessionState, maybe_schedule_analysis, send_event
from .live_settings import LiveSettings, build_deepgram_url, extract_client_options
from .live_stt import browser_to_deepgram, connect_deepgram, deepgram_to_browser, keepalive_loop
from .services import is_audio_file, is_video_file, sanitize_name

_UI_DIR = Path(__file__).resolve().parent / "ui"
_REALTIME_UPLOAD_TTL_SEC = 6 * 60 * 60

router = APIRouter(tags=["realtime"])


def _exception_message(exc: BaseException) -> str:
    text = str(exc).strip()
    if text:
        return text
    return f"{exc.__class__.__module__}.{exc.__class__.__name__}: no message"


def _exception_payload(exc: BaseException) -> Dict[str, Any]:
    return {
        "error": _exception_message(exc),
        "error_type": exc.__class__.__name__,
        "traceback": "".join(traceback.format_exception_only(type(exc), exc)).strip(),
    }


def _upload_store(request: Request) -> Dict[str, Dict[str, Any]]:
    store = getattr(request.app.state, "realtime_uploads", None)
    if not isinstance(store, dict):
        store = {}
        request.app.state.realtime_uploads = store
    return store


def _cleanup_upload_store(store: Dict[str, Dict[str, Any]]) -> None:
    now = time.time()
    expired: List[str] = []
    for upload_id, item in store.items():
        if now - float(item.get("created_at", now)) <= _REALTIME_UPLOAD_TTL_SEC:
            continue
        expired.append(upload_id)
    for upload_id in expired:
        item = store.pop(upload_id, {})
        for key in ("raw_path", "prepared_path"):
            try:
                path = Path(str(item.get(key) or ""))
                if path.exists():
                    path.unlink(missing_ok=True)
            except Exception:
                pass


def _get_upload_session(websocket: WebSocket, upload_id: str) -> Dict[str, Any]:
    store = getattr(websocket.app.state, "realtime_uploads", {})
    if not isinstance(store, dict) or upload_id not in store:
        raise HTTPException(status_code=404, detail="realtime upload not found or expired")
    return store[upload_id]


def _file_stream_settings(settings: LiveSettings) -> LiveSettings:
    return replace(settings, encoding="linear16", sample_rate=16000, channels=1)


def _start_ffmpeg_raw_pcm(ffmpeg_binary: str, audio_path: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            ffmpeg_binary,
            "-v",
            "error",
            "-i",
            str(audio_path),
            "-vn",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


async def _file_to_deepgram(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    deepgram_ws: Any,
    state: LiveSessionState,
    settings: LiveSettings,
    audio_path: Path,
    stop_event: asyncio.Event,
    *,
    chunk_ms: int = 250,
) -> None:
    app_settings = websocket.app.state.settings
    ffmpeg_binary = app_settings.processing.ffmpeg_binary
    sample_rate = 16000
    channels = 1
    bytes_per_second = sample_rate * channels * 2
    chunk_size = max(640, int(bytes_per_second * max(40, chunk_ms) / 1000))
    if chunk_size % 2:
        chunk_size += 1

    if not audio_path.exists():
        raise FileNotFoundError(f"prepared audio file not found: {audio_path}")

    proc = await asyncio.to_thread(_start_ffmpeg_raw_pcm, ffmpeg_binary, audio_path)
    sent_bytes = 0
    started = time.monotonic()
    await send_event(
        websocket,
        send_lock,
        "file.playback.started",
        session_id=state.session_id,
        path=str(audio_path),
        chunk_size=chunk_size,
    )

    try:
        if proc.stdout is None:
            raise RuntimeError("ffmpeg stdout pipe was not created")

        while not stop_event.is_set():
            chunk = await asyncio.to_thread(proc.stdout.read, chunk_size)
            if not chunk:
                break

            await deepgram_ws.send(chunk)
            sent_bytes += len(chunk)
            audio_elapsed = sent_bytes / float(bytes_per_second)
            wall_elapsed = time.monotonic() - started
            if audio_elapsed > wall_elapsed:
                await asyncio.sleep(min(1.0, audio_elapsed - wall_elapsed))
            if sent_bytes % (bytes_per_second * 5) < chunk_size:
                await send_event(
                    websocket,
                    send_lock,
                    "file.playback.progress",
                    session_id=state.session_id,
                    audio_seconds=round(audio_elapsed, 2),
                    sent_bytes=sent_bytes,
                )

        return_code = await asyncio.to_thread(proc.wait)
        if return_code != 0 or sent_bytes == 0:
            stderr = b""
            if proc.stderr is not None:
                stderr = await asyncio.to_thread(proc.stderr.read)
            detail = stderr.decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"ffmpeg realtime decode failed rc={return_code}; sent_bytes={sent_bytes}; stderr={detail}")

        await deepgram_ws.send(json.dumps({"type": "CloseStream"}))
        await send_event(
            websocket,
            send_lock,
            "file.playback.finished",
            session_id=state.session_id,
            audio_seconds=round(sent_bytes / float(bytes_per_second), 2),
            sent_bytes=sent_bytes,
        )
    except Exception as exc:
        await send_event(websocket, send_lock, "file.playback.error", session_id=state.session_id, **_exception_payload(exc))
        raise
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()


@router.get("/realtime", include_in_schema=False, summary="Realtime classroom STT panel")
async def realtime_index() -> FileResponse:
    return FileResponse(_UI_DIR / "realtime.html")


@router.get("/realtime/status", summary="Realtime STT runtime status")
async def realtime_status(request: Request) -> Dict[str, Any]:
    settings = LiveSettings.from_env()
    app_settings = getattr(getattr(request.app, "state", None), "settings", None)
    return {
        "status": "ok",
        "app": app_settings.app.name if app_settings else "Tootak",
        "realtime": settings.public_dict(),
    }


@router.post("/realtime/uploads", summary="Upload audio/video for simulated realtime playback")
async def realtime_upload(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    source_name = file.filename or "uploaded-media"
    content_type = file.content_type
    if not (is_audio_file(source_name, content_type) or is_video_file(source_name, content_type)):
        raise HTTPException(status_code=415, detail="upload an audio or video file")

    media = request.app.state.services.transcription.media
    raw_path = await media.save_upload(file)
    prepared_path: Optional[Path] = None
    try:
        prepared_path = await media.extract_audio(raw_path, source_name, content_type)
        duration = await media.probe_duration(prepared_path)
    except Exception:
        if raw_path.exists():
            raw_path.unlink(missing_ok=True)
        raise

    store = _upload_store(request)
    _cleanup_upload_store(store)
    upload_id = uuid.uuid4().hex
    store[upload_id] = {
        "upload_id": upload_id,
        "source_filename": sanitize_name(source_name),
        "source_content_type": content_type,
        "raw_path": str(raw_path),
        "prepared_path": str(prepared_path),
        "duration_seconds": duration,
        "created_at": time.time(),
    }
    return {
        "upload_id": upload_id,
        "source_filename": source_name,
        "duration_seconds": duration,
        "prepared_audio_path": str(prepared_path),
    }


@router.websocket("/ws/realtime")
async def realtime_ws(websocket: WebSocket) -> None:
    settings = LiveSettings.from_env()
    await websocket.accept()
    send_lock = asyncio.Lock()
    state = LiveSessionState(session_id=uuid.uuid4().hex)
    stop_event = asyncio.Event()

    if not settings.enabled:
        await send_event(websocket, send_lock, "error", session_id=state.session_id, error="realtime mode is disabled")
        await websocket.close(code=1013)
        return

    if not settings.deepgram_api_key:
        await send_event(
            websocket,
            send_lock,
            "error",
            session_id=state.session_id,
            error="DEEPGRAM_API_KEY or PROVIDER_DEEPGRAM_API_KEY is not configured",
        )
        await websocket.close(code=1011)
        return

    try:
        initial = await asyncio.wait_for(websocket.receive_text(), timeout=8.0)
        initial_payload = json.loads(initial) if initial else {}
    except asyncio.TimeoutError:
        initial_payload = {}
    except json.JSONDecodeError:
        initial_payload = {}

    source = str(initial_payload.get("source") or "mic").strip().lower()
    upload_session: Optional[Dict[str, Any]] = None
    if source == "upload":
        upload_id = str(initial_payload.get("upload_id") or "").strip()
        upload_session = _get_upload_session(websocket, upload_id)
        settings = _file_stream_settings(settings)

    client_options = extract_client_options(initial_payload, settings)
    state.topic = str(client_options.get("topic") or "")
    deepgram_url = build_deepgram_url(settings, client_options)

    await send_event(
        websocket,
        send_lock,
        "session.started",
        session_id=state.session_id,
        source=source,
        upload={
            "upload_id": upload_session.get("upload_id"),
            "filename": upload_session.get("source_filename"),
            "duration_seconds": upload_session.get("duration_seconds"),
            "prepared_path": upload_session.get("prepared_path"),
        } if upload_session else None,
        stt={
            "model": settings.deepgram_model,
            "language": client_options.get("language") or settings.language,
            "encoding": settings.encoding,
            "sample_rate": settings.sample_rate,
        },
        llm={
            "enabled": settings.llm_enabled,
            "configured": bool(settings.llm_api_key),
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        },
    )

    stt_ws = None
    tasks: List[asyncio.Task[Any]] = []
    try:
        stt_ws = await connect_deepgram(deepgram_url, settings.deepgram_api_key)
        await send_event(websocket, send_lock, "stt.open", session_id=state.session_id)

        if source == "upload" and upload_session:
            sender_task = asyncio.create_task(
                _file_to_deepgram(
                    websocket,
                    send_lock,
                    stt_ws,
                    state,
                    settings,
                    Path(str(upload_session["prepared_path"])),
                    stop_event,
                )
            )
            receiver_task = asyncio.create_task(deepgram_to_browser(websocket, send_lock, stt_ws, state, settings, stop_event))
            keepalive_task = asyncio.create_task(keepalive_loop(stt_ws, settings, stop_event))
            tasks = [sender_task, receiver_task, keepalive_task]

            await sender_task
            try:
                await asyncio.wait_for(receiver_task, timeout=max(10.0, settings.llm_timeout_sec))
            except asyncio.TimeoutError:
                await send_event(websocket, send_lock, "warning", session_id=state.session_id, error="timed out waiting for final STT results")
            stop_event.set()
            keepalive_task.cancel()
        else:
            tasks = [
                asyncio.create_task(browser_to_deepgram(websocket, stt_ws, stop_event)),
                asyncio.create_task(deepgram_to_browser(websocket, send_lock, stt_ws, state, settings, stop_event)),
                asyncio.create_task(keepalive_loop(stt_ws, settings, stop_event)),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None and not isinstance(exc, WebSocketDisconnect):
                    await send_event(websocket, send_lock, "error", session_id=state.session_id, **_exception_payload(exc))
            stop_event.set()
            for task in pending:
                task.cancel()

        await maybe_schedule_analysis(websocket, send_lock, state, settings, force=True)
        if state.analysis_task:
            try:
                await asyncio.wait_for(state.analysis_task, timeout=settings.llm_timeout_sec + 5.0)
            except Exception as exc:
                await send_event(websocket, send_lock, "analysis.error", session_id=state.session_id, **_exception_payload(exc))

    except Exception as exc:
        await send_event(websocket, send_lock, "error", session_id=state.session_id, **_exception_payload(exc))

    finally:
        stop_event.set()
        for task in tasks:
            if not task.done():
                task.cancel()

        if stt_ws is not None:
            try:
                await stt_ws.close()
            except Exception:
                pass

        try:
            await send_event(
                websocket,
                send_lock,
                "session.closed",
                session_id=state.session_id,
                final_text=state.final_text(),
            )
            await websocket.close()
        except Exception:
            pass
