from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .live_analysis import LiveSessionState, TranscriptChunk, maybe_schedule_analysis, send_event
from .live_settings import LiveSettings


async def connect_deepgram(url: str, api_key: str) -> Any:
    try:
        import websockets
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("websockets package is required for live Deepgram streaming") from exc

    headers = {"Authorization": f"Token {api_key}"}
    try:
        return await websockets.connect(url, additional_headers=headers, max_size=8 * 1024 * 1024)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, max_size=8 * 1024 * 1024)


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
    send_lock: asyncio.Lock,
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
                await send_event(websocket, send_lock, "deepgram.raw", data=str(raw)[:1000])
                continue

            payload_type = payload.get("type")
            if payload_type == "Metadata":
                await send_event(websocket, send_lock, "stt.metadata", session_id=state.session_id, metadata=payload)
                continue
            if payload_type == "SpeechStarted":
                await send_event(websocket, send_lock, "speech.started", session_id=state.session_id, data=payload)
                continue
            if payload_type == "UtteranceEnd":
                await send_event(websocket, send_lock, "utterance.end", session_id=state.session_id, data=payload)
                await maybe_schedule_analysis(websocket, send_lock, state, settings, force=True)
                continue
            if payload_type in {"Error", "Warning"}:
                await send_event(websocket, send_lock, "stt.error", session_id=state.session_id, data=payload)
                continue

            transcript = deepgram_transcript_payload(payload)
            if transcript is None:
                continue

            event_type = "transcript.final" if transcript["is_final"] else "transcript.partial"
            await send_event(websocket, send_lock, event_type, session_id=state.session_id, **transcript)

            if transcript["is_final"]:
                state.final_chunks.append(
                    TranscriptChunk(
                        text=transcript["text"],
                        start=transcript.get("start"),
                        end=transcript.get("end"),
                        confidence=transcript.get("confidence"),
                    )
                )
                await maybe_schedule_analysis(websocket, send_lock, state, settings)
    finally:
        stop_event.set()
