from __future__ import annotations

from typing import Any

from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket

from . import live
from .live_prompt_guard import _enhance_live_html, apply_live_prompt_guard
from .live_runtime_fixes import apply_live_runtime_fixes
from .main import app as base_app


class LiveEnabledASGI:
    def __init__(self, base: Any) -> None:
        self.base = base
        self.state = base.state
        self.router = base.router
        self.routes = base.routes

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        path = str(scope.get("path") or "")
        if scope.get("type") == "websocket" and path.rstrip("/") == "/live/ws":
            await self._handle_live_ws(scope, receive, send)
            return
        if scope.get("type") == "http" and path.rstrip("/") == "/live":
            await self._handle_live_http(scope, receive, send)
            return
        await self.base(scope, receive, send)

    async def _handle_live_http(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        html = (live._UI_DIR / "live.html").read_text(encoding="utf-8")
        response = HTMLResponse(_enhance_live_html(html))
        await response(scope, receive, send)

    async def _handle_live_ws(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        patched_scope = dict(scope)
        patched_scope["app"] = self.base
        websocket = WebSocket(patched_scope, receive=receive, send=send)
        await websocket.accept()
        session = live.LiveSession(websocket)
        await session.run()


def _disable_groq_stt_prompt() -> None:
    """Groq STT has a very small prompt character limit; live Groq STT sends no prompt."""
    session_cls = live.LiveSession
    if getattr(session_cls, "_tootak_groq_stt_no_prompt", False):
        return

    original = session_cls._transcribe_chunk

    async def patched_transcribe_chunk(self: Any, audio_path: Any) -> dict[str, Any]:
        if str(self.config.get("provider") or "").lower() != "groq":
            return await original(self, audio_path)

        old_prompt = self.config.get("prompt")
        old_topic = self.config.get("audio_topic")
        old_stt_context = self.config.get("stt_context_tokens")
        old_previous_context = self.previous_context
        try:
            self.config["prompt"] = ""
            self.config["audio_topic"] = ""
            self.config["stt_context_tokens"] = 0
            self.previous_context = ""
            return await original(self, audio_path)
        finally:
            self.config["prompt"] = old_prompt
            self.config["audio_topic"] = old_topic
            self.config["stt_context_tokens"] = old_stt_context
            self.previous_context = old_previous_context

    session_cls._transcribe_chunk = patched_transcribe_chunk
    setattr(session_cls, "_tootak_groq_stt_no_prompt", True)


def _prepare_live() -> None:
    apply_live_prompt_guard(live)
    apply_live_runtime_fixes(live)
    _disable_groq_stt_prompt()


_prepare_live()
app = LiveEnabledASGI(base_app)
