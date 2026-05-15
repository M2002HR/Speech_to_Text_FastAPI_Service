from __future__ import annotations

import asyncio
import ctypes
import difflib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
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

WHISPER_VARIANT_METADATA: Dict[str, Dict[str, Any]] = {
    "tiny": {
        "variant": "tiny",
        "parameters_million": 39,
        "estimated_model_bin_mb": 75,
        "estimated_vram_gb": 1.0,
        "context_tokens": 448,
        "multilingual": True,
    },
    "base": {
        "variant": "base",
        "parameters_million": 74,
        "estimated_model_bin_mb": 145,
        "estimated_vram_gb": 1.0,
        "context_tokens": 448,
        "multilingual": True,
    },
    "small": {
        "variant": "small",
        "parameters_million": 244,
        "estimated_model_bin_mb": 465,
        "estimated_vram_gb": 2.0,
        "context_tokens": 448,
        "multilingual": True,
    },
    "medium": {
        "variant": "medium",
        "parameters_million": 769,
        "estimated_model_bin_mb": 1460,
        "estimated_vram_gb": 5.0,
        "context_tokens": 448,
        "multilingual": True,
    },
    "large": {
        "variant": "large",
        "parameters_million": 1550,
        "estimated_model_bin_mb": 2950,
        "estimated_vram_gb": 10.0,
        "context_tokens": 448,
        "multilingual": True,
    },
    "large-v3": {
        "variant": "large-v3",
        "parameters_million": 1550,
        "estimated_model_bin_mb": 3000,
        "estimated_vram_gb": 10.0,
        "context_tokens": 448,
        "multilingual": True,
    },
}

VARIANT_TO_LOCAL_DIR_ALIASES: Dict[str, List[str]] = {
    "tiny": ["faster-whisper-tiny"],
    "base": ["faster-whisper-base"],
    "small": ["faster-whisper-small"],
    "medium": ["faster-whisper-medium"],
    "large-v3": ["faster-whisper-large-v3", "openai-whisper-large-v3"],
    "large": ["faster-whisper-large-v3", "openai-whisper-large-v3"],
}

MODEL_PRESETS = [
    {
        "name": "faster-whisper-tiny",
        "repo_id": "Systran/faster-whisper-tiny",
        "notes": "Very fast, lower accuracy",
        **WHISPER_VARIANT_METADATA["tiny"],
    },
    {
        "name": "faster-whisper-small",
        "repo_id": "Systran/faster-whisper-small",
        "notes": "Balanced speed/quality",
        **WHISPER_VARIANT_METADATA["small"],
    },
    {
        "name": "faster-whisper-medium",
        "repo_id": "Systran/faster-whisper-medium",
        "notes": "Higher accuracy, heavier",
        **WHISPER_VARIANT_METADATA["medium"],
    },
    {
        "name": "faster-whisper-large-v3",
        "repo_id": "Systran/faster-whisper-large-v3",
        "notes": "Best quality among common Whisper variants",
        **WHISPER_VARIANT_METADATA["large-v3"],
    },
    {
        "name": "openai-whisper-large-v3",
        "repo_id": "openai/whisper-large-v3",
        "notes": "Official whisper-large-v3 repo",
        **WHISPER_VARIANT_METADATA["large-v3"],
    },
]

FASTER_WHISPER_KNOWN_MODEL_IDS = {
    "tiny.en",
    "tiny",
    "base.en",
    "base",
    "small.en",
    "small",
    "medium.en",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "large",
    "distil-large-v2",
    "distil-medium.en",
    "distil-small.en",
    "distil-large-v3",
    "distil-large-v3.5",
    "large-v3-turbo",
    "turbo",
}


def normalize_model_token(value: str) -> str:
    return str(value or "").strip().lower().replace("\\", "/").strip("/")


def build_faster_whisper_model_aliases() -> Dict[str, str]:
    aliases: Dict[str, str] = {}

    for model_id in FASTER_WHISPER_KNOWN_MODEL_IDS:
        aliases[normalize_model_token(model_id)] = model_id
        aliases[normalize_model_token(f"faster-whisper-{model_id}")] = model_id
        aliases[normalize_model_token(f"systran/faster-whisper-{model_id}")] = model_id
        aliases[normalize_model_token(f"systran--faster-whisper-{model_id}")] = model_id

    for model_id in ["distil-large-v2", "distil-medium.en", "distil-small.en", "distil-large-v3", "distil-large-v3.5"]:
        suffix = model_id.removeprefix("distil-")
        aliases[normalize_model_token(f"systran/faster-distil-whisper-{suffix}")] = model_id
        aliases[normalize_model_token(f"systran--faster-distil-whisper-{suffix}")] = model_id
        aliases[normalize_model_token(f"distil-whisper/{model_id}")] = model_id

    aliases[normalize_model_token("openai/whisper-large-v3")] = "large-v3"
    aliases[normalize_model_token("openai-whisper-large-v3")] = "large-v3"
    aliases[normalize_model_token("openai/whisper-large-v3-turbo")] = "large-v3-turbo"
    aliases[normalize_model_token("openai-whisper-large-v3-turbo")] = "large-v3-turbo"
    aliases[normalize_model_token("faster-whisper-large-v3-turbo")] = "large-v3-turbo"

    return aliases


FASTER_WHISPER_MODEL_ALIASES = build_faster_whisper_model_aliases()


def canonicalize_faster_whisper_model_id(model_id: str) -> Optional[str]:
    normalized = normalize_model_token(model_id)
    if not normalized:
        return None
    return FASTER_WHISPER_MODEL_ALIASES.get(normalized)


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


def normalize_proxy_env() -> None:
    for key in ["ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
        value = os.getenv(key)
        if not value:
            continue
        if value.startswith("socks://"):
            os.environ[key] = "socks5://" + value[len("socks://"):]


def has_cuda_runtime() -> bool:
    for lib_name in ["libcublas.so.12", "libcublas.so"]:
        try:
            ctypes.CDLL(lib_name)
            return True
        except OSError:
            continue
    return preload_cuda_libraries()


def configure_cuda_library_env() -> None:
    candidates = [
        Path("/usr/local/lib/ollama/cuda_v12"),
        Path("/usr/local/lib/ollama/mlx_cuda_v13"),
        Path("/usr/local/cuda/lib64"),
        Path("/usr/local/cuda-12/lib64"),
    ]

    existing = [str(p) for p in candidates if p.exists()]
    if not existing:
        return

    current = os.getenv("LD_LIBRARY_PATH", "")
    current_parts = [x for x in current.split(":") if x]
    merged = []
    for item in existing + current_parts:
        if item not in merged:
            merged.append(item)
    os.environ["LD_LIBRARY_PATH"] = ":".join(merged)


def preload_cuda_libraries() -> bool:
    lib_dirs = [
        Path("/usr/local/lib/ollama/cuda_v12"),
        Path("/usr/local/lib/ollama/mlx_cuda_v13"),
        Path("/usr/local/cuda/lib64"),
        Path("/usr/local/cuda-12/lib64"),
    ]
    libs = ["libcudart.so.12", "libcublasLt.so.12", "libcublas.so.12"]
    loaded_any = False

    for lib_dir in lib_dirs:
        if not lib_dir.exists():
            continue
        for lib_name in libs:
            full_path = lib_dir / lib_name
            if not full_path.exists():
                continue
            try:
                ctypes.CDLL(str(full_path), mode=ctypes.RTLD_GLOBAL)
                loaded_any = True
            except OSError:
                continue

    if loaded_any:
        try:
            ctypes.CDLL("libcublas.so.12")
            return True
        except OSError:
            return False
    return False


def detect_whisper_variant(text: str) -> Optional[str]:
    normalized = normalize_model_token(text)
    canonical = canonicalize_faster_whisper_model_id(normalized)

    if canonical in {"tiny", "tiny.en"}:
        return "tiny"
    if canonical in {"base", "base.en"}:
        return "base"
    if canonical in {"small", "small.en", "distil-small.en"}:
        return "small"
    if canonical in {"medium", "medium.en", "distil-medium.en"}:
        return "medium"
    if canonical in {"large-v3", "large-v3-turbo", "distil-large-v3", "distil-large-v3.5", "turbo"}:
        return "large-v3"
    if canonical in {"large-v2", "distil-large-v2"}:
        return "large"
    if canonical in {"large-v1", "large"}:
        return "large"

    if "large-v3" in normalized or "turbo" in normalized:
        return "large-v3"
    for item in ["large-v2", "large-v1", "large", "medium", "small", "base", "tiny"]:
        if item in normalized:
            if item.startswith("large-v"):
                return "large"
            return item
    return None


def infer_variant_from_config(config_payload: Dict[str, Any]) -> Optional[str]:
    try:
        layers = int(config_payload.get("num_encoder_layers", -1))
        hidden = int(config_payload.get("d_model", -1))
    except Exception:
        return None

    signature = (layers, hidden)
    mapping = {
        (4, 384): "tiny",
        (6, 512): "base",
        (12, 768): "small",
        (24, 1024): "medium",
        (32, 1280): "large",
    }
    return mapping.get(signature)


def is_local_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if not (path / "config.json").exists() or not (path / "model.bin").exists():
        return False
    has_tokenizer = (path / "tokenizer.json").exists()
    has_vocab = (path / "vocabulary.json").exists() or (path / "vocabulary.txt").exists()
    return has_tokenizer and has_vocab


def fallback_faster_whisper_files(repo_id: str) -> List[str]:
    repo = repo_id.lower()
    base = ["config.json", "model.bin", "tokenizer.json"]
    if "systran/faster-whisper" in repo:
        return base + ["vocabulary.txt"]
    return base + ["vocabulary.json"]


_LOOP_TOKEN_STRIP_CHARS = "\"'`.,!?;:()[]{}<>«»“”‘’،؛…ـ"
_MIN_SINGLE_TOKEN_REPEAT = 20
_MIN_PHRASE_REPEAT = 8
_MAX_PHRASE_N = 4
_MAX_TAIL_TOKENS = 320


def _normalize_loop_token(token: str) -> str:
    cleaned = token.strip(_LOOP_TOKEN_STRIP_CHARS)
    cleaned = re.sub(r"[\u200c\u200d\u200e\u200f]", "", cleaned)
    return cleaned.lower().strip()


def _detect_tail_loop(text: str) -> Optional[Dict[str, Any]]:
    tokens = [t for t in str(text or "").split() if t.strip()]
    if len(tokens) < 24:
        return None

    norm_all = [_normalize_loop_token(t) for t in tokens]
    tail_start = max(0, len(tokens) - _MAX_TAIL_TOKENS)
    tail_tokens = tokens[tail_start:]
    norm = norm_all[tail_start:]

    best: Optional[Dict[str, Any]] = None

    last = norm_all[-1] if norm_all else ""
    if last:
        run = 1
        idx = len(norm_all) - 2
        while idx >= 0 and norm_all[idx] == last:
            run += 1
            idx -= 1
        if run >= _MIN_SINGLE_TOKEN_REPEAT:
            best = {
                "kind": "single_token",
                "pattern_size": 1,
                "repeats": run,
                "remove_tokens": run - 1,
                "pattern": [last],
            }

    max_phrase_n = min(_MAX_PHRASE_N, len(norm) // 2)
    for n in range(2, max_phrase_n + 1):
        pattern = norm[-n:]
        if any(not item for item in pattern):
            continue
        repeats = 1
        idx = len(norm) - (2 * n)
        while idx >= 0 and norm[idx: idx + n] == pattern:
            repeats += 1
            idx -= n
        if repeats >= _MIN_PHRASE_REPEAT:
            candidate = {
                "kind": "phrase",
                "pattern_size": n,
                "repeats": repeats,
                "remove_tokens": (repeats - 1) * n,
                "pattern": pattern,
            }
            if best is None or candidate["remove_tokens"] > best["remove_tokens"]:
                best = candidate

    if not best:
        return None

    best["tail_tokens"] = len(tail_tokens)
    best["tail_start_index"] = tail_start
    best["total_tokens"] = len(tokens)
    return best


def _trim_detected_tail_loop(text: str, loop_info: Dict[str, Any]) -> str:
    tokens = [t for t in str(text or "").split() if t.strip()]
    remove_count = int(loop_info.get("remove_tokens") or 0)
    if remove_count <= 0 or remove_count >= len(tokens):
        return text.strip()
    trimmed = " ".join(tokens[:-remove_count]).strip()
    return trimmed or text.strip()


def _normalize_merge_token(token: str) -> str:
    return _normalize_loop_token(token)


def _split_words(text: str) -> List[str]:
    return [w for w in str(text or "").split() if w.strip()]


def _word_overlap_suffix_prefix(left: List[str], right: List[str], max_words: int) -> int:
    if not left or not right:
        return 0
    max_k = min(len(left), len(right), max(1, max_words))
    for k in range(max_k, 0, -1):
        if left[-k:] == right[:k]:
            return k
    return 0


def _text_similarity(a: str, b: str) -> float:
    a_norm = " ".join(_normalize_merge_token(x) for x in _split_words(a) if _normalize_merge_token(x))
    b_norm = " ".join(_normalize_merge_token(x) for x in _split_words(b) if _normalize_merge_token(x))
    if not a_norm or not b_norm:
        return 0.0
    return float(difflib.SequenceMatcher(None, a_norm, b_norm).ratio())


def _build_overlapping_windows(
    duration_seconds: float,
    window_minutes: float,
    overlap_minutes: float,
) -> List[Dict[str, float]]:
    duration = max(0.0, float(duration_seconds))
    window = max(1.0, float(window_minutes) * 60.0)
    overlap = max(0.0, float(overlap_minutes) * 60.0)
    if overlap >= window:
        overlap = max(0.0, window - 1.0)
    step = max(1.0, window - overlap)

    windows: List[Dict[str, float]] = []
    start = 0.0
    idx = 0
    while start < duration:
        end = min(duration, start + window)
        windows.append({"index": idx, "start": round(start, 3), "end": round(end, 3)})
        idx += 1
        if end >= duration:
            break
        start += step
    return windows


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

    async def extract_audio_window(self, input_path: Path, start_sec: float, end_sec: float) -> Path:
        if not self.ffmpeg_available():
            raise HTTPException(
                status_code=500,
                detail=f"ffmpeg binary not found: {self.settings.processing.ffmpeg_binary}",
            )

        start = max(0.0, float(start_sec))
        end = max(start, float(end_sec))
        duration = max(0.01, end - start)
        out_ext = self.settings.processing.extracted_audio_format.strip(".")
        out_path = Path(self.settings.storage.output_dir) / f"{uuid.uuid4().hex}.{out_ext}"

        cmd = [
            self.settings.processing.ffmpeg_binary,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(input_path),
            "-t",
            f"{duration:.3f}",
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
            raise HTTPException(status_code=500, detail=f"ffmpeg chunk extract failed: {result.stderr[:500]}")

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
        normalize_proxy_env()
        configure_cuda_library_env()
        self.settings = settings
        self._models: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    def _resolve_model_id(self, raw_model_id: str) -> str:
        model_id = raw_model_id.strip()
        if not model_id:
            return self.settings.local.model_id
        canonical_model_id = canonicalize_faster_whisper_model_id(model_id)
        normalized_model_id = normalize_model_token(model_id)

        raw_path = Path(model_id)
        if raw_path.is_absolute() and is_local_model_dir(raw_path):
            return str(raw_path)

        model_root = Path(self.settings.storage.model_dir)
        candidate_dirs = [
            model_root / model_id,
            model_root / sanitize_name(model_id),
            model_root / model_id.replace("/", "--"),
            model_root / sanitize_name(model_id.replace("/", "--")),
        ]
        variant = detect_whisper_variant(canonical_model_id or model_id)
        if variant:
            for alias in VARIANT_TO_LOCAL_DIR_ALIASES.get(variant, []):
                candidate_dirs.append(model_root / alias)
                candidate_dirs.append(model_root / sanitize_name(alias))
                candidate_dirs.append(model_root / alias.replace("/", "--"))

        preset = next(
            (
                x
                for x in MODEL_PRESETS
                if x["name"] == model_id
                or x["repo_id"] == model_id
                or normalize_model_token(x["name"]) == normalized_model_id
                or normalize_model_token(x["repo_id"]) == normalized_model_id
            ),
            None,
        )
        if preset:
            candidate_dirs.append(model_root / preset["name"])
            candidate_dirs.append(model_root / preset["repo_id"].replace("/", "--"))
            preset_variant = detect_whisper_variant(preset["name"])
            if preset_variant:
                for alias in VARIANT_TO_LOCAL_DIR_ALIASES.get(preset_variant, []):
                    candidate_dirs.append(model_root / alias)
                    candidate_dirs.append(model_root / sanitize_name(alias))
                    candidate_dirs.append(model_root / alias.replace("/", "--"))

        seen_paths: set[str] = set()
        for path in candidate_dirs:
            key = str(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            if is_local_model_dir(path):
                return str(path)

        if canonical_model_id:
            return canonical_model_id

        if model_id in FASTER_WHISPER_KNOWN_MODEL_IDS:
            return model_id

        if variant:
            return variant

        return model_id

    async def _get_model(self, model_id: str) -> Any:
        resolved_model_id = self._resolve_model_id(model_id)
        key = f"{resolved_model_id}:{self.settings.local.device}:{self.settings.local.compute_type}"
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

            attempts: List[tuple[str, str]] = []
            wants_gpu = self.settings.local.device in {"auto", "cuda"}
            cuda_ok = has_cuda_runtime()

            if wants_gpu and not cuda_ok:
                attempts.extend([("cpu", "int8"), ("cpu", "int8_float32")])
            else:
                attempts.append((self.settings.local.device, self.settings.local.compute_type))
                if wants_gpu:
                    attempts.append(("cpu", "int8"))
                    attempts.append(("cpu", "int8_float32"))

            seen: set[tuple[str, str]] = set()
            errors: List[str] = []
            for device, compute_type in attempts:
                combo = (device, compute_type)
                if combo in seen:
                    continue
                seen.add(combo)
                try:
                    model = await asyncio.to_thread(
                        WhisperModel,
                        resolved_model_id,
                        device=device,
                        compute_type=compute_type,
                        cpu_threads=self.settings.local.cpu_threads,
                        num_workers=self.settings.local.num_workers,
                        download_root=self.settings.storage.model_dir,
                    )
                    self._models[key] = model
                    return model
                except Exception as exc:  # pragma: no cover - runtime dependent
                    errors.append(f"{device}/{compute_type}: {exc}")
                    continue

            raise HTTPException(status_code=500, detail=f"failed to load local model '{resolved_model_id}': {' | '.join(errors)}")

    def _consume_segments_iter(
        self,
        segments_iter: Any,
        duration_for_progress: Optional[float],
        progress_cb: Optional[Callable[[float], None]],
    ) -> List[Any]:
        segments_raw: List[Any] = []
        for seg in segments_iter:
            segments_raw.append(seg)
            if progress_cb and duration_for_progress and duration_for_progress > 0:
                try:
                    pct = max(0.0, min(99.5, (float(seg.end) / duration_for_progress) * 100.0))
                    progress_cb(round(pct, 2))
                except Exception:
                    pass
        return segments_raw

    async def transcribe(
        self,
        audio_path: Path,
        options: Dict[str, Any],
        duration_hint: Optional[float] = None,
        progress_cb: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        requested_model_id = str(options.get("model") or self.settings.local.model_id)
        resolved_model_id = self._resolve_model_id(requested_model_id)
        model = await self._get_model(requested_model_id)

        word_ts_raw = options.get("word_timestamps")
        seg_ts_raw = options.get("segment_timestamps")
        vad_raw = options.get("vad_filter")
        temperature_raw = options.get("temperature")
        beam_size_raw = options.get("beam_size")
        best_of_raw = options.get("best_of")
        patience_raw = options.get("patience")
        condition_prev_raw = options.get("condition_on_previous_text")
        initial_prompt_raw = options.get("initial_prompt")
        repetition_penalty_raw = options.get("repetition_penalty")
        no_repeat_ngram_size_raw = options.get("no_repeat_ngram_size")
        compression_ratio_threshold_raw = options.get("compression_ratio_threshold")
        log_prob_threshold_raw = options.get("log_prob_threshold")
        no_speech_threshold_raw = options.get("no_speech_threshold")
        prompt_reset_on_temperature_raw = options.get("prompt_reset_on_temperature")
        hallucination_silence_threshold_raw = options.get("hallucination_silence_threshold")
        max_new_tokens_raw = options.get("max_new_tokens")
        vad_threshold_raw = options.get("vad_threshold")
        vad_neg_threshold_raw = options.get("vad_neg_threshold")
        vad_min_speech_duration_ms_raw = options.get("vad_min_speech_duration_ms")
        vad_min_silence_duration_ms_raw = options.get("vad_min_silence_duration_ms")
        vad_speech_pad_ms_raw = options.get("vad_speech_pad_ms")

        word_timestamps = self.settings.transcription.enable_word_timestamps if word_ts_raw is None else bool(word_ts_raw)
        segment_timestamps = self.settings.transcription.enable_segment_timestamps if seg_ts_raw is None else bool(seg_ts_raw)
        vad_filter = self.settings.local.vad_filter if vad_raw is None else bool(vad_raw)
        temperature = self.settings.local.temperature if temperature_raw is None else float(temperature_raw)
        beam_size = self.settings.local.beam_size if beam_size_raw is None else int(beam_size_raw)
        best_of = self.settings.local.best_of if best_of_raw is None else int(best_of_raw)
        patience = self.settings.local.patience if patience_raw is None else float(patience_raw)
        condition_on_previous_text = (
            self.settings.local.condition_on_previous_text
            if condition_prev_raw is None
            else bool(condition_prev_raw)
        )
        repetition_penalty = (
            self.settings.local.repetition_penalty
            if repetition_penalty_raw is None
            else float(repetition_penalty_raw)
        )
        no_repeat_ngram_size = (
            self.settings.local.no_repeat_ngram_size
            if no_repeat_ngram_size_raw is None
            else int(no_repeat_ngram_size_raw)
        )
        compression_ratio_threshold = (
            self.settings.local.compression_ratio_threshold
            if compression_ratio_threshold_raw is None
            else float(compression_ratio_threshold_raw)
        )
        log_prob_threshold = (
            self.settings.local.log_prob_threshold
            if log_prob_threshold_raw is None
            else float(log_prob_threshold_raw)
        )
        no_speech_threshold = (
            self.settings.local.no_speech_threshold
            if no_speech_threshold_raw is None
            else float(no_speech_threshold_raw)
        )
        prompt_reset_on_temperature = (
            self.settings.local.prompt_reset_on_temperature
            if prompt_reset_on_temperature_raw is None
            else float(prompt_reset_on_temperature_raw)
        )
        hallucination_silence_threshold = (
            self.settings.local.hallucination_silence_threshold
            if hallucination_silence_threshold_raw is None
            else float(hallucination_silence_threshold_raw)
        )
        max_new_tokens = (
            self.settings.local.max_new_tokens
            if max_new_tokens_raw is None
            else int(max_new_tokens_raw)
        )
        initial_prompt = (
            options.get("prompt")
            if options.get("prompt") is not None
            else (self.settings.local.initial_prompt if initial_prompt_raw is None else str(initial_prompt_raw))
        )

        vad_parameters: Dict[str, Any] = {}
        vad_threshold = self.settings.local.vad_threshold if vad_threshold_raw is None else float(vad_threshold_raw)
        vad_neg_threshold = self.settings.local.vad_neg_threshold if vad_neg_threshold_raw is None else float(vad_neg_threshold_raw)
        vad_min_speech_duration_ms = (
            self.settings.local.vad_min_speech_duration_ms
            if vad_min_speech_duration_ms_raw is None
            else int(vad_min_speech_duration_ms_raw)
        )
        vad_min_silence_duration_ms = (
            self.settings.local.vad_min_silence_duration_ms
            if vad_min_silence_duration_ms_raw is None
            else int(vad_min_silence_duration_ms_raw)
        )
        vad_speech_pad_ms = (
            self.settings.local.vad_speech_pad_ms
            if vad_speech_pad_ms_raw is None
            else int(vad_speech_pad_ms_raw)
        )
        if vad_threshold is not None:
            vad_parameters["threshold"] = float(vad_threshold)
        if vad_neg_threshold is not None:
            vad_parameters["neg_threshold"] = float(vad_neg_threshold)
        if vad_min_speech_duration_ms is not None:
            vad_parameters["min_speech_duration_ms"] = int(vad_min_speech_duration_ms)
        if vad_min_silence_duration_ms is not None:
            vad_parameters["min_silence_duration_ms"] = int(vad_min_silence_duration_ms)
        if vad_speech_pad_ms is not None:
            vad_parameters["speech_pad_ms"] = int(vad_speech_pad_ms)

        kwargs = {
            "language": options.get("language") or self.settings.transcription.default_language,
            "beam_size": beam_size,
            "best_of": best_of,
            "patience": patience,
            "temperature": temperature,
            "condition_on_previous_text": condition_on_previous_text,
            "repetition_penalty": repetition_penalty,
            "no_repeat_ngram_size": no_repeat_ngram_size,
            "compression_ratio_threshold": compression_ratio_threshold,
            "log_prob_threshold": log_prob_threshold,
            "no_speech_threshold": no_speech_threshold,
            "prompt_reset_on_temperature": prompt_reset_on_temperature,
            "initial_prompt": initial_prompt,
            "vad_filter": vad_filter,
            "word_timestamps": word_timestamps,
            "task": "transcribe",
        }
        if max_new_tokens is not None and max_new_tokens > 0:
            kwargs["max_new_tokens"] = max_new_tokens
        if word_timestamps and hallucination_silence_threshold is not None:
            kwargs["hallucination_silence_threshold"] = hallucination_silence_threshold
        if vad_filter and vad_parameters:
            kwargs["vad_parameters"] = vad_parameters

        async def _decode_once(decode_kwargs: Dict[str, Any]) -> Dict[str, Any]:
            started = time.perf_counter()
            segments_iter, info_obj = await asyncio.to_thread(model.transcribe, str(audio_path), **decode_kwargs)
            info_duration = (
                float(getattr(info_obj, "duration", 0.0))
                if getattr(info_obj, "duration", None) is not None
                else None
            )
            duration_for_progress = info_duration if info_duration and info_duration > 0 else duration_hint
            segments_raw = await asyncio.to_thread(
                self._consume_segments_iter,
                segments_iter,
                duration_for_progress,
                progress_cb,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0

            text_parts_local: List[str] = []
            segments_local: List[Dict[str, Any]] = []
            words_local: List[Dict[str, Any]] = []

            for idx, seg in enumerate(segments_raw):
                text_seg = (seg.text or "").strip()
                if text_seg:
                    text_parts_local.append(text_seg)

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
                        words_local.append(item)

                if word_timestamps:
                    segment_obj["words"] = seg_words

                segments_local.append(segment_obj)

            return {
                "text": " ".join(text_parts_local).strip(),
                "language": getattr(info_obj, "language", None),
                "duration_seconds": info_duration,
                "segments": segments_local if segment_timestamps else None,
                "words": words_local if word_timestamps else None,
                "process_ms": elapsed_ms,
            }

        primary_output = await _decode_once(kwargs)
        selected_output = primary_output
        loop_before = _detect_tail_loop(primary_output["text"])
        retry_used = False
        retry_options: Optional[Dict[str, Any]] = None
        loop_after = loop_before

        if loop_before:
            retry_options = dict(kwargs)
            retry_options["condition_on_previous_text"] = False
            retry_options["repetition_penalty"] = max(1.05, float(retry_options.get("repetition_penalty") or 1.0))
            retry_options["no_repeat_ngram_size"] = max(3, int(retry_options.get("no_repeat_ngram_size") or 0))
            retry_options.setdefault("max_new_tokens", 448)

            current_temperature = retry_options.get("temperature")
            if isinstance(current_temperature, (int, float)) and float(current_temperature) == 0.0:
                retry_options["temperature"] = [0.0, 0.2, 0.4, 0.6]

            if word_timestamps and retry_options.get("hallucination_silence_threshold") is None:
                retry_options["hallucination_silence_threshold"] = 1.5

            try:
                retry_output = await _decode_once(retry_options)
                retry_used = True
                retry_loop = _detect_tail_loop(retry_output["text"])

                if retry_loop is None or retry_loop.get("remove_tokens", 0) < loop_before.get("remove_tokens", 0):
                    selected_output = retry_output
                    loop_after = retry_loop
                else:
                    loop_after = loop_before
            except Exception:
                retry_used = False
                loop_after = loop_before

        tail_trim_applied = False
        if loop_after:
            trimmed_text = _trim_detected_tail_loop(selected_output["text"], loop_after)
            if trimmed_text and trimmed_text != selected_output["text"]:
                selected_output["text"] = trimmed_text
                tail_trim_applied = True

        return {
            "text": selected_output["text"],
            "language": selected_output["language"],
            "duration_seconds": selected_output["duration_seconds"],
            "segments": selected_output["segments"],
            "words": selected_output["words"],
            "usage": {
                "provider": "local",
                "model": resolved_model_id,
                "audio_seconds": selected_output["duration_seconds"],
                "process_ms": round(float(selected_output["process_ms"]), 2),
            },
            "metadata": {
                "requested_model": requested_model_id,
                "resolved_model": resolved_model_id,
                "execution_device": getattr(getattr(model, "model", None), "device", None),
                "local_decode_options": {
                    "beam_size": beam_size,
                    "best_of": best_of,
                    "patience": patience,
                    "temperature": temperature,
                    "condition_on_previous_text": condition_on_previous_text,
                    "repetition_penalty": repetition_penalty,
                    "no_repeat_ngram_size": no_repeat_ngram_size,
                    "compression_ratio_threshold": compression_ratio_threshold,
                    "log_prob_threshold": log_prob_threshold,
                    "no_speech_threshold": no_speech_threshold,
                    "prompt_reset_on_temperature": prompt_reset_on_temperature,
                    "initial_prompt": initial_prompt,
                    "vad_filter": vad_filter,
                    "vad_parameters": vad_parameters or None,
                    "hallucination_silence_threshold": (
                        hallucination_silence_threshold if word_timestamps else None
                    ),
                    "max_new_tokens": max_new_tokens,
                },
                "tail_loop_guard": {
                    "detected_before_retry": loop_before,
                    "retry_used": retry_used,
                    "retry_decode_options": retry_options,
                    "detected_after_retry": loop_after,
                    "tail_trim_applied": tail_trim_applied,
                },
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
class TranscriptionJob:
    job_id: str
    provider: str
    model: str
    source_filename: str
    source_content_type: Optional[str]
    options: Dict[str, Any]
    raw_path: Path
    status: str = "pending"
    created_at: datetime = field(default_factory=now_utc)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float = 0.0
    stage: str = "queued"
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "source_filename": self.source_filename,
            "source_content_type": self.source_content_type,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_percent": round(self.progress_percent, 2),
            "stage": self.stage,
            "error": self.error,
            "result": self.result,
        }


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

    def build_hf_file_url(self, repo_id: str, filename: str, revision: str = "main") -> Dict[str, str]:
        base = self.settings.mirrors.huggingface_base
        repo_clean = repo_id.strip("/")
        file_clean = filename.strip("/")
        url = join_url(base, f"{repo_clean}/resolve/{revision}/{file_clean}")
        return {"source": "official", "url": url}

    async def probe_url(self, url: str) -> bool:
        try:
            resp = await self.client.get(url, timeout=15)
            return resp.status_code < 500
        except Exception:
            return False

    async def _url_exists(self, url: str) -> Optional[bool]:
        try:
            head = await self.client.head(url, follow_redirects=True, timeout=20)
            if head.status_code < 400:
                return True
            if head.status_code in {404, 410}:
                return False
        except Exception:
            return None

        try:
            headers = {"Range": "bytes=0-0"}
            async with self.client.stream("GET", url, headers=headers, follow_redirects=True, timeout=20) as resp:
                if resp.status_code < 400:
                    return True
                if resp.status_code in {404, 410}:
                    return False
                return None
        except Exception:
            return None

    async def resolve_hf_file_url(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str = "main",
    ) -> Dict[str, str]:
        primary = self.build_hf_file_url(repo_id=repo_id, filename=filename, revision=revision)
        self._assert_domain_allowed(primary["url"])
        return primary

    async def fetch_remote_repo_files(
        self,
        *,
        repo_id: str,
        revision: str = "main",
    ) -> List[Dict[str, Any]]:
        endpoint = join_url(self.settings.mirrors.huggingface_base, f"/api/models/{repo_id}/revision/{revision}")
        try:
            resp = await self.client.get(endpoint, params={"blobs": "true"}, timeout=60)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"unable to reach model metadata API at {self.settings.mirrors.huggingface_base}. "
                    f"network/connectivity error: {exc.__class__.__name__}"
                ),
            ) from exc
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=f"failed to fetch model files: {resp.text[:300]}")

        payload = resp.json()
        siblings = payload.get("siblings") or []
        items: List[Dict[str, Any]] = []
        for raw in siblings:
            path = str(raw.get("rfilename") or "").strip()
            if not path:
                continue
            lfs_meta = raw.get("lfs") if isinstance(raw.get("lfs"), dict) else {}
            items.append(
                {
                    "path": path,
                    "size_bytes": raw.get("size") if isinstance(raw.get("size"), int) else None,
                    "lfs_size_bytes": lfs_meta.get("size") if isinstance(lfs_meta.get("size"), int) else None,
                }
            )
        return items

    async def search_remote_model_repos(self, *, query: str, limit: int = 30) -> List[Dict[str, Any]]:
        endpoint = join_url(self.settings.mirrors.huggingface_base, "/api/models")
        try:
            resp = await self.client.get(
                endpoint,
                params={
                    "search": query,
                    "limit": max(1, min(limit, 100)),
                    "full": "false",
                },
                timeout=60,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"unable to reach model search API at {self.settings.mirrors.huggingface_base}. "
                    f"network/connectivity error: {exc.__class__.__name__}"
                ),
            ) from exc
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=f"failed to search models: {resp.text[:300]}")

        payload = resp.json()
        rows = payload if isinstance(payload, list) else []
        out: List[Dict[str, Any]] = []
        for row in rows:
            repo_id = str(row.get("id") or "").strip()
            if not repo_id:
                continue
            out.append(
                {
                    "repo_id": repo_id,
                    "downloads": row.get("downloads") if isinstance(row.get("downloads"), int) else None,
                    "likes": row.get("likes") if isinstance(row.get("likes"), int) else None,
                    "last_modified": row.get("lastModified"),
                    "private": row.get("private") if isinstance(row.get("private"), bool) else None,
                    "gated": row.get("gated") if isinstance(row.get("gated"), bool) else None,
                }
            )
        return out

    def _pick_file(self, remote_paths: List[str], candidates: List[str]) -> Optional[str]:
        remote_set = set(remote_paths)
        for name in candidates:
            if name in remote_set:
                return name
        for name in candidates:
            matches = [x for x in remote_paths if x.endswith("/" + name)]
            if len(matches) == 1:
                return matches[0]
        return None

    def choose_download_files(self, remote_paths: List[str], requested_files: Optional[List[str]]) -> List[str]:
        if requested_files:
            remote_set = set(remote_paths)
            selected = [x for x in requested_files if x in remote_set]
            missing = [x for x in requested_files if x not in remote_set]
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail=f"requested files not found in repo: {', '.join(missing)}",
                )
            if not selected:
                raise HTTPException(status_code=422, detail="no valid files selected for download")
            return selected

        selected: List[str] = []
        config_file = self._pick_file(remote_paths, ["config.json"])
        model_file = self._pick_file(remote_paths, ["model.bin"])
        if not config_file or not model_file:
            raise HTTPException(status_code=422, detail="repo does not look like a faster-whisper model (missing config.json/model.bin)")
        selected.extend([config_file, model_file])

        tokenizer_file = self._pick_file(remote_paths, ["tokenizer.json", "tokenizer_config.json"])
        if tokenizer_file and tokenizer_file not in selected:
            selected.append(tokenizer_file)

        vocab_file = self._pick_file(remote_paths, ["vocabulary.json", "vocabulary.txt"])
        if vocab_file and vocab_file not in selected:
            selected.append(vocab_file)

        preprocess_file = self._pick_file(remote_paths, ["preprocessor_config.json"])
        if preprocess_file and preprocess_file not in selected:
            selected.append(preprocess_file)

        return selected

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

    async def create_local_model_jobs(
        self,
        *,
        preset_name: Optional[str],
        repo_id: Optional[str],
        revision: str,
        output_subdir: Optional[str],
        files: Optional[List[str]],
    ) -> List[DownloadJob]:
        selected_repo = (repo_id or "").strip()
        selected_subdir = (output_subdir or "").strip()

        if preset_name:
            preset = next((item for item in MODEL_PRESETS if item["name"] == preset_name), None)
            if preset is None:
                raise HTTPException(status_code=404, detail=f"unknown preset_name: {preset_name}")
            selected_repo = preset["repo_id"]
            if not selected_subdir:
                selected_subdir = preset["name"]

        if not selected_repo:
            raise HTTPException(status_code=422, detail="repo_id is required")

        if not selected_subdir:
            selected_subdir = selected_repo.replace("/", "--")

        requested_files = [x.strip("/") for x in (files or []) if str(x).strip("/")] or None

        # If caller provided explicit file list, do not hard-depend on remote metadata fetch.
        if requested_files:
            model_files = requested_files
        else:
            try:
                remote_files = await self.fetch_remote_repo_files(repo_id=selected_repo, revision=revision)
                remote_paths = [x["path"] for x in remote_files]
                model_files = self.choose_download_files(remote_paths, requested_files=None)
            except HTTPException as exc:
                if exc.status_code == 503:
                    model_files = fallback_faster_whisper_files(selected_repo)
                else:
                    raise

        created: List[DownloadJob] = []
        for file_name in model_files:
            built = await self.resolve_hf_file_url(
                repo_id=selected_repo,
                filename=file_name,
                revision=revision,
            )
            job = await self.create_job(
                source="huggingface_file",
                requested_url=f"hf://{selected_repo}@{revision}/{file_name}",
                resolved_url=built["url"],
                output_subdir=selected_subdir,
                output_filename=Path(file_name).name,
            )
            created.append(job)

        return created

    def list_local_models(self) -> List[Dict[str, Any]]:
        root = Path(self.settings.storage.model_dir)
        root.mkdir(parents=True, exist_ok=True)
        items: List[Dict[str, Any]] = []

        for current, _, filenames in os.walk(root):
            model_dir = Path(current)
            if not is_local_model_dir(model_dir):
                continue
            files_meta: List[Dict[str, Any]] = []
            total_size = 0
            latest_mtime = 0.0
            model_bin_size: Optional[int] = None

            for file_path in sorted(model_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                size = file_path.stat().st_size
                mtime = file_path.stat().st_mtime
                total_size += size
                latest_mtime = max(latest_mtime, mtime)
                if file_path.name == "model.bin":
                    model_bin_size = size
                files_meta.append(
                    {
                        "path": file_path.relative_to(model_dir).as_posix(),
                        "size_bytes": size,
                    }
                )

            rel_path = model_dir.relative_to(root).as_posix()
            updated_at = datetime.fromtimestamp(latest_mtime or time.time(), tz=timezone.utc)
            variant = detect_whisper_variant(rel_path)

            config_payload: Dict[str, Any] = {}
            config_path = model_dir / "config.json"
            if config_path.exists():
                try:
                    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception:
                    config_payload = {}

            if variant is None:
                variant = infer_variant_from_config(config_payload)
            variant_meta = WHISPER_VARIANT_METADATA.get(variant or "", {})

            items.append(
                {
                    "model_id": str(model_dir),
                    "display_name": rel_path,
                    "path": str(model_dir),
                    "total_size_bytes": total_size,
                    "model_bin_size_bytes": model_bin_size,
                    "file_count": len(files_meta),
                    "updated_at": updated_at,
                    "files": files_meta,
                    "variant": variant_meta.get("variant"),
                    "parameters_million": variant_meta.get("parameters_million"),
                    "estimated_model_bin_mb": variant_meta.get("estimated_model_bin_mb"),
                    "estimated_vram_gb": variant_meta.get("estimated_vram_gb"),
                    "context_tokens": variant_meta.get("context_tokens"),
                    "multilingual": variant_meta.get("multilingual"),
                }
            )

        return sorted(items, key=lambda x: x["updated_at"], reverse=True)

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

                active_url = job.resolved_url
                async with self.client.stream("GET", active_url, headers=headers, timeout=self.settings.downloads.timeout_sec, follow_redirects=True) as resp:
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
        normalize_proxy_env()
        configure_cuda_library_env()
        self.client = httpx.AsyncClient(
            timeout=settings.app.request_timeout_sec,
            trust_env=True,
        )
        self.media = MediaService(settings)
        self.local = LocalTranscriber(settings)
        self.api = APITranscriber(settings, self.client)
        self.downloads = DownloadManager(settings, self.client)
        self.jobs: Dict[str, TranscriptionJob] = {}
        self._job_sem = asyncio.Semaphore(max(1, settings.downloads.max_concurrent_jobs))

    async def close(self) -> None:
        await self.client.aclose()

    async def create_transcription_job(self, upload: UploadFile, options: Dict[str, Any]) -> TranscriptionJob:
        provider = str(options.get("provider") or self.settings.transcription.default_provider)
        source_name = upload.filename or "uploaded-file"
        source_content_type = upload.content_type
        raw_path = await self.media.save_upload(upload)

        requested_model = str(options.get("model") or (self.settings.local.model_id if provider == "local" else "default"))
        resolved_model = requested_model
        if provider == "local":
            resolved_model = self.local._resolve_model_id(requested_model)

        job = TranscriptionJob(
            job_id=uuid.uuid4().hex,
            provider=provider,
            model=resolved_model,
            source_filename=source_name,
            source_content_type=source_content_type,
            options=options,
            raw_path=raw_path,
        )
        self.jobs[job.job_id] = job
        asyncio.create_task(self._run_transcription_job(job))
        return job

    def get_transcription_job(self, job_id: str) -> TranscriptionJob:
        job = self.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="transcription job not found")
        return job

    def list_transcription_jobs(self) -> List[TranscriptionJob]:
        return sorted(self.jobs.values(), key=lambda x: x.created_at, reverse=True)

    def _update_job_progress(self, job: TranscriptionJob, percent: float, stage: Optional[str] = None) -> None:
        job.progress_percent = max(job.progress_percent, min(100.0, float(percent)))
        if stage:
            job.stage = stage

    def _resolve_chunking_runtime(self, options: Dict[str, Any], duration_seconds: Optional[float]) -> Dict[str, Any]:
        enabled_raw = options.get("chunking_enabled")
        chunk_minutes_raw = options.get("chunk_minutes")
        overlap_minutes_raw = options.get("chunk_overlap_minutes")
        min_duration_raw = options.get("chunk_min_duration_minutes")

        enabled = (
            self.settings.local.long_audio_chunking_enabled
            if enabled_raw is None
            else bool(enabled_raw)
        )
        chunk_minutes = (
            self.settings.local.long_audio_chunk_minutes
            if chunk_minutes_raw is None
            else float(chunk_minutes_raw)
        )
        overlap_minutes = (
            self.settings.local.long_audio_overlap_minutes
            if overlap_minutes_raw is None
            else float(overlap_minutes_raw)
        )
        min_duration_minutes = (
            self.settings.local.long_audio_min_duration_minutes
            if min_duration_raw is None
            else float(min_duration_raw)
        )

        chunk_minutes = max(0.1, float(chunk_minutes))
        overlap_minutes = max(0.0, float(overlap_minutes))
        if overlap_minutes >= chunk_minutes:
            overlap_minutes = max(0.0, chunk_minutes - 0.01)
        min_duration_minutes = max(0.1, float(min_duration_minutes))

        duration = float(duration_seconds) if duration_seconds is not None else None
        should_chunk = bool(
            enabled
            and duration is not None
            and duration >= (min_duration_minutes * 60.0)
            and duration > (chunk_minutes * 60.0)
            and chunk_minutes > overlap_minutes
        )

        return {
            "enabled": enabled,
            "should_chunk": should_chunk,
            "chunk_minutes": chunk_minutes,
            "overlap_minutes": overlap_minutes,
            "min_duration_minutes": min_duration_minutes,
            "duration_seconds": duration,
        }

    def _build_vocabulary_bias_text(self, options: Dict[str, Any]) -> Optional[str]:
        pieces: List[str] = []
        if self.settings.local.vocabulary_bias_enabled and self.settings.local.vocabulary_bias_text:
            pieces.append(str(self.settings.local.vocabulary_bias_text))
        if options.get("vocabulary_bias"):
            pieces.append(str(options["vocabulary_bias"]))

        if not pieces:
            return None

        raw_terms: List[str] = []
        for item in pieces:
            for term in re.split(r"[,;\n|،؛]+", item):
                cleaned = term.strip()
                if cleaned:
                    raw_terms.append(cleaned)

        unique_terms: List[str] = []
        seen: set[str] = set()
        for term in raw_terms:
            key = _normalize_merge_token(term)
            if not key or key in seen:
                continue
            seen.add(key)
            unique_terms.append(term)

        if not unique_terms:
            return None
        return "، ".join(unique_terms)

    def _apply_vocabulary_bias(self, options: Dict[str, Any], bias_text: Optional[str]) -> Dict[str, Any]:
        out = dict(options)
        if not bias_text:
            return out

        prefix = f"واژگان کلیدی و اصطلاحات تخصصی این فایل: {bias_text}"
        existing = str(out.get("prompt") or out.get("initial_prompt") or "").strip()
        out["prompt"] = f"{existing}\n{prefix}".strip() if existing else prefix
        return out

    def _merge_chunk_outputs(
        self,
        *,
        chunk_runs: List[Dict[str, Any]],
        segment_timestamps: bool,
        word_timestamps: bool,
        similarity_threshold: float,
        max_word_overlap: int,
    ) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = []
        all_words: List[Dict[str, Any]] = []
        language: Optional[str] = None
        duration_seconds: Optional[float] = None

        for run in chunk_runs:
            offset = float(run["start"])
            output = run["output"]
            if language is None and output.get("language"):
                language = output.get("language")
            if duration_seconds is None and output.get("duration_seconds") is not None:
                duration_seconds = float(output["duration_seconds"])

            segs = output.get("segments") if isinstance(output.get("segments"), list) else []
            if not segs:
                text_fallback = str(output.get("text") or "").strip()
                if text_fallback:
                    segs = [{
                        "id": 0,
                        "start": 0.0,
                        "end": max(0.0, float(run["end"]) - float(run["start"])),
                        "text": text_fallback,
                        "avg_logprob": None,
                        "no_speech_prob": None,
                        "words": [],
                    }]

            for seg in segs:
                text_seg = str(seg.get("text") or "").strip()
                if not text_seg:
                    continue
                start = offset + float(seg.get("start", 0.0))
                end = offset + float(seg.get("end", seg.get("start", 0.0)))
                if end < start:
                    end = start
                candidates.append(
                    {
                        "start": start,
                        "end": end,
                        "text": text_seg,
                        "avg_logprob": seg.get("avg_logprob"),
                        "no_speech_prob": seg.get("no_speech_prob"),
                        "words": seg.get("words") if isinstance(seg.get("words"), list) else [],
                    }
                )

                if word_timestamps:
                    for w in (seg.get("words") if isinstance(seg.get("words"), list) else []):
                        ws = offset + float(w.get("start", 0.0))
                        we = offset + float(w.get("end", w.get("start", 0.0)))
                        all_words.append(
                            {
                                "start": ws,
                                "end": max(ws, we),
                                "word": str(w.get("word") or ""),
                                "probability": w.get("probability"),
                            }
                        )

        candidates.sort(key=lambda x: (x["start"], x["end"]))

        merged_segments: List[Dict[str, Any]] = []
        merged_text_tokens: List[str] = []
        duplicate_count = 0
        dedupe_trimmed_words = 0

        for item in candidates:
            score = float(item["avg_logprob"]) if isinstance(item.get("avg_logprob"), (int, float)) else -10.0
            if merged_segments:
                prev = merged_segments[-1]
                overlap = max(0.0, min(prev["end"], item["end"]) - max(prev["start"], item["start"]))
                prev_duration = max(0.001, float(prev["end"]) - float(prev["start"]))
                item_duration = max(0.001, float(item["end"]) - float(item["start"]))
                overlap_ratio = overlap / min(prev_duration, item_duration)
                sim = _text_similarity(prev["text"], item["text"])

                if overlap > 0 and overlap_ratio >= 0.45 and sim >= similarity_threshold:
                    duplicate_count += 1
                    prev_score = (
                        float(prev["avg_logprob"])
                        if isinstance(prev.get("avg_logprob"), (int, float))
                        else -10.0
                    )
                    if score > prev_score:
                        merged_segments[-1] = dict(item)
                    continue

            current_tokens = _split_words(item["text"])
            current_norm = [_normalize_merge_token(x) for x in current_tokens]
            merged_norm = [_normalize_merge_token(x) for x in merged_text_tokens]
            overlap_words = _word_overlap_suffix_prefix(merged_norm, current_norm, max_word_overlap)
            if overlap_words > 0:
                dedupe_trimmed_words += overlap_words
                current_tokens = current_tokens[overlap_words:]

            if not current_tokens:
                continue

            clean_text = " ".join(current_tokens).strip()
            if not clean_text:
                continue

            merged_text_tokens.extend(current_tokens)
            new_seg = dict(item)
            new_seg["text"] = clean_text
            merged_segments.append(new_seg)

        final_segments: List[Dict[str, Any]] = []
        for idx, seg in enumerate(merged_segments):
            final_seg = {
                "id": idx,
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": str(seg["text"]),
                "avg_logprob": seg.get("avg_logprob"),
                "no_speech_prob": seg.get("no_speech_prob"),
            }
            if word_timestamps:
                final_seg["words"] = []
            final_segments.append(final_seg)

        merged_words: Optional[List[Dict[str, Any]]] = None
        if word_timestamps:
            all_words.sort(key=lambda x: (x["start"], x["end"]))
            merged_words = []
            for w in all_words:
                text_w = str(w.get("word") or "").strip()
                if not text_w:
                    continue
                if merged_words:
                    prev = merged_words[-1]
                    prev_word = _normalize_merge_token(str(prev.get("word") or ""))
                    cur_word = _normalize_merge_token(text_w)
                    overlap = max(0.0, min(float(prev["end"]), float(w["end"])) - max(float(prev["start"]), float(w["start"])))
                    if cur_word and prev_word == cur_word and overlap > 0:
                        continue
                merged_words.append(w)

        merged_plain_text = " ".join(merged_text_tokens).strip()
        merged_segment_text = "\n".join(seg["text"] for seg in final_segments if str(seg.get("text") or "").strip()).strip()

        return {
            "text": merged_segment_text or merged_plain_text,
            "language": language,
            "duration_seconds": duration_seconds,
            "segments": final_segments if segment_timestamps else None,
            "words": merged_words if word_timestamps else None,
            "merge_stats": {
                "input_segments": len(candidates),
                "output_segments": len(final_segments),
                "dropped_duplicates": duplicate_count,
                "dedupe_trimmed_words": dedupe_trimmed_words,
            },
        }

    async def _transcribe_local_with_optional_chunking(
        self,
        *,
        prepared_path: Path,
        options: Dict[str, Any],
        duration: Optional[float],
        progress_cb: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        chunking = self._resolve_chunking_runtime(options, duration)
        bias_text = self._build_vocabulary_bias_text(options)
        local_options = self._apply_vocabulary_bias(options, bias_text)

        if not chunking["should_chunk"]:
            out = await self.local.transcribe(
                prepared_path,
                local_options,
                duration_hint=duration,
                progress_cb=progress_cb,
            )
            out.setdefault("metadata", {}).setdefault(
                "chunking",
                {
                    "enabled": bool(chunking["enabled"]),
                    "used": False,
                    "reason": "duration_or_settings_not_matched",
                },
            )
            if bias_text:
                out.setdefault("metadata", {})["vocabulary_bias"] = {
                    "enabled": True,
                    "terms": bias_text,
                }
            return out

        window_minutes = float(chunking["chunk_minutes"])
        overlap_minutes = float(chunking["overlap_minutes"])
        windows = _build_overlapping_windows(
            duration_seconds=float(chunking["duration_seconds"]),
            window_minutes=window_minutes,
            overlap_minutes=overlap_minutes,
        )
        if len(windows) <= 1:
            out = await self.local.transcribe(prepared_path, local_options, duration_hint=duration, progress_cb=progress_cb)
            out.setdefault("metadata", {}).setdefault(
                "chunking",
                {
                    "enabled": True,
                    "used": False,
                    "reason": "single_window_after_planning",
                },
            )
            if bias_text:
                out.setdefault("metadata", {})["vocabulary_bias"] = {
                    "enabled": True,
                    "terms": bias_text,
                }
            return out

        run_options = dict(local_options)
        run_options["segment_timestamps"] = True
        run_options["condition_on_previous_text"] = False

        chunk_runs: List[Dict[str, Any]] = []
        chunk_temp_paths: List[Path] = []
        total_windows = len(windows)
        try:
            for idx, w in enumerate(windows):
                if progress_cb:
                    progress_cb(round((idx / max(1, total_windows)) * 100.0, 2))
                chunk_path = await self.media.extract_audio_window(prepared_path, float(w["start"]), float(w["end"]))
                chunk_temp_paths.append(chunk_path)
                chunk_duration = max(0.0, float(w["end"]) - float(w["start"]))
                chunk_start_pct = (idx / max(1, total_windows)) * 100.0
                chunk_end_pct = ((idx + 1) / max(1, total_windows)) * 100.0
                chunk_out = await self.local.transcribe(
                    chunk_path,
                    run_options,
                    duration_hint=chunk_duration,
                    progress_cb=(
                        (lambda p, _s=chunk_start_pct, _e=chunk_end_pct: progress_cb(round(_s + ((_e - _s) * (float(p) / 100.0)), 2)))
                        if progress_cb is not None
                        else None
                    ),
                )
                chunk_runs.append(
                    {
                        "index": int(w["index"]),
                        "start": float(w["start"]),
                        "end": float(w["end"]),
                        "output": chunk_out,
                    }
                )
                if progress_cb:
                    progress_cb(round(((idx + 1) / max(1, total_windows)) * 100.0, 2))

            merged = self._merge_chunk_outputs(
                chunk_runs=chunk_runs,
                segment_timestamps=(
                    self.settings.transcription.enable_segment_timestamps
                    if options.get("segment_timestamps") is None
                    else bool(options.get("segment_timestamps"))
                ),
                word_timestamps=(
                    self.settings.transcription.enable_word_timestamps
                    if options.get("word_timestamps") is None
                    else bool(options.get("word_timestamps"))
                ),
                similarity_threshold=float(self.settings.local.chunk_merge_similarity_threshold),
                max_word_overlap=int(self.settings.local.chunk_merge_max_word_overlap),
            )

            total_process_ms = 0.0
            resolved_model: Optional[str] = None
            execution_device: Optional[str] = None
            for run in chunk_runs:
                usage = run["output"].get("usage") or {}
                if isinstance(usage.get("process_ms"), (int, float)):
                    total_process_ms += float(usage["process_ms"])
                md = run["output"].get("metadata") or {}
                if resolved_model is None and md.get("resolved_model"):
                    resolved_model = str(md["resolved_model"])
                if execution_device is None and md.get("execution_device") is not None:
                    execution_device = md.get("execution_device")

            out: Dict[str, Any] = {
                "text": merged["text"],
                "language": merged["language"],
                "duration_seconds": duration,
                "segments": merged["segments"],
                "words": merged["words"],
                "usage": {
                    "provider": "local",
                    "model": resolved_model or str(options.get("model") or self.settings.local.model_id),
                    "audio_seconds": duration,
                    "process_ms": round(total_process_ms, 2),
                },
                "metadata": {
                    "requested_model": str(options.get("model") or self.settings.local.model_id),
                    "resolved_model": resolved_model,
                    "execution_device": execution_device,
                    "chunking": {
                        "enabled": True,
                        "used": True,
                        "window_minutes": window_minutes,
                        "overlap_minutes": overlap_minutes,
                        "window_count": len(windows),
                        "windows": windows,
                        "merge_stats": merged["merge_stats"],
                    },
                    "local_decode_options": {
                        "beam_size": run_options.get("beam_size"),
                        "best_of": run_options.get("best_of"),
                        "patience": run_options.get("patience"),
                        "temperature": run_options.get("temperature"),
                        "condition_on_previous_text": False,
                        "prompt": run_options.get("prompt") or run_options.get("initial_prompt"),
                        "repetition_penalty": run_options.get("repetition_penalty"),
                        "no_repeat_ngram_size": run_options.get("no_repeat_ngram_size"),
                    },
                },
            }

            if bias_text:
                out["metadata"]["vocabulary_bias"] = {
                    "enabled": True,
                    "terms": bias_text,
                }

            merged_tail_loop = _detect_tail_loop(out["text"])
            if merged_tail_loop:
                trimmed_text = _trim_detected_tail_loop(out["text"], merged_tail_loop)
                tail_trim_applied = False
                if trimmed_text and trimmed_text != out["text"]:
                    out["text"] = trimmed_text
                    tail_trim_applied = True
                out["metadata"]["tail_loop_guard"] = {
                    "detected_after_chunk_merge": merged_tail_loop,
                    "tail_trim_applied": tail_trim_applied,
                }

            return out
        finally:
            for p in chunk_temp_paths:
                if p.exists():
                    p.unlink(missing_ok=True)

    async def _run_transcription_job(self, job: TranscriptionJob) -> None:
        async with self._job_sem:
            if job.cancel_event.is_set():
                job.status = "cancelled"
                job.completed_at = now_utc()
                return

            prepared_path: Optional[Path] = None
            try:
                job.status = "running"
                job.started_at = now_utc()
                self._update_job_progress(job, 0, "validating")

                if not (is_video_file(job.source_filename, job.source_content_type) or is_audio_file(job.source_filename, job.source_content_type)):
                    raise HTTPException(status_code=415, detail="unsupported media type, upload an audio/video file")

                self._update_job_progress(job, 0, "preparing-audio")
                prepared_path = await self.media.extract_audio(job.raw_path, job.source_filename, job.source_content_type)
                duration = await self.media.probe_duration(prepared_path)
                self._update_job_progress(job, 0, "loading-model")

                if job.provider == "local":
                    out = await self._transcribe_local_with_optional_chunking(
                        prepared_path=prepared_path,
                        options=job.options,
                        duration=duration,
                        progress_cb=lambda p: self._update_job_progress(job, p, "transcribing"),
                    )
                else:
                    out = await self.api.transcribe(job.provider, prepared_path, job.options)
                    self._update_job_progress(job, 0, "finalizing")

                meta = out.setdefault("metadata", {})
                meta.update(
                    {
                        "input_filename": job.source_filename,
                        "input_content_type": job.source_content_type,
                        "provider": job.provider,
                        "audio_prepared_path": str(prepared_path),
                        "duration_probe_seconds": duration,
                        "was_video": is_video_file(job.source_filename, job.source_content_type),
                    }
                )

                job.result = out
                job.status = "completed"
                self._update_job_progress(job, 100, "completed")
                job.completed_at = now_utc()
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = now_utc()
                job.stage = "failed"
            finally:
                if self.settings.storage.cleanup_temp_after_request:
                    for p in {job.raw_path, prepared_path}:
                        if p and p.exists():
                            try:
                                p.unlink(missing_ok=True)
                            except Exception:
                                pass
                else:
                    if prepared_path and job.raw_path != prepared_path and not self.settings.processing.preserve_original_upload:
                        job.raw_path.unlink(missing_ok=True)

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
                out = await self._transcribe_local_with_optional_chunking(
                    prepared_path=prepared_path,
                    options=options,
                    duration=duration,
                    progress_cb=None,
                )
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
