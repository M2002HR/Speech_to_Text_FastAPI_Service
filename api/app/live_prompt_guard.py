from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_MAX_STT_PROMPT_CHARS = 840


def apply_live_prompt_guard(live_module: Any) -> None:
    """Small runtime fixes for /live: STT prompt length, local auto language, and list cleanup."""
    if not getattr(live_module, "_tootak_stt_prompt_char_guard", False):
        live_module._build_stt_prompt = _build_limited_stt_prompt
        setattr(live_module, "_tootak_stt_prompt_char_guard", True)

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


def _build_limited_stt_prompt(base_prompt: str, audio_topic: str, previous_context: str, context_tokens: int) -> str:
    base = _collapse(base_prompt)
    topic = _collapse(audio_topic)
    context = _collapse(previous_context)
    parts: List[str] = []
    if base:
        parts.append(_clip(base, 220))
    if topic:
        parts.append("موضوع صدا: " + _clip(topic, 220))
    used = len("\n".join(parts))
    remaining = _MAX_STT_PROMPT_CHARS - used - 80
    if context and remaining > 60:
        word_budget = max(0, min(int(context_tokens or 0), 80))
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
