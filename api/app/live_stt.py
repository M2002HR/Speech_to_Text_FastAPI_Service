from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .live_analysis import BrowserSender, LiveSessionState, TranscriptChunk, maybe_schedule_analysis, send_event
from .live_settings import LiveSettings


def _connect_error_message(exc: BaseException, settings: LiveSettings, attempt: int) -> str:
    base = str(exc).strip() or f"{exc.__class__.__module__}.{exc.__class__.__name__}: no message"
    if isinstance(exc, asyncio.TimeoutError) or "timed out during handshake" in base.lower():
        return (
            f"Deepgram websocket handshake timed out on attempt {attempt}. "
            f"open_timeout={settings.open_timeout_sec}s, url={settings.deepgram_base_url}. "
            "Check internet access from the backend machine, VPN/proxy/firewall rules, and whether wss://api.deepgram.com is reachable. "
            f"Original error: {base}"
        )
    return f"Deepgram websocket connection failed on attempt {attempt}: {base}"


async def connect_deepgram(url: str, api_key: str, settings: Optional[LiveSettings] = None) -> Any:
    try:
        import websockets
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("websockets package is required for live Deepgram streaming") from exc

    settings = settings or LiveSettings.from_env()
    headers = {"Authorization": f"Token {api_key}"}
    attempts = max(1, int(settings.connect_retries or 1))
    last_exc: Optional[BaseException] = None

    # Deepgram's streaming endpoint does not reliably answer WebSocket
    # protocol-level ping frames; it expects application-level "KeepAlive"
    # JSON messages instead (sent here by keepalive_loop). Leaving the
    # websockets client's built-in keepalive ping enabled therefore makes the
    # client close the connection with 1011 "keepalive ping timeout" after a
    # few unanswered pings, even while transcripts are flowing. So when the
    # configured ping interval is non-positive we disable client-side pings
    # entirely and rely solely on the KeepAlive loop.
    ping_interval_raw = settings.ping_interval_sec
    if ping_interval_raw is None or float(ping_interval_raw) <= 0:
        ping_interval: Optional[float] = None
        ping_timeout: Optional[float] = None
    else:
        ping_interval = max(5.0, float(ping_interval_raw))
        ping_timeout = max(5.0, float(settings.ping_timeout_sec or 20.0))

    for attempt in range(1, attempts + 1):
        try:
            kwargs = {
                "max_size": 8 * 1024 * 1024,
                "open_timeout": max(5.0, float(settings.open_timeout_sec or 45.0)),
                "close_timeout": max(1.0, float(settings.close_timeout_sec or 10.0)),
                "ping_interval": ping_interval,
                "ping_timeout": ping_timeout,
                # Audio frames are raw PCM (incompressible); permessage-deflate
                # only burns CPU and adds per-message latency on the hot path.
                "compression": None,
            }
            try:
                return await websockets.connect(url, additional_headers=headers, **kwargs)
            except TypeError:
                return await websockets.connect(url, extra_headers=headers, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            await asyncio.sleep(max(0.0, float(settings.connect_retry_backoff_sec or 2.0)) * attempt)

    assert last_exc is not None
    raise TimeoutError(_connect_error_message(last_exc, settings, attempts)) from last_exc


def deepgram_transcript_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if payload.get("type") != "Results":
        return None

    alternatives = (((payload.get("channel") or {}).get("alternatives")) or [])
    if not alternatives:
        return None

    alt = alternatives[0] or {}
    transcript = str(alt.get("transcript") or "").strip()
    if not transcript:
        return None

    start = payload.get("start")
    duration = payload.get("duration")
    end: Optional[float] = None
    try:
        end = float(start) + float(duration) if start is not None and duration is not None else None
    except Exception:
        end = None

    return {
        "text": transcript,
        "start": start,
        "duration": duration,
        "end": end,
        "confidence": alt.get("confidence"),
        "words": alt.get("words") if isinstance(alt.get("words"), list) else [],
        "is_final": bool(payload.get("is_final") or payload.get("speech_final")),
        "speech_final": bool(payload.get("speech_final")),
        "channel_index": payload.get("channel_index"),
    }


async def keepalive_loop(deepgram_ws: Any, settings: LiveSettings, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await asyncio.sleep(max(1.0, float(settings.keepalive_sec)))
        if stop_event.is_set():
            return
        try:
            await deepgram_ws.send(json.dumps({"type": "KeepAlive"}))
        except Exception:
            return


async def browser_to_deepgram(
    websocket: WebSocket,
    deepgram_ws: Any,
    stop_event: asyncio.Event,
) -> None:
    try:
        while not stop_event.is_set():
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                stop_event.set()
                return

            if message.get("bytes") is not None:
                await deepgram_ws.send(message["bytes"])
                continue

            if message.get("text") is not None:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                msg_type = payload.get("type")
                if msg_type in {"stop", "close"}:
                    await deepgram_ws.send(json.dumps({"type": "CloseStream"}))
                    stop_event.set()
                    return
    except WebSocketDisconnect:
        stop_event.set()
    except Exception:
        stop_event.set()
        raise


async def deepgram_to_browser(
    websocket: WebSocket,
    sender: "BrowserSender",
    deepgram_ws: Any,
    state: LiveSessionState,
    settings: LiveSettings,
    stop_event: asyncio.Event,
) -> None:
    try:
        async for raw in deepgram_ws:
            if stop_event.is_set():
                return

            if isinstance(raw, bytes):
                continue

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await send_event(websocket, sender, "deepgram.raw", data=str(raw)[:1000])
                continue

            payload_type = payload.get("type")
            if payload_type == "Metadata":
                await send_event(websocket, sender, "stt.metadata", session_id=state.session_id, metadata=payload)
                continue
            if payload_type == "SpeechStarted":
                await send_event(websocket, sender, "speech.started", session_id=state.session_id, data=payload)
                continue
            if payload_type == "UtteranceEnd":
                await send_event(websocket, sender, "utterance.end", session_id=state.session_id, data=payload)
                await maybe_schedule_analysis(websocket, sender, state, settings)
                await maybe_schedule_analysis(websocket, sender, state, settings, resolve_only=True)
                continue
            if payload_type in {"Error", "Warning"}:
                await send_event(websocket, sender, "stt.error", session_id=state.session_id, data=payload)
                continue

            transcript = deepgram_transcript_payload(payload)
            if transcript is None:
                continue

            event_type = "transcript.final" if transcript["is_final"] else "transcript.partial"
            await send_event(websocket, sender, event_type, session_id=state.session_id, **transcript)

            if transcript["is_final"]:
                state.final_chunks.append(
                    TranscriptChunk(
                        text=transcript["text"],
                        start=transcript.get("start"),
                        end=transcript.get("end"),
                        confidence=transcript.get("confidence"),
                    )
                )
                await maybe_schedule_analysis(websocket, sender, state, settings)
                await maybe_schedule_analysis(websocket, sender, state, settings, resolve_only=True)
    finally:
        stop_event.set()
