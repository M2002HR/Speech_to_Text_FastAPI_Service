from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_MAX_STT_PROMPT_CHARS = 620


def apply_live_prompt_guard(live_module: Any) -> None:
    """Small runtime fixes for /live: STT prompt length, local auto language, UI controls, and list cleanup."""
    if not getattr(live_module, "_tootak_stt_prompt_char_guard", False):
        live_module._build_stt_prompt = _build_limited_stt_prompt
        setattr(live_module, "_tootak_stt_prompt_char_guard", True)

    _patch_api_prompt_limit()
    _patch_live_ui(live_module)

    session_cls = live_module.LiveSession
    if not getattr(session_cls, "_tootak_llm_list_cleanup_patch", False):
        original_send = session_cls._send

        async def patched_send(self: Any, payload: Dict[str, Any]) -> None:
            if isinstance(payload, dict) and payload.get("type") == "transcript":
                payload = dict(payload)
                payload["possible_missing_words"] = _normalize_text_list(payload.get("possible_missing_words"))
                payload["uncertain_spans"] = _normalize_text_list(payload.get("uncertain_spans"))
            await original_send(self, payload)

        session_cls._send = patched_send
        setattr(session_cls, "_tootak_llm_list_cleanup_patch", True)

    _patch_local_auto_language()


def _patch_api_prompt_limit() -> None:
    try:
        from .services import APITranscriber
    except Exception:
        return
    if getattr(APITranscriber, "_tootak_api_prompt_limit_patch", False):
        return

    original = APITranscriber._call_openai_compatible

    async def patched(self: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        options = kwargs.get("options")
        if isinstance(options, dict) and options.get("prompt"):
            safe_options = dict(options)
            safe_options["prompt"] = _clip(str(options.get("prompt") or ""), _MAX_STT_PROMPT_CHARS)
            kwargs["options"] = safe_options
        return await original(self, *args, **kwargs)

    APITranscriber._call_openai_compatible = patched
    setattr(APITranscriber, "_tootak_api_prompt_limit_patch", True)


def _patch_live_ui(live_module: Any) -> None:
    if getattr(live_module, "_tootak_live_ui_guard", False):
        return

    def install_live_routes(app: Any) -> None:
        if getattr(app.state, "live_routes_installed", False):
            return
        app.state.live_routes_installed = True

        from fastapi.responses import HTMLResponse

        @app.get("/live", include_in_schema=False, summary="Live transcription Web UI")
        async def ui_live_index() -> HTMLResponse:
            html = (live_module._UI_DIR / "live.html").read_text(encoding="utf-8")
            return HTMLResponse(_enhance_live_html(html))

        @app.websocket("/live/ws")
        async def live_transcription_ws(websocket: Any) -> None:
            await websocket.accept()
            session = live_module.LiveSession(websocket)
            await session.run()

    live_module.install_live_routes = install_live_routes
    setattr(live_module, "_tootak_live_ui_guard", True)


def _enhance_live_html(html: str) -> str:
    language_input = '<label>زبان<input id="language" value="fa" dir="ltr"></label>'
    language_select = (
        '<label>زبان<select id="language">'
        '<option value="auto">Auto / تشخیص خودکار</option>'
        '<option value="fa" selected>فارسی fa</option>'
        '<option value="en">English en</option>'
        '<option value="ar">Arabic ar</option>'
        '<option value="tr">Turkish tr</option>'
        '<option value="de">German de</option>'
        '<option value="fr">French fr</option>'
        '</select></label>'
    )
    html = html.replace(language_input, language_select)
    html = html.replace("language:$('language').value.trim()||'fa'", "language:$('language').value")
    html = html.replace(
        "<option value=\"local\">Local faster-whisper</option>",
        "<option value=\"local\">Local faster-whisper اگر مدل موجود باشد</option>",
    )
    html = html.replace(
        "Provider STT<select id=\"provider\"><option value=\"groq\" selected>Groq - دقیق‌تر</option><option value=\"openai\">OpenAI-compatible</option><option value=\"local\">Local faster-whisper اگر مدل موجود باشد</option><option value=\"custom\">Custom</option></select>",
        "Provider STT<select id=\"provider\"><option value=\"groq\" selected>Groq - دقیق‌تر</option><option value=\"local\">Local faster-whisper اگر مدل موجود باشد</option><option value=\"openai\">OpenAI-compatible</option><option value=\"custom\">Custom</option></select>",
    )
    html = html.replace(
        "$('provider').addEventListener('change',()=>{if($('provider').value==='groq')$('sttModel').value='whisper-large-v3'});",
        "$('provider').addEventListener('change',()=>{if($('provider').value==='groq'){$('sttModel').value='whisper-large-v3'}else if($('provider').value==='local'){$('sttModel').value='large-v3';addEvent('Provider لوکال انتخاب شد؛ اگر large-v3 دانلود نشده، از مدل موجود مثل medium یا small استفاده کن.','warning')}});",
    )
    marker = "function handleServerMessage(m){"
    helper = (
        "function formatItem(x){if(x===null||x===undefined)return '';"
        "if(typeof x==='string'||typeof x==='number'||typeof x==='boolean')return String(x).trim();"
        "if(Array.isArray(x))return x.map(formatItem).filter(Boolean).join('، ');"
        "if(typeof x==='object'){for(const k of ['text','word','phrase','span','value','reason','note']){if(x[k])return formatItem(x[k])}try{return JSON.stringify(x)}catch(_){return String(x)}}return String(x).trim()}"
        "function formatList(v){if(!Array.isArray(v))v=v?[v]:[];const out=[];for(const item of v){const text=formatItem(item);if(text&&!out.includes(text))out.push(text)}return out}"
    )
    if "function formatItem" not in html and marker in html:
        html = html.replace(marker, helper + marker)
    html = html.replace(
        "const miss=Array.isArray(m.possible_missing_words)?m.possible_missing_words.filter(Boolean):[];const unc=Array.isArray(m.uncertain_spans)?m.uncertain_spans.filter(Boolean):[];",
        "const miss=formatList(m.possible_missing_words);const unc=formatList(m.uncertain_spans);",
    )
    return html


def _build_limited_stt_prompt(base_prompt: str, audio_topic: str, previous_context: str, context_tokens: int) -> str:
    base = _collapse(base_prompt)
    topic = _collapse(audio_topic)
    context = _collapse(previous_context)
    parts: List[str] = []
    if base:
        parts.append(_clip(base, 180))
    if topic:
        parts.append("موضوع صدا: " + _clip(topic, 160))
    used = len("\n".join(parts))
    remaining = _MAX_STT_PROMPT_CHARS - used - 80
    if context and remaining > 60:
        word_budget = max(0, min(int(context_tokens or 0), 45))
        context_text = " ".join(context.split()[-word_budget:]) if word_budget else ""
        context_text = _clip(context_text, remaining)
        if context_text:
            parts.append("متن قبلی فقط برای پیوستگی است؛ از روی آن حدس نزن: " + context_text)
    return _clip("\n".join(parts), _MAX_STT_PROMPT_CHARS)


def _patch_local_auto_language() -> None:
    try:
        from .services import LocalTranscriber
    except Exception:
        return
    if getattr(LocalTranscriber, "_tootak_auto_language_patch", False):
        return
    original = LocalTranscriber.transcribe

    async def patched(self: Any, audio_path: Path, options: Dict[str, Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if str((options or {}).get("language") or "").strip().lower() != "auto":
            return await original(self, audio_path, options, *args, **kwargs)
        patched_options = dict(options or {})
        patched_options.pop("language", None)
        trans_settings = getattr(self.settings, "transcription", None)
        old_lang = getattr(trans_settings, "default_language", None)
        changed = False
        try:
            if trans_settings is not None:
                setattr(trans_settings, "default_language", "auto")
                changed = True
            return await original(self, audio_path, patched_options, *args, **kwargs)
        finally:
            if changed:
                try:
                    setattr(trans_settings, "default_language", old_lang)
                except Exception:
                    pass

    LocalTranscriber.transcribe = patched
    setattr(LocalTranscriber, "_tootak_auto_language_patch", True)


def _normalize_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, dict):
        for key in ("text", "word", "phrase", "span", "value", "reason", "note"):
            if value.get(key):
                return _normalize_text_list(value.get(key))
        compact = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return [compact] if compact else []
    if isinstance(value, list):
        out: List[str] = []
        seen: set[str] = set()
        for item in value:
            for text in _normalize_text_list(item):
                if text and text not in seen:
                    seen.add(text)
                    out.append(text)
        return out[:12]
    text = str(value).strip()
    return [text] if text else []


def _collapse(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clip(value: Any, max_chars: int) -> str:
    text = _collapse(value)
    limit = max(1, int(max_chars))
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].strip()
    return clipped if clipped else text[:limit].strip()
