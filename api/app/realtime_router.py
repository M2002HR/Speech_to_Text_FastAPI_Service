from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .live_analysis import LiveSessionState, maybe_schedule_analysis, send_event
from .live_settings import LiveSettings, build_deepgram_url, extract_client_options
from .live_stt import browser_to_deepgram, connect_deepgram, deepgram_to_browser, keepalive_loop

_UI_DIR = Path(__file__).resolve().parent / "ui"

router = APIRouter(tags=["realtime"])


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

    client_options = extract_client_options(initial_payload, settings)
    state.topic = str(client_options.get("topic") or "")
    deepgram_url = build_deepgram_url(settings, client_options)

    await send_event(
        websocket,
        send_lock,
        "session.started",
        session_id=state.session_id,
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
                await send_event(websocket, send_lock, "error", session_id=state.session_id, error=str(exc))

        stop_event.set()
        for task in pending:
            task.cancel()

        await maybe_schedule_analysis(websocket, send_lock, state, settings, force=True)
        if state.analysis_task:
            try:
                await asyncio.wait_for(state.analysis_task, timeout=settings.llm_timeout_sec + 5.0)
            except Exception:
                pass

    except Exception as exc:
        await send_event(websocket, send_lock, "error", session_id=state.session_id, error=str(exc))

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
