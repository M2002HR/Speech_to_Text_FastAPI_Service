from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, UploadFile

from .config import ProviderSection, Settings


VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg"
}
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".webm"
}

MODEL_PRESETS = [
    {
        "name": "faster-whisper-tiny",
        "repo_id": "Systran/faster-whisper-tiny",
        "notes": "Very fast, lower accuracy",
    },
    {
        "name": "faster-whisper-small",
        "repo_id": "Systran/faster-whisper-small",
        "notes": "Balanced speed/quality",
    },
    {
        "name": "faster-whisper-medium",
        "repo_id": "Systran/faster-whisper-medium",
        "notes": "Higher accuracy, heavier",
    },
    {
        "name": "faster-whisper-large-v3",
        "repo_id": "Systran/faster-whisper-large-v3",
        "notes": "Best quality among common Whisper variants",
    },
    {
        "name": "openai-whisper-large-v3",
        "repo_id": "openai/whisper-large-v3",
        "notes": "Official whisper-large-v3 repo",
    },
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def join_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def is_video_file(filename: str, content_type: Optional[str]) -> bool:
    suffix = Path(filename).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return True
    if content_type and content_type.startswith("video/"):
        return True
    return False


def is_audio_file(filename: str, content_type: Optional[str]) -> bool:
    suffix = Path(filename).suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return True
    if content_type and content_type.startswith("audio/"):
        return True
    return False


def sanitize_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    return safe.strip("._") or "file"


class MediaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ffmpeg_available(self) -> bool:
        return shutil.which(self.settings.processing.ffmpeg_binary) is not None

    def ffprobe_available(self) -> bool:
        return shutil.which(self.settings.processing.ffprobe_binary) is not None

    async def save_upload(self, upload: UploadFile) -> Path:
        max_bytes = self.settings.storage.max_upload_mb * 1024 * 1024
        src_name = sanitize_name(upload.filename or f"upload-{uuid.uuid4().hex}")
        file_id = uuid.uuid4().hex
        dest_path = Path(self.settings.storage.upload_dir) / f"{file_id}_{src_name}"

        total = 0
        with dest_path.open("wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"file is too large (>{self.settings.storage.max_upload_mb} MB)")
                f.write(chunk)
        await upload.close()
        return dest_path

    async def extract_audio(self, input_path: Path, source_name: str, content_type: Optional[str]) -> Path:
        needs_extract = self.settings.processing.always_extract_audio or is_video_file(source_name, content_type)
        if not needs_extract:
            return input_path

        if not self.ffmpeg_available():
            raise HTTPException(
                status_code=500,
                detail=f"ffmpeg binary not found: {self.settings.processing.ffmpeg_binary}",
            )

        out_ext = self.settings.processing.extracted_audio_format.strip(".")
        out_path = Path(self.settings.storage.output_dir) / f"{uuid.uuid4().hex}.{out_ext}"

        cmd = [
            self.settings.processing.ffmpeg_binary,
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            self.settings.processing.audio_codec,
            "-ar",
            str(self.settings.processing.audio_sample_rate),
            "-ac",
            str(self.settings.processing.audio_channels),
            str(out_path),
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"ffmpeg extract failed: {result.stderr[:500]}")

        return out_path

    async def probe_duration(self, media_path: Path) -> Optional[float]:
        if not self.ffprobe_available():
            return None

        cmd = [
            self.settings.processing.ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media_path),
        ]
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        try:
            payload = json.loads(result.stdout)
            duration = payload.get("format", {}).get("duration")
            if duration is None:
                return None
            return float(duration)
        except Exception:
            return None


class LocalTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._models: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def _get_model(self, model_id: str) -> Any:
        key = f"{model_id}:{self.settings.local.device}:{self.settings.local.compute_type}"
        async with self._lock:
            if key in self._models:
                return self._models[key]

            try:
                from faster_whisper import WhisperModel  # type: ignore
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "faster-whisper is not installed. "
                        "Install with: pip install faster-whisper ctranslate2"
                    ),
                ) from exc

            model = await asyncio.to_thread(
                WhisperModel,
                model_id,
                device=self.settings.local.device,
                compute_type=self.settings.local.compute_type,
                cpu_threads=self.settings.local.cpu_threads,
                num_workers=self.settings.local.num_workers,
                download_root=self.settings.storage.model_dir,
            )
            self._models[key] = model
            return model

    async def transcribe(self, audio_path: Path, options: Dict[str, Any]) -> Dict[str, Any]:
        model_id = str(options.get("model") or self.settings.local.model_id)
        model = await self._get_model(model_id)

        word_timestamps = bool(options.get("word_timestamps", self.settings.transcription.enable_word_timestamps))
        segment_timestamps = bool(options.get("segment_timestamps", self.settings.transcription.enable_segment_timestamps))

        kwargs = {
            "language": options.get("language") or self.settings.transcription.default_language,
            "beam_size": self.settings.local.beam_size,
            "best_of": self.settings.local.best_of,
            "patience": self.settings.local.patience,
            "temperature": options.get("temperature", self.settings.local.temperature),
            "condition_on_previous_text": self.settings.local.condition_on_previous_text,
            "initial_prompt": options.get("prompt") or self.settings.local.initial_prompt,
            "vad_filter": bool(options.get("vad_filter", self.settings.local.vad_filter)),
            "word_timestamps": word_timestamps,
            "task": "transcribe",
        }

        started = time.perf_counter()
        segments_iter, info = await asyncio.to_thread(model.transcribe, str(audio_path), **kwargs)
        segments_raw = list(segments_iter)
        process_ms = (time.perf_counter() - started) * 1000.0

        text_parts: List[str] = []
        segments: List[Dict[str, Any]] = []
        words: List[Dict[str, Any]] = []

        for idx, seg in enumerate(segments_raw):
            text_seg = (seg.text or "").strip()
            if text_seg:
                text_parts.append(text_seg)

            segment_obj: Dict[str, Any] = {
                "id": int(getattr(seg, "id", idx)),
                "start": float(seg.start),
                "end": float(seg.end),
                "text": text_seg,
                "avg_logprob": float(getattr(seg, "avg_logprob", 0.0)) if getattr(seg, "avg_logprob", None) is not None else None,
                "no_speech_prob": float(getattr(seg, "no_speech_prob", 0.0)) if getattr(seg, "no_speech_prob", None) is not None else None,
            }

            seg_words: List[Dict[str, Any]] = []
            if word_timestamps and getattr(seg, "words", None):
                for w in seg.words:
                    item = {
                        "start": float(w.start),
                        "end": float(w.end),
                        "word": str(w.word),
                        "probability": float(w.probability) if getattr(w, "probability", None) is not None else None,
                    }
                    seg_words.append(item)
                    words.append(item)

            if word_timestamps:
                segment_obj["words"] = seg_words

            segments.append(segment_obj)

        return {
            "text": " ".join(text_parts).strip(),
            "language": getattr(info, "language", None),
            "duration_seconds": float(getattr(info, "duration", 0.0)) if getattr(info, "duration", None) is not None else None,
            "segments": segments if segment_timestamps else None,
            "words": words if word_timestamps else None,
            "usage": {
                "provider": "local",
                "model": model_id,
                "audio_seconds": float(getattr(info, "duration", 0.0)) if getattr(info, "duration", None) is not None else None,
                "process_ms": round(process_ms, 2),
            },
        }


class APITranscriber:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    async def _call_openai_compatible(
        self,
        *,
        provider_name: str,
        provider: ProviderSection,
        audio_path: Path,
        options: Dict[str, Any],
        custom_auth_header: Optional[str] = None,
        custom_auth_scheme: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not provider.enabled:
            raise HTTPException(status_code=400, detail=f"provider '{provider_name}' is disabled")
        if not provider.base_url or not provider.api_key:
            raise HTTPException(status_code=500, detail=f"provider '{provider_name}' is missing base_url/api_key")

        url = join_url(provider.base_url, provider.transcriptions_path)
        model_name = str(options.get("model") or provider.model)

        data: Dict[str, Any] = {
            "model": model_name,
        }
        if options.get("language"):
            data["language"] = options["language"]
        if options.get("prompt"):
            data["prompt"] = options["prompt"]
        if options.get("response_format"):
            data["response_format"] = options["response_format"]
        if options.get("temperature") is not None:
            data["temperature"] = str(options["temperature"])

        auth_header = custom_auth_header or "Authorization"
        auth_scheme = custom_auth_scheme or "Bearer"
        if auth_scheme:
            auth_value = f"{auth_scheme} {provider.api_key}".strip()
        else:
            auth_value = provider.api_key

        headers = {
            auth_header: auth_value,
        }

        content_type = mimetypes.guess_type(str(audio_path))[0] or "application/octet-stream"
        started = time.perf_counter()
        with audio_path.open("rb") as f:
            files = {"file": (audio_path.name, f, content_type)}
            resp = await self.client.post(
                url,
                data=data,
                files=files,
                headers=headers,
                timeout=provider.timeout_sec,
            )
        process_ms = (time.perf_counter() - started) * 1000.0

        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=f"upstream transcription error: {resp.text[:600]}")

        payload: Dict[str, Any]
        ctype = resp.headers.get("content-type", "").lower()
        if "application/json" in ctype:
            payload = resp.json()
        else:
            text_payload = resp.text.strip()
            payload = {"text": text_payload}

        text = str(payload.get("text") or payload.get("transcript") or payload.get("output_text") or "").strip()
        segments = payload.get("segments") if isinstance(payload.get("segments"), list) else None
        words = payload.get("words") if isinstance(payload.get("words"), list) else None

        return {
            "text": text,
            "language": payload.get("language"),
            "duration_seconds": payload.get("duration") if isinstance(payload.get("duration"), (int, float)) else None,
            "segments": segments,
            "words": words,
            "usage": {
                "provider": provider_name,
                "model": model_name,
                "audio_seconds": payload.get("duration") if isinstance(payload.get("duration"), (int, float)) else None,
                "process_ms": round(process_ms, 2),
            },
            "metadata": {
                "upstream_raw": payload,
            },
        }

    async def transcribe(self, provider_name: str, audio_path: Path, options: Dict[str, Any]) -> Dict[str, Any]:
        if provider_name == "openai":
            return await self._call_openai_compatible(
                provider_name=provider_name,
                provider=self.settings.providers.openai,
                audio_path=audio_path,
                options=options,
            )
        if provider_name == "groq":
            return await self._call_openai_compatible(
                provider_name=provider_name,
                provider=self.settings.providers.groq,
                audio_path=audio_path,
                options=options,
            )
        if provider_name == "custom":
            return await self._call_openai_compatible(
                provider_name=provider_name,
                provider=self.settings.providers.custom,
                audio_path=audio_path,
                options=options,
                custom_auth_header=self.settings.providers.custom.auth_header,
                custom_auth_scheme=self.settings.providers.custom.auth_scheme,
            )

        raise HTTPException(status_code=400, detail=f"unsupported provider: {provider_name}")


@dataclass
class DownloadJob:
    job_id: str
    source: str
    requested_url: str
    resolved_url: str
    output_subdir: str
    output_filename: Optional[str]
    status: str = "pending"
    created_at: datetime = field(default_factory=now_utc)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    bytes_total: Optional[int] = None
    bytes_downloaded: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_dict(self) -> Dict[str, Any]:
        progress = None
        if self.bytes_total and self.bytes_total > 0:
            progress = round((self.bytes_downloaded / self.bytes_total) * 100.0, 2)
        return {
            "job_id": self.job_id,
            "status": self.status,
            "source": self.source,
            "requested_url": self.requested_url,
            "resolved_url": self.resolved_url,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "bytes_total": self.bytes_total,
            "bytes_downloaded": self.bytes_downloaded,
            "progress_percent": progress,
            "output_path": self.output_path,
            "error": self.error,
        }


class DownloadManager:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self.jobs: Dict[str, DownloadJob] = {}
        self._sem = asyncio.Semaphore(settings.downloads.max_concurrent_jobs)

    def _assert_domain_allowed(self, url: str) -> None:
        domain = (urlparse(url).hostname or "").lower()
        if not domain:
            raise HTTPException(status_code=400, detail="invalid download url")
        if self.settings.downloads.allowed_domains and domain not in self.settings.downloads.allowed_domains:
            raise HTTPException(status_code=403, detail=f"domain '{domain}' is not in DOWNLOADS_ALLOWED_DOMAINS")

    def build_hf_file_url(self, repo_id: str, filename: str, revision: str = "main", use_mirror: Optional[bool] = None) -> Dict[str, str]:
        use_mirror_final = self.settings.mirrors.prefer_mirror if use_mirror is None else use_mirror
        base = self.settings.mirrors.huggingface_mirror_base if use_mirror_final else self.settings.mirrors.huggingface_base
        source = "mirror" if use_mirror_final else "official"

        repo_clean = repo_id.strip("/")
        file_clean = filename.strip("/")
        url = join_url(base, f"{repo_clean}/resolve/{revision}/{file_clean}")
        return {"source": source, "url": url}

    async def probe_url(self, url: str) -> bool:
        try:
            resp = await self.client.get(url, timeout=15)
            return resp.status_code < 500
        except Exception:
            return False

    async def create_job(
        self,
        *,
        source: str,
        requested_url: str,
        resolved_url: str,
        output_subdir: str,
        output_filename: Optional[str],
    ) -> DownloadJob:
        if not self.settings.downloads.enabled:
            raise HTTPException(status_code=403, detail="downloads are disabled")

        self._assert_domain_allowed(resolved_url)

        job = DownloadJob(
            job_id=uuid.uuid4().hex,
            source=source,
            requested_url=requested_url,
            resolved_url=resolved_url,
            output_subdir=sanitize_name(output_subdir),
            output_filename=sanitize_name(output_filename) if output_filename else None,
        )
        self.jobs[job.job_id] = job
        asyncio.create_task(self._run_job(job))
        return job

    async def _run_job(self, job: DownloadJob) -> None:
        async with self._sem:
            if job.cancel_event.is_set():
                job.status = "cancelled"
                job.completed_at = now_utc()
                return

            job.status = "running"
            job.started_at = now_utc()

            output_dir = Path(self.settings.storage.model_dir) / job.output_subdir
            output_dir.mkdir(parents=True, exist_ok=True)

            name_from_url = sanitize_name(Path(urlparse(job.resolved_url).path).name)
            final_name = job.output_filename or name_from_url or f"{job.job_id}.bin"
            final_path = output_dir / final_name
            part_path = final_path.with_suffix(final_path.suffix + ".part")

            try:
                mode = "ab" if self.settings.downloads.allow_resume and part_path.exists() else "wb"
                resumed = part_path.stat().st_size if mode == "ab" and part_path.exists() else 0

                headers = {}
                if resumed > 0 and self.settings.downloads.allow_resume:
                    headers["Range"] = f"bytes={resumed}-"

                async with self.client.stream("GET", job.resolved_url, headers=headers, timeout=self.settings.downloads.timeout_sec, follow_redirects=True) as resp:
                    if resp.status_code >= 400:
                        raise RuntimeError(f"download failed with status={resp.status_code}")

                    content_length = resp.headers.get("content-length")
                    if content_length and str(content_length).isdigit():
                        total = int(content_length)
                        if resumed > 0 and resp.status_code == 206:
                            total += resumed
                        job.bytes_total = total

                    bytes_done = resumed
                    with part_path.open(mode) as f:
                        async for chunk in resp.aiter_bytes(chunk_size=self.settings.downloads.chunk_size):
                            if job.cancel_event.is_set():
                                job.status = "cancelled"
                                job.completed_at = now_utc()
                                return
                            if not chunk:
                                continue
                            f.write(chunk)
                            bytes_done += len(chunk)
                            job.bytes_downloaded = bytes_done

                os.replace(part_path, final_path)
                job.output_path = str(final_path)
                job.status = "completed"
                job.completed_at = now_utc()
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = now_utc()

    def get(self, job_id: str) -> DownloadJob:
        job = self.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    def list(self) -> List[DownloadJob]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel(self, job_id: str) -> DownloadJob:
        job = self.get(job_id)
        if job.status in {"completed", "failed", "cancelled"}:
            return job
        job.cancel_event.set()
        return job


class TranscriptionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.app.request_timeout_sec)
        self.media = MediaService(settings)
        self.local = LocalTranscriber(settings)
        self.api = APITranscriber(settings, self.client)
        self.downloads = DownloadManager(settings, self.client)

    async def close(self) -> None:
        await self.client.aclose()

    async def transcribe_upload(self, upload: UploadFile, options: Dict[str, Any]) -> Dict[str, Any]:
        provider = str(options.get("provider") or self.settings.transcription.default_provider)

        source_name = upload.filename or "uploaded-file"
        source_content_type = upload.content_type

        raw_path = await self.media.save_upload(upload)
        prepared_path: Optional[Path] = None

        try:
            if not (is_video_file(source_name, source_content_type) or is_audio_file(source_name, source_content_type)):
                raise HTTPException(status_code=415, detail="unsupported media type, upload an audio/video file")

            prepared_path = await self.media.extract_audio(raw_path, source_name, source_content_type)
            duration = await self.media.probe_duration(prepared_path)

            if provider == "local":
                out = await self.local.transcribe(prepared_path, options)
            else:
                out = await self.api.transcribe(provider, prepared_path, options)

            meta = out.setdefault("metadata", {})
            meta.update(
                {
                    "input_filename": source_name,
                    "input_content_type": source_content_type,
                    "provider": provider,
                    "audio_prepared_path": str(prepared_path),
                    "duration_probe_seconds": duration,
                    "was_video": is_video_file(source_name, source_content_type),
                }
            )
            return out
        finally:
            if self.settings.storage.cleanup_temp_after_request:
                for p in {raw_path, prepared_path}:
                    if p and p.exists():
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
            else:
                if prepared_path and raw_path != prepared_path and not self.settings.processing.preserve_original_upload:
                    raw_path.unlink(missing_ok=True)


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.transcription = TranscriptionService(settings)

    async def close(self) -> None:
        await self.transcription.close()
