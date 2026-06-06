from __future__ import annotations

import json
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

_DEFAULT_LLM_MAX_TOKENS = 768


def apply_live_runtime_fixes(live_module: Any) -> None:
    """Patch /live behavior without touching the local faster-whisper path."""
    session_cls = live_module.LiveSession
    if getattr(session_cls, "_tootak_noise_guard_patch", False):
        return

    async def patched_process_chunk(self: Any, chunk_index: int, chunk: bytes) -> None:
        suffix = live_module._suffix_for_mime(self.config["mime_type"])
        with tempfile.NamedTemporaryFile(prefix=f"tootak-live-{chunk_index}-", suffix=suffix, delete=False) as tmp:
            tmp.write(chunk)
            tmp_path = Path(tmp.name)

        started = time.perf_counter()
        try:
            await self._send({"type": "processing", "chunk_index": chunk_index})
            stt_result = await self._transcribe_chunk(tmp_path)
            stt_ms = round((time.perf_counter() - started) * 1000.0, 2)
            raw_text = str(stt_result.get("text") or "").strip()
            quality_flags = live_module._quality_flags(stt_result)

            ignore, reason, details = _should_ignore_transcript(raw_text, stt_result, self.config, quality_flags)
            if ignore:
                self.ignored_chunks = int(getattr(self, "ignored_chunks", 0)) + 1
                await self._send({
                    "type": "ignored_audio",
                    "chunk_index": chunk_index,
                    "reason": reason,
                    "raw_text": raw_text,
                    "details": details,
                    "ignored_chunks": self.ignored_chunks,
                    "quality_flags": quality_flags,
                    "timing_ms": {
                        "stt": stt_ms,
                        "total": round((time.perf_counter() - started) * 1000.0, 2),
                    },
                })
                return

            clean_payload = await self._clean_with_llm(raw_text, quality_flags)
            clean_text = str(clean_payload.get("cleaned_text") or raw_text).strip()

            raw_delta, self.raw_committed = live_module._merge_delta(self.raw_committed, raw_text)
            clean_delta, self.clean_committed = live_module._merge_delta(self.clean_committed, clean_text)
            context_budget = max(
                live_module._safe_positive_int(self.config.get("llm_context_tokens"), live_module._DEFAULT_LLM_CONTEXT_TOKENS),
                live_module._safe_positive_int(self.config.get("stt_context_tokens"), live_module._DEFAULT_STT_CONTEXT_TOKENS),
            )
            self.previous_context = live_module._tail_tokens(self.clean_committed, context_budget)

            await self._send({
                "type": "transcript",
                "chunk_index": chunk_index,
                "raw_text": raw_text,
                "raw_delta": raw_delta,
                "clean_text": clean_text,
                "clean_delta": clean_delta,
                "raw_full": self.raw_committed,
                "clean_full": self.clean_committed,
                "quality_flags": quality_flags,
                "possible_missing_words": clean_payload.get("possible_missing_words", []),
                "uncertain_spans": clean_payload.get("uncertain_spans", []),
                "llm": clean_payload.get("llm", {}),
                "usage": stt_result.get("usage", {}),
                "context": {
                    "audio_topic": self.config.get("audio_topic"),
                    "llm_context_tokens": self.config.get("llm_context_tokens"),
                    "stt_context_tokens": self.config.get("stt_context_tokens"),
                },
                "timing_ms": {
                    "stt": stt_ms,
                    "total": round((time.perf_counter() - started) * 1000.0, 2),
                },
            })
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def patched_clean_with_llm(self: Any, raw_text: str, quality_flags: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not raw_text:
            return {"cleaned_text": "", "possible_missing_words": [], "uncertain_spans": [], "llm": {"enabled": False, "reason": "empty_text"}}
        if not self.config.get("llm_enabled"):
            return {"cleaned_text": raw_text, "possible_missing_words": [], "uncertain_spans": [], "llm": {"enabled": False, "reason": "disabled"}}

        provider_name = str(self.config.get("llm_provider") or "groq")
        provider = getattr(self.settings.providers, provider_name, None)
        if provider is None or not provider.enabled or not provider.all_api_keys():
            return _llm_fail_open(raw_text, provider_name, "", f"{provider_name} provider is not enabled or has no key")

        model = str(self.config.get("llm_model") or "").strip()
        if not model:
            model = live_module._DEFAULT_GROQ_LLM_MODEL if provider_name == "groq" else str(provider.model or "")
        if not model:
            return _llm_fail_open(raw_text, provider_name, model, "empty_llm_model")

        llm_context_tokens = live_module._safe_positive_int(self.config.get("llm_context_tokens"), live_module._DEFAULT_LLM_CONTEXT_TOKENS)
        previous_context = live_module._tail_tokens(self.previous_context, llm_context_tokens)
        audio_topic = str(self.config.get("audio_topic") or "").strip()

        url = live_module._join_provider_path(provider.base_url, "/v1/chat/completions")
        headers = {"Authorization": f"Bearer {provider.all_api_keys()[0]}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": max(live_module._safe_positive_int(self.config.get("llm_max_tokens"), _DEFAULT_LLM_MAX_TOKENS), _DEFAULT_LLM_MAX_TOKENS),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "تو ویراستار حداقلی ترنسکریپت فارسی هستی. فقط raw_transcript_chunk را تمیز کن. "
                        "audio_topic و previous_context فقط برای فهم موضوع و اصطلاحات‌اند؛ آن‌ها را در خروجی تکرار نکن. "
                        "خلاصه‌سازی، اضافه‌کردن جمله جدید، حدس زدن متن افتاده، و تکرار متن قبلی ممنوع است. "
                        "یک JSON کوتاه بده با کلیدهای cleaned_text، possible_missing_words، uncertain_spans و notes. "
                        "اگر raw_transcript_chunk نویز یا بی‌معنی است، cleaned_text را خالی بگذار."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "audio_topic": audio_topic,
                        "previous_context": previous_context,
                        "raw_transcript_chunk": raw_text,
                        "quality_flags": quality_flags,
                    }, ensure_ascii=False),
                },
            ],
        }
        started = time.perf_counter()
        client: httpx.AsyncClient = self.transcription.client
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=min(float(provider.timeout_sec or 30), 30.0))
            if resp.status_code >= 400:
                return _llm_fail_open(raw_text, provider_name, model, f"HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            content = str(data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            parsed = _parse_json_object(content) or {"cleaned_text": content or raw_text, "possible_missing_words": [], "uncertain_spans": [], "notes": "non_json_llm_output"}
            parsed.setdefault("cleaned_text", raw_text)
            parsed.setdefault("possible_missing_words", [])
            parsed.setdefault("uncertain_spans", [])
            parsed.setdefault("notes", "")
            cleaned = str(parsed.get("cleaned_text") or "").strip()
            parsed["cleaned_text"] = cleaned or raw_text
            parsed["llm"] = {
                "enabled": True,
                "provider": provider_name,
                "model": model,
                "context_tokens": llm_context_tokens,
                "audio_topic_used": bool(audio_topic),
                "json_mode": False,
                "process_ms": round((time.perf_counter() - started) * 1000.0, 2),
            }
            return parsed
        except Exception as exc:
            return _llm_fail_open(raw_text, provider_name, model, f"{exc.__class__.__name__}: {exc}")

    session_cls._process_chunk = patched_process_chunk
    session_cls._clean_with_llm = patched_clean_with_llm
    setattr(session_cls, "_tootak_noise_guard_patch", True)


def _llm_fail_open(raw_text: str, provider: str, model: str, reason: str) -> Dict[str, Any]:
    return {
        "cleaned_text": raw_text,
        "possible_missing_words": [],
        "uncertain_spans": [],
        "llm": {"enabled": False, "provider": provider, "model": model, "reason": reason, "fail_open": True},
    }


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start:end + 1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _extract_segments(stt_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments = stt_result.get("segments")
    if not isinstance(segments, list):
        metadata = stt_result.get("metadata")
        upstream = metadata.get("upstream_raw", {}) if isinstance(metadata, dict) else {}
        segments = upstream.get("segments") if isinstance(upstream, dict) else None
    if not isinstance(segments, list):
        return []
    return [seg for seg in segments if isinstance(seg, dict)]


def _should_ignore_transcript(raw_text: str, stt_result: Dict[str, Any], config: Dict[str, Any], quality_flags: List[Dict[str, Any]]) -> Tuple[bool, str, Dict[str, Any]]:
    text = " ".join(str(raw_text or "").split())
    if not text:
        return True, "empty_transcript", {"message": "No speech text returned."}

    segments = _extract_segments(stt_result)
    no_speech_values = [seg.get("no_speech_prob") for seg in segments if isinstance(seg.get("no_speech_prob"), (int, float))]
    avg_logprob_values = [seg.get("avg_logprob") for seg in segments if isinstance(seg.get("avg_logprob"), (int, float))]
    max_no_speech = max(no_speech_values) if no_speech_values else None
    avg_logprob = sum(avg_logprob_values) / len(avg_logprob_values) if avg_logprob_values else None
    repeated = _repeated_ngram_score(text)
    prompt_similarity = _prompt_echo_score(text, config)
    details = {
        "max_no_speech_prob": max_no_speech,
        "avg_logprob": avg_logprob,
        "repeated_ngram_score": repeated,
        "prompt_echo_score": prompt_similarity,
        "quality_flag_count": len(quality_flags),
    }

    if isinstance(max_no_speech, (int, float)) and max_no_speech >= 0.72 and len(text.split()) <= 24:
        return True, "probable_silence", details
    if prompt_similarity >= 0.72:
        return True, "prompt_echo", details
    if repeated >= 0.58 and len(text.split()) >= 8:
        return True, "repeated_hallucination", details
    if isinstance(avg_logprob, (int, float)) and avg_logprob < -0.85 and repeated >= 0.35:
        return True, "low_confidence_repetition", details
    return False, "speech", details


def _normalize_for_compare(value: str) -> List[str]:
    chars = []
    for ch in str(value or "").lower():
        if ch.isalnum() or ch in "آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی":
            chars.append(ch)
        else:
            chars.append(" ")
    return [tok for tok in "".join(chars).split() if tok]


def _prompt_echo_score(raw_text: str, config: Dict[str, Any]) -> float:
    raw_tokens = set(_normalize_for_compare(raw_text))
    if not raw_tokens:
        return 0.0
    prompt_text = " ".join([
        str(config.get("prompt") or ""),
        str(config.get("audio_topic") or ""),
        "اصطلاحات تخصصی را با املای درست حفظ کن",
    ])
    prompt_tokens = set(_normalize_for_compare(prompt_text))
    if not prompt_tokens:
        return 0.0
    overlap = len(raw_tokens & prompt_tokens) / max(1, min(len(raw_tokens), len(prompt_tokens)))
    raw_joined = " ".join(_normalize_for_compare(raw_text))
    if "اصطلاحات تخصصی" in raw_joined and raw_joined.count("اصطلاحات تخصصی") >= 2:
        return max(overlap, 0.9)
    return overlap


def _repeated_ngram_score(text: str) -> float:
    words = _normalize_for_compare(text)
    if len(words) < 6:
        return 0.0
    best = 0.0
    for n in (2, 3, 4):
        if len(words) < n * 2:
            continue
        ngrams = [tuple(words[i:i + n]) for i in range(0, len(words) - n + 1)]
        counts = Counter(ngrams)
        if counts:
            best = max(best, (max(counts.values()) * n) / max(1, len(words)))
    return best
