from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


logging.basicConfig(
    level=getattr(logging, os.getenv("QUEUE_WORKER_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("queue-worker")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class JobCancelledError(RuntimeError):
    pass


@dataclass(slots=True)
class WorkerSettings:
    queue_base_url: str
    queue_token: str
    worker_id: str
    poll_interval_sec: float
    lease_sec: int

    local_stt_url: str
    local_stt_jobs_url: str
    local_stt_provider: str
    local_stt_model: str
    local_stt_language: str
    local_stt_timeout_sec: float
    local_stt_profile: str
    local_stt_chunk_minutes: float
    local_stt_chunk_overlap_minutes: float

    openai_api_key: str
    openai_base_url: str
    openai_fallback_base_urls: tuple[str, ...]
    openai_proxy_url: str
    openai_model: str
    openai_timeout_sec: float
    openai_retry_rounds: int
    openai_retry_backoff_sec: float
    openai_allow_public_fallback: bool

    llm_prompt_template: str
    llm_prompt_template_strict: str
    llm_fail_open: bool


def _env(name: str, default: str = "") -> str:
    val = os.getenv(name)
    return default if val is None else val


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def normalize_proxy_env() -> None:
    for key in ["ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
        value = os.getenv(key)
        if not value:
            continue
        if value.startswith("socks://"):
            os.environ[key] = "socks5://" + value[len("socks://"):]


def _parse_base_urls(raw: str) -> tuple[str, ...]:
    urls: list[str] = []
    for chunk in str(raw or "").split(","):
        item = chunk.strip().rstrip("/")
        if item and item not in urls:
            urls.append(item)
    return tuple(urls)


def load_settings() -> WorkerSettings:
    load_dotenv(_env("ENV_FILE", ".env"), override=False)
    worker_id = _env("QUEUE_WORKER_ID", "").strip() or f"local-{socket.gethostname()}"
    return WorkerSettings(
        queue_base_url=_env("QUEUE_SERVER_BASE_URL", "http://127.0.0.1:8090").rstrip("/"),
        queue_token=_env("QUEUE_WORKER_TOKEN", "").strip(),
        worker_id=worker_id,
        poll_interval_sec=float(_env("QUEUE_POLL_INTERVAL_SEC", "3")),
        lease_sec=max(120, int(_env("QUEUE_LEASE_SEC", "1800"))),
        local_stt_url=_env("LOCAL_STT_URL", "http://127.0.0.1:8000/transcribe").strip(),
        local_stt_jobs_url=_env("LOCAL_STT_JOBS_URL", "http://127.0.0.1:8000/transcribe/jobs").strip(),
        local_stt_provider=_env("LOCAL_STT_PROVIDER", "local").strip(),
        local_stt_model=_env("LOCAL_STT_MODEL", "").strip(),
        local_stt_language=_env("LOCAL_STT_LANGUAGE", "fa").strip(),
        local_stt_timeout_sec=float(_env("LOCAL_STT_TIMEOUT_SEC", "1800")),
        local_stt_profile=_env("LOCAL_STT_PROFILE", "ultra").strip().lower(),
        local_stt_chunk_minutes=float(_env("LOCAL_STT_CHUNK_MINUTES", "10")),
        local_stt_chunk_overlap_minutes=float(_env("LOCAL_STT_CHUNK_OVERLAP_MINUTES", "5")),
        openai_api_key=_env("OPENAI_API_KEY", "").strip(),
        openai_base_url=_env("OPENAI_BASE_URL", "https://api.gapgpt.app/v1").rstrip("/"),
        openai_fallback_base_urls=_parse_base_urls(
            _env("OPENAI_FALLBACK_BASE_URLS", "https://api.gapapi.com/v1,https://api.openai.com/v1")
        ),
        openai_proxy_url=_env("OPENAI_PROXY_URL", "").strip(),
        openai_model=_env("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_timeout_sec=float(_env("OPENAI_TIMEOUT_SEC", "120")),
        openai_retry_rounds=max(1, int(_env("OPENAI_RETRY_ROUNDS", "3"))),
        openai_retry_backoff_sec=max(0.25, float(_env("OPENAI_RETRY_BACKOFF_SEC", "1.2"))),
        openai_allow_public_fallback=_env_bool("OPENAI_ALLOW_PUBLIC_OPENAI_FALLBACK", False),
        llm_prompt_template=_env(
            "LLM_PROMPT_TEMPLATE",
            (
                "تو یک ویراستار حرفه‌ای ترنسکریپت هستی.\n"
                "متن خام گفتار را کامل نگه دار و هرگز خلاصه‌سازی نکن.\n"
                "هیچ بخش محتوایی را حذف نکن، فقط خوانایی و نظم متن را بهتر کن.\n"
                "غلط‌های املایی/نگارشی را اصلاح کن و واژه‌های اشتباه را با قرینهٔ واضح درست کن.\n"
                "پاراگراف‌بندی مناسب انجام بده اما معنی و اطلاعات اصلی را حفظ کن.\n"
                "خروجی را دقیقا در فرمت {format} برگردان و توضیح اضافه ننویس."
            ),
        ),
        llm_prompt_template_strict=_env(
            "LLM_PROMPT_TEMPLATE_STRICT",
            (
                "تو یک ویرایشگر حداقلی ترنسکریپت هستی.\n"
                "خلاصه‌سازی، بازنویسی مفهومی یا حذف محتوا ممنوع است.\n"
                "متن را تا حد ممکن نزدیک به نسخه خام نگه دار.\n"
                "فقط اشتباه‌های واضح املایی/نگارشی و شکست‌های بدیهی کلمات را اصلاح کن.\n"
                "ترتیب جملات، جزئیات و تکرارهای طبیعی گفتار را حفظ کن.\n"
                "خروجی را دقیقا در فرمت {format} برگردان و هیچ توضیحی اضافه نکن."
            ),
        ),
        llm_fail_open=_env_bool("LLM_FAIL_OPEN", True),
    )


class QueueWorker:
    def __init__(self, settings: WorkerSettings) -> None:
        self.s = settings
        if not self.s.queue_token:
            raise ValueError("QUEUE_WORKER_TOKEN is required")
        if not self.s.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if self.s.openai_proxy_url:
            for key in ["ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
                os.environ[key] = self.s.openai_proxy_url
        normalize_proxy_env()
        queue_limits = httpx.Limits(max_connections=30, max_keepalive_connections=0)
        # Queue endpoints should be called directly to avoid local proxy 502 issues.
        self.queue_client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0),
            trust_env=False,
            limits=queue_limits,
            headers={"Connection": "close"},
        )
        # LLM endpoints can use system proxy settings when available.
        self.llm_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
        # Local STT must bypass proxy to avoid flaky 502 errors on localhost.
        self.local_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0), trust_env=False)

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.s.queue_token}"}

    async def close(self) -> None:
        await self.queue_client.aclose()
        await self.llm_client.aclose()
        await self.local_client.aclose()

    async def run_forever(self) -> None:
        logger.info("worker started: worker_id=%s queue=%s", self.s.worker_id, self.s.queue_base_url)
        while True:
            try:
                claimed = await self.claim_job()
                if claimed is None:
                    await asyncio.sleep(self.s.poll_interval_sec)
                    continue
                try:
                    await self.process_job(claimed)
                except JobCancelledError as exc:
                    logger.info("job cancelled and stopped: %s", exc)
                except Exception as exc:
                    job_id = str(claimed.get("job_id") or "")
                    if job_id:
                        await self.fail_job(job_id, str(exc))
                    raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("worker loop error: %s", exc)
                await asyncio.sleep(max(2.0, self.s.poll_interval_sec))

    async def claim_job(self) -> Optional[dict]:
        url = f"{self.s.queue_base_url}/internal/jobs/claim"
        payload = {"worker_id": self.s.worker_id, "lease_sec": self.s.lease_sec}
        resp = await self.queue_client.post(url, headers=self._auth_headers(), json=payload)
        if resp.status_code == 204:
            return None
        if resp.status_code >= 400:
            raise RuntimeError(f"claim failed {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    async def process_job(self, job: dict) -> None:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            raise RuntimeError("invalid claim payload without job_id")

        fmt = str(job.get("output_format") or "txt").lower().strip()
        if fmt not in {"txt", "md", "json"}:
            fmt = "txt"

        audio_url = str(job.get("audio_download_url") or "").strip()
        if not audio_url:
            raise RuntimeError(f"job {job_id} has empty audio_download_url")
        lang = str(job.get("language") or "").strip()
        vocabulary_bias = str(job.get("vocabulary_bias") or "").strip()
        content_description = str(job.get("content_description") or "").strip()
        llm_enhance_text = str(job.get("llm_enhance_text", "1")).strip().lower() not in {"0", "false", "off", "no"}
        stt_quality_mode = str(job.get("stt_quality_mode") or "accurate").strip().lower()
        if stt_quality_mode not in {"accurate", "fast"}:
            stt_quality_mode = "accurate"

        logger.info(
            "processing job=%s format=%s stt_quality_mode=%s llm_enhance_text=%s",
            job_id,
            fmt,
            stt_quality_mode,
            llm_enhance_text,
        )
        await self.ensure_job_active(job_id)
        await self.update_progress(job_id, 30, "preparing_audio", status="processing")

        with tempfile.TemporaryDirectory(prefix=f"job_{job_id}_") as td:
            temp_dir = Path(td)
            audio_path = temp_dir / self._audio_filename_from_url(audio_url)
            await self.download_audio(audio_url, audio_path)
            await self.ensure_job_active(job_id)
            duration_sec = self._probe_local_duration_sec(audio_path)
            if duration_sec > 0:
                await self.update_source_meta(job_id, duration_sec)
            await self.update_progress(job_id, 45, "stt_validating", status="processing")

            transcript = await self.transcribe_audio(
                job_id,
                audio_path,
                language=lang,
                vocabulary_bias=vocabulary_bias,
                stt_quality_mode=stt_quality_mode,
            )
            await self.ensure_job_active(job_id)
            await self.update_progress(job_id, 80, "llm_processing", status="processing")
            llm_output = await self._build_llm_output_with_fallback(
                job_id=job_id,
                transcript=transcript,
                fmt=fmt,
                content_description=content_description,
                llm_enhance_text=llm_enhance_text,
            )

            await self.ensure_job_active(job_id)
            out_path, out_mime = self.build_output_file(temp_dir=temp_dir, job_id=job_id, fmt=fmt, transcript=transcript, llm_output=llm_output)
            await self.update_progress(job_id, 94, "building_output", status="processing")
            await self.complete_job(job_id, transcript, llm_output, out_path, out_mime)

        logger.info("job completed and sent: %s", job_id)

    async def _build_llm_output_with_fallback(
        self,
        job_id: str,
        transcript: str,
        fmt: str,
        content_description: str,
        llm_enhance_text: bool,
    ) -> str:
        if not llm_enhance_text:
            return self._normalize_transcript_text(transcript)

        try:
            return await self.call_openai(job_id, transcript, fmt, content_description, llm_enhance_text)
        except Exception as exc:
            if not self.s.llm_fail_open:
                raise

            friendly = self._friendly_llm_error(exc)
            logger.warning(
                "llm unavailable for job=%s; fail-open enabled, using transcript output. reason=%s",
                job_id,
                friendly,
            )
            await self.update_progress(job_id, 92, "llm_degraded", status="processing")
            return self._normalize_transcript_text(transcript)

    def _audio_filename_from_url(self, audio_url: str) -> str:
        parsed = urlparse(audio_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".webm", ".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mpeg", ".mpg"}:
            return f"input_audio{suffix}"
        return "input_audio.m4a"

    async def download_audio(self, audio_url: str, output_path: Path) -> None:
        async with self.queue_client.stream("GET", audio_url, headers=self._auth_headers()) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(f"audio download failed {resp.status_code}: {resp.text[:300]}")
            with output_path.open("wb") as fh:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    fh.write(chunk)

    async def transcribe_audio(
        self,
        parent_job_id: str,
        audio_path: Path,
        language: str,
        vocabulary_bias: str,
        stt_quality_mode: str,
    ) -> str:
        data = self._build_stt_form_data(
            language=language,
            vocabulary_bias=vocabulary_bias,
            stt_quality_mode=stt_quality_mode,
        )

        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                stt_job_id = await self.create_stt_job(audio_path, data)
                text = await self.wait_stt_job(parent_job_id, stt_job_id)
                if not text:
                    raise RuntimeError("local stt returned empty text")
                return text
            except Exception as exc:
                last_error = exc
                if attempt >= 3:
                    break
                wait_sec = float(attempt)
                logger.warning("local stt attempt %s failed: %s (retry in %.1fs)", attempt, exc, wait_sec)
                await asyncio.sleep(wait_sec)

        raise RuntimeError(str(last_error) if last_error else "local stt failed")

    def _build_stt_form_data(self, language: str, vocabulary_bias: str, stt_quality_mode: str) -> dict[str, str]:
        data: dict[str, str] = {
            "provider": self.s.local_stt_provider,
            "response_format": "verbose_json",
        }
        if self.s.local_stt_model:
            data["model"] = self.s.local_stt_model
        lang = language or self.s.local_stt_language
        if lang:
            data["language"] = lang
        if vocabulary_bias:
            data["vocabulary_bias"] = vocabulary_bias

        if self.s.local_stt_profile == "ultra":
            data.update(
                {
                    "temperature": "0",
                    "beam_size": "10",
                    "best_of": "10",
                    "patience": "1.3",
                    "word_timestamps": "true",
                    "segment_timestamps": "true",
                    "vad_filter": "true",
                    "condition_on_previous_text": "true",
                    "repetition_penalty": "1.0",
                    "no_repeat_ngram_size": "0",
                    "compression_ratio_threshold": "2.4",
                    "log_prob_threshold": "-1.0",
                    "no_speech_threshold": "0.6",
                    "prompt_reset_on_temperature": "0.5",
                    "chunking_enabled": "true",
                    "chunk_minutes": str(self.s.local_stt_chunk_minutes),
                    "chunk_overlap_minutes": str(self.s.local_stt_chunk_overlap_minutes),
                    "chunk_min_duration_minutes": str(self.s.local_stt_chunk_minutes),
                }
            )
            if stt_quality_mode == "fast":
                fast_chunk_minutes = max(6.0, float(self.s.local_stt_chunk_minutes))
                data.update(
                    {
                        "beam_size": "4",
                        "best_of": "4",
                        "patience": "1.0",
                        "word_timestamps": "false",
                        "segment_timestamps": "false",
                        "condition_on_previous_text": "true",
                        "chunk_minutes": str(fast_chunk_minutes),
                        "chunk_overlap_minutes": "0",
                        "chunk_min_duration_minutes": str(fast_chunk_minutes),
                    }
                )
        return data

    async def create_stt_job(self, audio_path: Path, data: dict[str, str]) -> str:
        mime = self._mime_for_path(audio_path)
        with audio_path.open("rb") as fh:
            files = {"file": (audio_path.name or "audio.m4a", fh, mime)}
            resp = await self.local_client.post(
                self.s.local_stt_jobs_url,
                data=data,
                files=files,
                timeout=300,
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"local stt job create failed {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise RuntimeError("local stt job create missing job_id")
        return job_id

    async def wait_stt_job(self, parent_job_id: str, stt_job_id: str) -> str:
        url = f"{self.s.local_stt_jobs_url}/{stt_job_id}"
        deadline = asyncio.get_running_loop().time() + self.s.local_stt_timeout_sec
        while True:
            await self.ensure_job_active(parent_job_id)
            if asyncio.get_running_loop().time() > deadline:
                raise RuntimeError("local stt job timeout")
            resp = await self.local_client.get(url, timeout=30)
            if resp.status_code >= 400:
                raise RuntimeError(f"local stt job poll failed {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
            status = str(payload.get("status") or "").strip().lower()
            progress = float(payload.get("progress_percent") or 0.0)
            stage = str(payload.get("stage") or "transcribing").strip().replace("-", "_")
            if stage == "completed":
                stage = "transcribing"
            stage_alias = {
                "validating": "stt_validating",
                "preparing_audio": "stt_preparing_audio",
                "preparing_audio_chunks": "stt_preparing_audio",
                "loading_model": "stt_loading_model",
                "transcribing": "stt_extracting_text",
                "finalizing": "stt_postprocessing",
            }.get(stage, "stt_extracting_text")
            overall = int(45 + min(100.0, max(0.0, progress)) * 0.35)
            await self.update_progress(parent_job_id, overall, stage_alias, status="processing")
            if status == "completed":
                result = payload.get("result") or {}
                text = str(result.get("text") or "").strip()
                return text
            if status in {"failed", "cancelled"}:
                err = str(payload.get("error") or status)
                raise RuntimeError(f"local stt failed: {err}")
            await asyncio.sleep(1.0)

    def _mime_for_path(self, path: Path) -> str:
        by_ext = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
            ".ogg": "audio/ogg",
            ".opus": "audio/ogg",
            ".flac": "audio/flac",
            ".wma": "audio/x-ms-wma",
            ".webm": "video/webm",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".avi": "video/x-msvideo",
            ".m4v": "video/x-m4v",
            ".mpeg": "video/mpeg",
            ".mpg": "video/mpeg",
        }
        return by_ext.get(path.suffix.lower(), "application/octet-stream")

    async def call_openai(
        self,
        job_id: str,
        transcript: str,
        fmt: str,
        content_description: str,
        llm_enhance_text: bool,
    ) -> str:
        base_template = self.s.llm_prompt_template if llm_enhance_text else self.s.llm_prompt_template_strict
        prompt = base_template.replace("{format}", fmt.upper())
        context_block = ""
        if content_description:
            context_block = f"توضیح کاربر درباره محتوای فایل:\n{content_description}\n\n"
        user_text = f"{context_block}متن خام:\n{transcript}"

        headers = {
            "Authorization": f"Bearer {self.s.openai_api_key}",
            "Content-Type": "application/json",
        }

        base_urls = [self.s.openai_base_url]
        for alt in self.s.openai_fallback_base_urls:
            if alt and alt not in base_urls:
                base_urls.append(alt)
        if not self.s.openai_allow_public_fallback:
            base_urls = [b for b in base_urls if "api.openai.com" not in b]
        if not base_urls:
            raise RuntimeError("هیچ endpoint فعالی برای پردازش متن تنظیم نشده است.")

        requests: list[tuple[str, str, dict]] = []
        for base in base_urls:
            requests.append(
                (
                    base,
                    f"{base}/chat/completions",
                    {
                        "model": self.s.openai_model,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_text},
                        ],
                        "temperature": 0.1,
                    },
                )
            )
            requests.append(
                (
                    base,
                    f"{base}/responses",
                    {
                        "model": self.s.openai_model,
                        "input": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_text},
                        ],
                    },
                )
            )

        last_error: Optional[Exception] = None
        skipped_bases: set[str] = set()
        total_attempts = max(1, len(requests) * self.s.openai_retry_rounds)
        attempt_idx = 0
        for round_idx in range(self.s.openai_retry_rounds):
            for request_idx, (base, url, payload) in enumerate(requests):
                if base in skipped_bases:
                    continue
                attempt_idx += 1
                try:
                    await self.ensure_job_active(job_id)
                    progress = 80 + min(12, int((attempt_idx / max(1, total_attempts)) * 12))
                    await self.update_progress(job_id, progress, "llm_processing", status="processing")
                    resp = await self.llm_client.post(url, headers=headers, json=payload, timeout=self.s.openai_timeout_sec)
                    if resp.status_code >= 400:
                        body = (resp.text or "").strip()
                        if resp.status_code in {401, 403}:
                            skipped_bases.add(base)
                        raise RuntimeError(
                            f"llm failed {resp.status_code} on {url}: {self._compact_error_text(body)}"
                        )
                    data = resp.json()
                    text = self._extract_chat_text(data) or self._extract_response_text(data)
                    if not text:
                        raise RuntimeError(f"llm returned empty output text on {url}")
                    logger.info("llm request succeeded via %s", url)
                    return text
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "llm attempt failed (%s/%s, round=%s): %s",
                        attempt_idx,
                        total_attempts,
                        round_idx + 1,
                        exc,
                    )
                    if attempt_idx >= total_attempts:
                        break
                    wait_sec = min(
                        8.0,
                        (self.s.openai_retry_backoff_sec * (round_idx + 1)) + (0.35 * (request_idx + 1)),
                    )
                    await asyncio.sleep(wait_sec)
            if attempt_idx >= total_attempts:
                break
        msg = str(last_error or "llm request failed")
        if any(
            token in msg
            for token in (
                "Temporary failure in name resolution",
                "Name or service not known",
                "nodename nor servname provided",
                "getaddrinfo failed",
            )
        ):
            raise RuntimeError("اتصال شبکه برای دسترسی به سرویس پردازش متن برقرار نشد. دوباره تلاش کن.")
        if "llm failed 522" in msg:
            raise RuntimeError("سرویس پردازش متن موقتا در دسترس نیست (522). چند دقیقه دیگر دوباره تلاش کن.")
        if "llm failed 502" in msg or "llm failed 504" in msg:
            raise RuntimeError("درگاه پردازش متن موقتا ناپایدار است (502/504). لطفا دوباره تلاش کن.")
        raise RuntimeError(msg)

    def _friendly_llm_error(self, exc: Exception) -> str:
        msg = str(exc or "").strip()
        if not msg:
            return "unknown llm error"
        if "failed 522" in msg:
            return "upstream timeout (522)"
        if "failed 502" in msg:
            return "upstream bad gateway (502)"
        if "failed 504" in msg:
            return "upstream gateway timeout (504)"
        if "failed 401" in msg or "invalid_api_key" in msg:
            return "invalid upstream api key (401)"
        if "Temporary failure in name resolution" in msg or "getaddrinfo failed" in msg:
            return "dns resolution failure"
        return msg[:220]

    def _normalize_transcript_text(self, text: str) -> str:
        lines = [ln.strip() for ln in str(text or "").splitlines()]
        compact_lines: list[str] = []
        prev_empty = False
        for ln in lines:
            if not ln:
                if prev_empty:
                    continue
                compact_lines.append("")
                prev_empty = True
                continue
            compact_lines.append(" ".join(ln.split()))
            prev_empty = False
        return "\n".join(compact_lines).strip() or str(text or "").strip()

    def _compact_error_text(self, body: str) -> str:
        raw = str(body or "").strip()
        if not raw:
            return "-"
        if "<title>" in raw and "</title>" in raw:
            start = raw.find("<title>")
            end = raw.find("</title>", start + 7)
            if start >= 0 and end > start:
                title = raw[start + 7:end].strip()
                if title:
                    return title[:180]
        squashed = " ".join(raw.replace("\n", " ").replace("\r", " ").split())
        return squashed[:260]

    async def ensure_job_active(self, job_id: str) -> None:
        url = f"{self.s.queue_base_url}/internal/jobs/{job_id}/state"
        try:
            resp = await self.queue_client.get(url, headers=self._auth_headers(), timeout=10)
        except Exception:
            return
        if resp.status_code == 404:
            raise JobCancelledError(f"{job_id}: deleted by user")
        if resp.status_code >= 400:
            return
        payload = resp.json()
        status = str(payload.get("status") or "").strip().lower()
        if status in {"cancelled"}:
            raise JobCancelledError(f"{job_id}: cancelled")

    def _extract_chat_text(self, payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list):
            return ""
        chunks: list[str] = []
        for item in choices:
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                chunks.append(content.strip())
        return "\n".join(chunks).strip()

    def _extract_response_text(self, payload: dict) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        output = payload.get("output")
        if not isinstance(output, list):
            return ""

        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                txt = part.get("text")
                if isinstance(txt, str) and txt.strip():
                    chunks.append(txt.strip())
        return "\n".join(chunks).strip()

    def build_output_file(self, temp_dir: Path, job_id: str, fmt: str, transcript: str, llm_output: str) -> tuple[Path, str]:
        if fmt == "md":
            out = temp_dir / f"{job_id}.md"
            out.write_text(llm_output, encoding="utf-8")
            return out, "text/markdown"

        if fmt == "json":
            out = temp_dir / f"{job_id}.json"
            payload = {
                "job_id": job_id,
                "transcript": transcript,
                "result": llm_output,
            }
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return out, "application/json"

        out = temp_dir / f"{job_id}.txt"
        out.write_text(llm_output, encoding="utf-8")
        return out, "text/plain"

    async def complete_job(self, job_id: str, transcript: str, llm_output: str, output_file: Path, mime: str) -> None:
        url = f"{self.s.queue_base_url}/internal/jobs/{job_id}/complete"
        data = {
            "worker_id": self.s.worker_id,
            "transcript_text": transcript,
            "llm_text": llm_output,
        }
        with output_file.open("rb") as fh:
            files = {"result_file": (output_file.name, fh, mime)}
            resp = await self.queue_client.post(url, headers=self._auth_headers(), data=data, files=files, timeout=180)

        if resp.status_code >= 400:
            raise RuntimeError(f"complete failed {resp.status_code}: {resp.text[:500]}")

    async def fail_job(self, job_id: str, error: str) -> None:
        url = f"{self.s.queue_base_url}/internal/jobs/{job_id}/fail"
        data = {"worker_id": self.s.worker_id, "error": error[:3000]}
        resp = await self.queue_client.post(url, headers=self._auth_headers(), data=data)
        if resp.status_code >= 400:
            logger.error("unable to mark failed job=%s (%s): %s", job_id, resp.status_code, resp.text[:300])

    async def update_progress(self, job_id: str, percent: int, stage: str, status: str = "processing") -> None:
        url = f"{self.s.queue_base_url}/internal/jobs/{job_id}/progress"
        payload = {
            "worker_id": self.s.worker_id,
            "progress_percent": max(0, min(99, int(percent))),
            "stage": stage,
            "status": status,
        }
        try:
            resp = await self.queue_client.post(url, headers=self._auth_headers(), json=payload, timeout=20)
            if resp.status_code >= 400:
                logger.warning("progress update failed job=%s (%s): %s", job_id, resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("progress update error job=%s: %s", job_id, exc)

    async def update_source_meta(self, job_id: str, duration_sec: float) -> None:
        url = f"{self.s.queue_base_url}/internal/jobs/{job_id}/meta"
        payload = {
            "worker_id": self.s.worker_id,
            "source_duration_sec": max(0.0, float(duration_sec)),
        }
        try:
            resp = await self.queue_client.post(url, headers=self._auth_headers(), json=payload, timeout=20)
            if resp.status_code >= 400:
                logger.warning("source meta update failed job=%s (%s): %s", job_id, resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("source meta update error job=%s: %s", job_id, exc)

    def _probe_local_duration_sec(self, path: Path) -> float:
        try:
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if proc.returncode != 0:
                return 0.0
            raw = (proc.stdout or "").strip()
            return max(0.0, float(raw)) if raw else 0.0
        except Exception:
            return 0.0


async def amain() -> None:
    settings = load_settings()
    worker = QueueWorker(settings)
    try:
        await worker.run_forever()
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(amain())
