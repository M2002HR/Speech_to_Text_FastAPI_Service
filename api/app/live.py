from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

_UI_DIR = Path(__file__).resolve().parent / "ui"
_DEFAULT_GROQ_STT_MODEL = "whisper-large-v3"
_FALLBACK_GROQ_STT_MODEL = "whisper-large-v3-turbo"
_DEFAULT_GROQ_LLM_MODEL = "openai/gpt-oss-120b"
_MAX_LIVE_QUEUE_SIZE = 6
_DEFAULT_LLM_CONTEXT_TOKENS = 300
_DEFAULT_STT_CONTEXT_TOKENS = 160
_MAX_STT_PROMPT_TOKENS = 224


def install_live_routes(app: FastAPI) -> None:
    """Install the near-real-time live transcription panel and websocket once."""
    if getattr(app.state, "live_routes_installed", False):
        return
    app.state.live_routes_installed = True

    @app.get("/live", include_in_schema=False, summary="Live transcription Web UI")
    async def ui_live_index() -> FileResponse:
        return FileResponse(_UI_DIR / "live.html")

    @app.websocket("/live/ws")
    async def live_transcription_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        session = LiveSession(websocket)
        await session.run()


class LiveSession:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.settings: Any = None
        self.transcription: Any = None
        self.config: Dict[str, Any] = {}
        self.queue: asyncio.Queue[Optional[Tuple[int, bytes]]] = asyncio.Queue(maxsize=_MAX_LIVE_QUEUE_SIZE)
        self.stop_event = asyncio.Event()
        self.started_at = time.perf_counter()
        self.raw_committed = ""
        self.clean_committed = ""
        self.previous_context = ""
        self.chunk_counter = 0
        self.dropped_chunks = 0
        self.worker_task: Optional[asyncio.Task[None]] = None

    async def run(self) -> None:
        self.settings = self.websocket.app.state.settings
        self.transcription = self.websocket.app.state.services.transcription

        try:
            start_payload = await self.websocket.receive_json()
        except Exception:
            await self._send({"type": "error", "message": "اولین پیام websocket باید JSON تنظیمات live باشد."})
            await self.websocket.close(code=1003)
            return

        self.config = self._normalize_config(start_payload)
        await self._send({
            "type": "ready",
            "config": self._public_config(),
            "message": "live session ready",
        })

        self.worker_task = asyncio.create_task(self._worker())
        try:
            while not self.stop_event.is_set():
                message = await self.websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await self._handle_text_message(message["text"] or "")
                    continue
                chunk = message.get("bytes")
                if chunk:
                    await self._enqueue_audio_chunk(bytes(chunk))
        except WebSocketDisconnect:
            pass
        finally:
            self.stop_event.set()
            await self._finish_worker()

    def _normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider = str(payload.get("provider") or os.getenv("LIVE_STT_PROVIDER") or "groq").strip().lower()
        if provider not in {"local", "openai", "groq", "custom"}:
            provider = "groq"

        stt_model = str(payload.get("stt_model") or payload.get("model") or os.getenv("LIVE_STT_MODEL") or "").strip()
        if provider == "groq" and (not stt_model or stt_model == _FALLBACK_GROQ_STT_MODEL):
            stt_model = _DEFAULT_GROQ_STT_MODEL
        elif provider == "local" and not stt_model:
            stt_model = self.settings.local.model_id
        elif not stt_model:
            provider_section = getattr(self.settings.providers, provider, None)
            stt_model = getattr(provider_section, "model", "") or "default"

        llm_provider = str(payload.get("llm_provider") or os.getenv("LIVE_LLM_PROVIDER") or provider or "groq").strip().lower()
        if llm_provider not in {"openai", "groq", "custom"}:
            llm_provider = "groq"
        llm_model = str(payload.get("llm_model") or os.getenv("LIVE_LLM_MODEL") or "").strip()
        if llm_provider == "groq" and not llm_model:
            llm_model = _DEFAULT_GROQ_LLM_MODEL
        if llm_provider == "groq" and llm_model == "llama-3.1-8b-instant":
            llm_model = _DEFAULT_GROQ_LLM_MODEL

        mime_type = str(payload.get("mime_type") or "audio/webm").split(";", 1)[0].strip().lower()
        if not mime_type.startswith("audio/") and not mime_type.startswith("video/"):
            mime_type = "audio/webm"

        return {
            "provider": provider,
            "stt_model": stt_model,
            "language": str(payload.get("language") or os.getenv("LIVE_LANGUAGE") or "fa").strip().lower() or "fa",
            "prompt": str(payload.get("prompt") or "کلاس دانشگاهی به زبان فارسی. اصطلاحات تخصصی را با املای درست حفظ کن.").strip(),
            "audio_topic": str(payload.get("audio_topic") or os.getenv("LIVE_AUDIO_TOPIC") or "").strip(),
            "mime_type": mime_type,
            "llm_enabled": bool(payload.get("llm_enabled", os.getenv("LIVE_LLM_ENABLED", "true").lower() not in {"0", "false", "no", "off"})),
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_max_tokens": int(payload.get("llm_max_tokens") or 384),
            "llm_context_tokens": _safe_positive_int(payload.get("llm_context_tokens") or os.getenv("LIVE_LLM_CONTEXT_TOKENS"), _DEFAULT_LLM_CONTEXT_TOKENS),
            "stt_context_tokens": _safe_positive_int(payload.get("stt_context_tokens") or os.getenv("LIVE_STT_CONTEXT_TOKENS"), _DEFAULT_STT_CONTEXT_TOKENS),
        }

    def _public_config(self) -> Dict[str, Any]:
        return {k: v for k, v in self.config.items() if "key" not in k.lower()}

    async def _handle_text_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await self._send({"type": "warning", "message": "text websocket message ignored because it is not JSON"})
            return

        kind = payload.get("type")
        if kind == "stop":
            self.stop_event.set()
            await self.queue.put(None)
        elif kind == "ping":
            await self._send({"type": "pong", "uptime_sec": round(time.perf_counter() - self.started_at, 3)})
        elif kind == "config":
            self.config.update(self._normalize_config({**self.config, **payload}))
            await self._send({"type": "config", "config": self._public_config()})

    async def _enqueue_audio_chunk(self, chunk: bytes) -> None:
        if self.stop_event.is_set():
            return
        self.chunk_counter += 1
        chunk_index = self.chunk_counter
        if self.queue.full():
            self.dropped_chunks += 1
            await self._send({
                "type": "warning",
                "message": "live queue is full; dropping audio chunk to keep latency low",
                "dropped_chunks": self.dropped_chunks,
            })
            return
        await self.queue.put((chunk_index, chunk))
        await self._send({"type": "queued", "chunk_index": chunk_index, "queue_size": self.queue.qsize()})

    def _clear_pending_audio(self) -> int:
        cleared = 0
        while True:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                cleared += 1
            except asyncio.QueueEmpty:
                return cleared

    async def _finish_worker(self) -> None:
        if self.worker_task is None:
            return
        if not self.worker_task.done():
            try:
                self.queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            try:
                await asyncio.wait_for(self.worker_task, timeout=5)
            except asyncio.TimeoutError:
                self.worker_task.cancel()
        await self._send({
            "type": "done",
            "raw_text": self.raw_committed,
            "clean_text": self.clean_committed,
            "dropped_chunks": self.dropped_chunks,
        })

    async def _worker(self) -> None:
        while not self.stop_event.is_set():
            item = await self.queue.get()
            if item is None:
                self.queue.task_done()
                break
            chunk_index, chunk = item
            try:
                await self._process_chunk(chunk_index, chunk)
            except HTTPException as exc:
                if int(exc.status_code) in {401, 403}:
                    cleared = self._clear_pending_audio()
                    self.stop_event.set()
                    await self._send({
                        "type": "fatal",
                        "chunk_index": chunk_index,
                        "status_code": int(exc.status_code),
                        "message": _describe_upstream_http_error(exc, self.config),
                        "detail": str(exc.detail),
                        "cleared_queue_items": cleared,
                    })
                    break
                await self._send({
                    "type": "error",
                    "chunk_index": chunk_index,
                    "message": f"HTTPException: {exc.status_code}: {exc.detail}",
                })
            except Exception as exc:
                await self._send({
                    "type": "error",
                    "chunk_index": chunk_index,
                    "message": f"{exc.__class__.__name__}: {exc}",
                })
            finally:
                try:
                    self.queue.task_done()
                except ValueError:
                    pass

    async def _process_chunk(self, chunk_index: int, chunk: bytes) -> None:
        suffix = _suffix_for_mime(self.config["mime_type"])
        with tempfile.NamedTemporaryFile(prefix=f"tootak-live-{chunk_index}-", suffix=suffix, delete=False) as tmp:
            tmp.write(chunk)
            tmp_path = Path(tmp.name)

        started = time.perf_counter()
        try:
            await self._send({"type": "processing", "chunk_index": chunk_index})
            stt_result = await self._transcribe_chunk(tmp_path)
            stt_ms = round((time.perf_counter() - started) * 1000.0, 2)
            raw_text = str(stt_result.get("text") or "").strip()
            quality_flags = _quality_flags(stt_result)
            clean_payload = await self._clean_with_llm(raw_text, quality_flags)
            clean_text = str(clean_payload.get("cleaned_text") or raw_text).strip()

            raw_delta, self.raw_committed = _merge_delta(self.raw_committed, raw_text)
            clean_delta, self.clean_committed = _merge_delta(self.clean_committed, clean_text)
            context_budget = max(
                _safe_positive_int(self.config.get("llm_context_tokens"), _DEFAULT_LLM_CONTEXT_TOKENS),
                _safe_positive_int(self.config.get("stt_context_tokens"), _DEFAULT_STT_CONTEXT_TOKENS),
            )
            self.previous_context = _tail_tokens(self.clean_committed, context_budget)

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

    async def _transcribe_chunk(self, audio_path: Path) -> Dict[str, Any]:
        provider = self.config["provider"]
        prompt = self.config["prompt"]
        if provider != "local":
            prompt = _build_stt_prompt(
                base_prompt=self.config["prompt"],
                audio_topic=self.config.get("audio_topic", ""),
                previous_context=self.previous_context,
                context_tokens=_safe_positive_int(self.config.get("stt_context_tokens"), _DEFAULT_STT_CONTEXT_TOKENS),
            )
        options = {
            "provider": provider,
            "model": self.config["stt_model"],
            "language": self.config["language"],
            "prompt": prompt,
            "response_format": "verbose_json",
            "temperature": 0.0,
            "word_timestamps": False,
            "segment_timestamps": True,
            "vad_filter": True,
        }
        if provider == "local":
            return await self.transcription.local.transcribe(audio_path, options)
        try:
            return await self.transcription.api.transcribe(provider, audio_path, options)
        except HTTPException as exc:
            if provider == "groq" and int(exc.status_code) == 403 and options.get("model") == _DEFAULT_GROQ_STT_MODEL:
                fallback_options = {**options, "model": _FALLBACK_GROQ_STT_MODEL}
                await self._send({
                    "type": "warning",
                    "message": (
                        "Groq به مدل دقیق‌تر whisper-large-v3 دسترسی نداد؛ "
                        "برای ادامه live به whisper-large-v3-turbo fallback شد. "
                        "برای دقت بالاتر، مدل whisper-large-v3 را در Groq Project/Organization allow کن."
                    ),
                })
                result = await self.transcription.api.transcribe(provider, audio_path, fallback_options)
                self.config["stt_model"] = _FALLBACK_GROQ_STT_MODEL
                result.setdefault("metadata", {})
                if isinstance(result.get("metadata"), dict):
                    result["metadata"]["live_model_fallback"] = {
                        "from": _DEFAULT_GROQ_STT_MODEL,
                        "to": _FALLBACK_GROQ_STT_MODEL,
                        "reason": "403_forbidden",
                    }
                return result
            raise

    async def _clean_with_llm(self, raw_text: str, quality_flags: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not raw_text:
            return {"cleaned_text": "", "possible_missing_words": [], "uncertain_spans": [], "llm": {"enabled": False, "reason": "empty_text"}}
        if not self.config.get("llm_enabled"):
            return {"cleaned_text": raw_text, "possible_missing_words": [], "uncertain_spans": [], "llm": {"enabled": False, "reason": "disabled"}}

        provider_name = str(self.config.get("llm_provider") or "groq")
        provider = getattr(self.settings.providers, provider_name, None)
        if provider is None or not provider.enabled or not provider.all_api_keys():
            return {
                "cleaned_text": raw_text,
                "possible_missing_words": [],
                "uncertain_spans": [],
                "llm": {"enabled": False, "reason": f"{provider_name} provider is not enabled or has no key"},
            }

        model = str(self.config.get("llm_model") or "").strip()
        if not model:
            model = _DEFAULT_GROQ_LLM_MODEL if provider_name == "groq" else str(provider.model or "")
        if not model:
            return {"cleaned_text": raw_text, "possible_missing_words": [], "uncertain_spans": [], "llm": {"enabled": False, "reason": "empty_llm_model"}}

        llm_context_tokens = _safe_positive_int(self.config.get("llm_context_tokens"), _DEFAULT_LLM_CONTEXT_TOKENS)
        previous_context = _tail_tokens(self.previous_context, llm_context_tokens)
        audio_topic = str(self.config.get("audio_topic") or "").strip()

        url = _join_provider_path(provider.base_url, "/v1/chat/completions")
        headers = {"Authorization": f"Bearer {provider.all_api_keys()[0]}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": int(self.config.get("llm_max_tokens") or 384),
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "تو ویراستار بلادرنگ ترنسکریپت فارسی هستی. audio_topic و previous_context فقط برای فهم موضوع، جمله، ضمیر، اصطلاحات و پیوستگی است. "
                        "فقط raw_transcript_chunk را پاکسازی کن و متن قبلی را دوباره در cleaned_text تکرار نکن. "
                        "فقط نویزهای آشکار ASR، تکرارهای بی‌معنا، فاصله‌گذاری و املای واضح را اصلاح کن. "
                        "خلاصه‌سازی، اضافه‌کردن اطلاعات جدید و حدس قطعی ممنوع است. اگر بخشی احتمالاً افتاده یا نامفهوم است "
                        "آن را در possible_missing_words یا uncertain_spans گزارش کن، اما متن ساختگی وارد cleaned_text نکن. خروجی فقط JSON معتبر باشد."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "audio_topic": audio_topic,
                            "previous_context": previous_context,
                            "previous_context_token_budget": llm_context_tokens,
                            "raw_transcript_chunk": raw_text,
                            "quality_flags": quality_flags,
                            "required_json_schema": {
                                "cleaned_text": "string; cleaned version of raw_transcript_chunk only",
                                "possible_missing_words": ["string"],
                                "uncertain_spans": ["string"],
                                "notes": "string",
                            },
                        },
                        ensure_ascii=False,
                    ),
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
            parsed = _parse_json_object(content)
            if not parsed:
                parsed = {"cleaned_text": content or raw_text, "possible_missing_words": [], "uncertain_spans": [], "notes": "non_json_llm_output"}
            parsed.setdefault("cleaned_text", raw_text)
            parsed.setdefault("possible_missing_words", [])
            parsed.setdefault("uncertain_spans", [])
            parsed["llm"] = {
                "enabled": True,
                "provider": provider_name,
                "model": model,
                "context_tokens": llm_context_tokens,
                "audio_topic_used": bool(audio_topic),
                "process_ms": round((time.perf_counter() - started) * 1000.0, 2),
            }
            return parsed
        except Exception as exc:
            return _llm_fail_open(raw_text, provider_name, model, f"{exc.__class__.__name__}: {exc}")

    async def _send(self, payload: Dict[str, Any]) -> None:
        try:
            await self.websocket.send_json(payload)
        except Exception:
            self.stop_event.set()


def _llm_fail_open(raw_text: str, provider: str, model: str, reason: str) -> Dict[str, Any]:
    return {
        "cleaned_text": raw_text,
        "possible_missing_words": [],
        "uncertain_spans": [],
        "llm": {"enabled": False, "provider": provider, "model": model, "reason": reason},
    }


def _describe_upstream_http_error(exc: HTTPException, config: Dict[str, Any]) -> str:
    provider = str(config.get("provider") or "provider")
    model = str(config.get("stt_model") or "model")
    detail = str(exc.detail)
    if int(exc.status_code) == 403 and provider == "groq":
        return (
            f"Groq درخواست transcription را Forbidden کرد. معمولاً یعنی API key یا Project/Organization به مدل STT '{model}' دسترسی ندارد. "
            "در Groq Console بخش Settings → Project/Organization → Limits را چک کن و مدل‌های whisper-large-v3-turbo یا whisper-large-v3 را allow کن، "
            "یا یک API key جدید از همان project بساز. تا رفع این خطا live متوقف شد تا queue پر نشود. "
            f"جزئیات upstream: {detail[:240]}"
        )
    if int(exc.status_code) == 401:
        return (
            f"کلید {provider} نامعتبر است یا در .env درست load نشده. مقدار API key را بدون فاصله/quote اضافه چک کن. "
            f"جزئیات upstream: {detail[:240]}"
        )
    return f"upstream {provider} transcription failed with HTTP {exc.status_code}: {detail[:240]}"


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


def _join_provider_path(base_url: str, path: str) -> str:
    base = str(base_url or "").rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        return base + path[3:]
    return base + "/" + path.lstrip("/")


def _safe_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _tail_tokens(text: str, max_tokens: int) -> str:
    words = str(text or "").split()
    if not words:
        return ""
    return " ".join(words[-max(1, int(max_tokens)):])


def _limit_tokens(text: str, max_tokens: int) -> str:
    words = str(text or "").split()
    if len(words) <= max_tokens:
        return " ".join(words)
    return " ".join(words[-max_tokens:])


def _build_stt_prompt(base_prompt: str, audio_topic: str, previous_context: str, context_tokens: int) -> str:
    parts: List[str] = []
    base = " ".join(str(base_prompt or "").split())
    topic = " ".join(str(audio_topic or "").split())
    if base:
        parts.append(base)
    if topic:
        parts.append(f"موضوع صدا: {topic}")
    context_budget = min(max(0, int(context_tokens)), _MAX_STT_PROMPT_TOKENS - 48)
    context = _tail_tokens(previous_context, context_budget)
    if context:
        parts.append("متن قبلی فقط برای حفظ پیوستگی، املای اصطلاحات و سبک گفتار است؛ ادامه متن را از روی آن حدس نزن:")
        parts.append(context)
    return _limit_tokens("\n".join(parts), _MAX_STT_PROMPT_TOKENS)


def _suffix_for_mime(mime_type: str) -> str:
    if "wav" in mime_type:
        return ".wav"
    if "mpeg" in mime_type or "mp3" in mime_type:
        return ".mp3"
    if "mp4" in mime_type or "m4a" in mime_type:
        return ".m4a"
    if "ogg" in mime_type or "opus" in mime_type:
        return ".ogg"
    return ".webm"


def _quality_flags(stt_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    segments = stt_result.get("segments")
    if not isinstance(segments, list):
        upstream = stt_result.get("metadata", {}).get("upstream_raw", {}) if isinstance(stt_result.get("metadata"), dict) else {}
        segments = upstream.get("segments") if isinstance(upstream, dict) else None
    if not isinstance(segments, list):
        return flags

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        avg_logprob = seg.get("avg_logprob")
        no_speech_prob = seg.get("no_speech_prob")
        compression_ratio = seg.get("compression_ratio")
        text = str(seg.get("text") or "").strip()
        item: Dict[str, Any] = {"text": text, "start": seg.get("start"), "end": seg.get("end")}
        reasons: List[str] = []
        if isinstance(avg_logprob, (int, float)) and avg_logprob < -0.5:
            reasons.append("low_confidence")
        if isinstance(no_speech_prob, (int, float)) and no_speech_prob > 0.6:
            reasons.append("possible_non_speech")
        if isinstance(compression_ratio, (int, float)) and (compression_ratio > 2.4 or compression_ratio < 0.4):
            reasons.append("unusual_compression")
        if reasons:
            item["reasons"] = reasons
            item["avg_logprob"] = avg_logprob
            item["no_speech_prob"] = no_speech_prob
            item["compression_ratio"] = compression_ratio
            flags.append(item)
    return flags


def _merge_delta(committed: str, incoming: str) -> Tuple[str, str]:
    incoming = " ".join(str(incoming or "").split())
    committed = str(committed or "").strip()
    if not incoming:
        return "", committed
    if not committed:
        return incoming, incoming
    tail = committed[-1200:]
    if incoming in tail:
        return "", committed

    left_words = committed.split()
    right_words = incoming.split()
    max_k = min(32, len(left_words), len(right_words))
    for k in range(max_k, 0, -1):
        if left_words[-k:] == right_words[:k]:
            delta = " ".join(right_words[k:]).strip()
            if not delta:
                return "", committed
            return delta, f"{committed} {delta}".strip()
    return incoming, f"{committed} {incoming}".strip()
