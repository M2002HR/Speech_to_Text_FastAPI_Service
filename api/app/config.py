from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class AppSection(BaseModel):
    name: str = "Speech To Text Service"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    request_timeout_sec: float = 300.0
    enable_docs: bool = True
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"


class StorageSection(BaseModel):
    runtime_dir: str = "runtime"
    upload_dir: str = "runtime/uploads"
    output_dir: str = "runtime/outputs"
    model_dir: str = "runtime/models"
    cleanup_temp_after_request: bool = True
    max_upload_mb: int = 2048


class ProcessingSection(BaseModel):
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    audio_codec: str = "pcm_s16le"
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    always_extract_audio: bool = True
    extracted_audio_format: str = "wav"
    preserve_original_upload: bool = False


class AdminSection(BaseModel):
    enabled: bool = True
    require_auth: bool = False
    token: str = ""
    header_name: str = "x-admin-token"


class TranscriptionSection(BaseModel):
    default_provider: Literal["local", "openai", "groq", "custom"] = "local"
    default_language: Optional[str] = None
    default_prompt: Optional[str] = None
    default_response_format: Literal["text", "json", "verbose_json", "srt", "vtt"] = "verbose_json"
    enable_word_timestamps: bool = True
    enable_segment_timestamps: bool = True


class LocalSection(BaseModel):
    backend: Literal["faster_whisper"] = "faster_whisper"
    model_id: str = "small"
    device: str = "auto"
    compute_type: str = "auto"
    cpu_threads: int = 4
    num_workers: int = 1
    vad_filter: bool = True
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    temperature: float = 0.0
    condition_on_previous_text: bool = True
    initial_prompt: Optional[str] = None
    repetition_penalty: float = 1.0
    no_repeat_ngram_size: int = 0
    compression_ratio_threshold: Optional[float] = 2.4
    log_prob_threshold: Optional[float] = -1.0
    no_speech_threshold: Optional[float] = 0.6
    prompt_reset_on_temperature: float = 0.5
    hallucination_silence_threshold: Optional[float] = None
    max_new_tokens: Optional[int] = None
    vad_threshold: Optional[float] = None
    vad_neg_threshold: Optional[float] = None
    vad_min_speech_duration_ms: Optional[int] = None
    vad_min_silence_duration_ms: Optional[int] = None
    vad_speech_pad_ms: Optional[int] = None


class ProviderSection(BaseModel):
    enabled: bool = False
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    transcriptions_path: str = "/v1/audio/transcriptions"
    timeout_sec: float = 300.0


class CustomProviderSection(ProviderSection):
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"


class ProvidersSection(BaseModel):
    openai: ProviderSection = Field(default_factory=lambda: ProviderSection(
        enabled=False,
        base_url="https://api.openai.com",
        model="whisper-1",
    ))
    groq: ProviderSection = Field(default_factory=lambda: ProviderSection(
        enabled=False,
        base_url="https://api.groq.com/openai",
        model="whisper-large-v3",
    ))
    custom: CustomProviderSection = Field(default_factory=CustomProviderSection)


class MirrorsSection(BaseModel):
    huggingface_base: str = "https://huggingface.co"


class DownloadsSection(BaseModel):
    enabled: bool = True
    max_concurrent_jobs: int = 2
    chunk_size: int = 1024 * 1024
    timeout_sec: float = 1800.0
    allow_resume: bool = True
    allowed_domains: List[str] = Field(default_factory=lambda: ["huggingface.co"])

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def _normalize_domains(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [x.strip() for x in value.split(",") if x.strip()]
        else:
            items = [str(x).strip() for x in value if str(x).strip()]
        return sorted(set(items))


class Settings(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    storage: StorageSection = Field(default_factory=StorageSection)
    processing: ProcessingSection = Field(default_factory=ProcessingSection)
    admin: AdminSection = Field(default_factory=AdminSection)
    transcription: TranscriptionSection = Field(default_factory=TranscriptionSection)
    local: LocalSection = Field(default_factory=LocalSection)
    providers: ProvidersSection = Field(default_factory=ProvidersSection)
    mirrors: MirrorsSection = Field(default_factory=MirrorsSection)
    downloads: DownloadsSection = Field(default_factory=DownloadsSection)

    @model_validator(mode="after")
    def _validate_settings(self) -> "Settings":
        if self.transcription.default_provider == "openai" and not self.providers.openai.enabled:
            raise ValueError("default provider is openai but providers.openai.enabled is false")
        if self.transcription.default_provider == "groq" and not self.providers.groq.enabled:
            raise ValueError("default provider is groq but providers.groq.enabled is false")
        if self.transcription.default_provider == "custom" and not self.providers.custom.enabled:
            raise ValueError("default provider is custom but providers.custom.enabled is false")

        if self.providers.openai.enabled and (not self.providers.openai.base_url or not self.providers.openai.api_key):
            raise ValueError("providers.openai requires base_url and api_key when enabled")
        if self.providers.groq.enabled and (not self.providers.groq.base_url or not self.providers.groq.api_key):
            raise ValueError("providers.groq requires base_url and api_key when enabled")
        if self.providers.custom.enabled and (not self.providers.custom.base_url or not self.providers.custom.api_key):
            raise ValueError("providers.custom requires base_url and api_key when enabled")

        if self.storage.max_upload_mb <= 0:
            raise ValueError("storage.max_upload_mb must be positive")
        if self.downloads.max_concurrent_jobs <= 0:
            raise ValueError("downloads.max_concurrent_jobs must be positive")

        return self


# -------------------------
# Parsing helpers
# -------------------------
def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _set_nested(data: Dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    cursor = data
    for key in keys[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[keys[-1]] = value


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return raw


def _apply_env_overrides(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    mapping: Dict[str, tuple[str, Any]] = {
        "APP_NAME": ("app.name", str),
        "APP_VERSION": ("app.version", str),
        "APP_HOST": ("app.host", str),
        "APP_PORT": ("app.port", int),
        "APP_LOG_LEVEL": ("app.log_level", str),
        "APP_REQUEST_TIMEOUT_SEC": ("app.request_timeout_sec", float),
        "APP_ENABLE_DOCS": ("app.enable_docs", _parse_bool),
        "APP_DOCS_URL": ("app.docs_url", str),
        "APP_REDOC_URL": ("app.redoc_url", str),
        "APP_OPENAPI_URL": ("app.openapi_url", str),

        "STORAGE_RUNTIME_DIR": ("storage.runtime_dir", str),
        "STORAGE_UPLOAD_DIR": ("storage.upload_dir", str),
        "STORAGE_OUTPUT_DIR": ("storage.output_dir", str),
        "STORAGE_MODEL_DIR": ("storage.model_dir", str),
        "STORAGE_CLEANUP_TEMP_AFTER_REQUEST": ("storage.cleanup_temp_after_request", _parse_bool),
        "STORAGE_MAX_UPLOAD_MB": ("storage.max_upload_mb", int),

        "PROCESSING_FFMPEG_BINARY": ("processing.ffmpeg_binary", str),
        "PROCESSING_FFPROBE_BINARY": ("processing.ffprobe_binary", str),
        "PROCESSING_AUDIO_CODEC": ("processing.audio_codec", str),
        "PROCESSING_AUDIO_SAMPLE_RATE": ("processing.audio_sample_rate", int),
        "PROCESSING_AUDIO_CHANNELS": ("processing.audio_channels", int),
        "PROCESSING_ALWAYS_EXTRACT_AUDIO": ("processing.always_extract_audio", _parse_bool),
        "PROCESSING_EXTRACTED_AUDIO_FORMAT": ("processing.extracted_audio_format", str),
        "PROCESSING_PRESERVE_ORIGINAL_UPLOAD": ("processing.preserve_original_upload", _parse_bool),

        "ADMIN_ENABLED": ("admin.enabled", _parse_bool),
        "ADMIN_REQUIRE_AUTH": ("admin.require_auth", _parse_bool),
        "ADMIN_TOKEN": ("admin.token", str),
        "ADMIN_HEADER_NAME": ("admin.header_name", str),

        "TRANSCRIPTION_DEFAULT_PROVIDER": ("transcription.default_provider", str),
        "TRANSCRIPTION_DEFAULT_LANGUAGE": ("transcription.default_language", str),
        "TRANSCRIPTION_DEFAULT_PROMPT": ("transcription.default_prompt", str),
        "TRANSCRIPTION_DEFAULT_RESPONSE_FORMAT": ("transcription.default_response_format", str),
        "TRANSCRIPTION_ENABLE_WORD_TIMESTAMPS": ("transcription.enable_word_timestamps", _parse_bool),
        "TRANSCRIPTION_ENABLE_SEGMENT_TIMESTAMPS": ("transcription.enable_segment_timestamps", _parse_bool),

        "LOCAL_BACKEND": ("local.backend", str),
        "LOCAL_MODEL_ID": ("local.model_id", str),
        "LOCAL_DEVICE": ("local.device", str),
        "LOCAL_COMPUTE_TYPE": ("local.compute_type", str),
        "LOCAL_CPU_THREADS": ("local.cpu_threads", int),
        "LOCAL_NUM_WORKERS": ("local.num_workers", int),
        "LOCAL_VAD_FILTER": ("local.vad_filter", _parse_bool),
        "LOCAL_BEAM_SIZE": ("local.beam_size", int),
        "LOCAL_BEST_OF": ("local.best_of", int),
        "LOCAL_PATIENCE": ("local.patience", float),
        "LOCAL_TEMPERATURE": ("local.temperature", float),
        "LOCAL_CONDITION_ON_PREVIOUS_TEXT": ("local.condition_on_previous_text", _parse_bool),
        "LOCAL_INITIAL_PROMPT": ("local.initial_prompt", str),
        "LOCAL_REPETITION_PENALTY": ("local.repetition_penalty", float),
        "LOCAL_NO_REPEAT_NGRAM_SIZE": ("local.no_repeat_ngram_size", int),
        "LOCAL_COMPRESSION_RATIO_THRESHOLD": ("local.compression_ratio_threshold", float),
        "LOCAL_LOG_PROB_THRESHOLD": ("local.log_prob_threshold", float),
        "LOCAL_NO_SPEECH_THRESHOLD": ("local.no_speech_threshold", float),
        "LOCAL_PROMPT_RESET_ON_TEMPERATURE": ("local.prompt_reset_on_temperature", float),
        "LOCAL_HALLUCINATION_SILENCE_THRESHOLD": ("local.hallucination_silence_threshold", float),
        "LOCAL_MAX_NEW_TOKENS": ("local.max_new_tokens", int),
        "LOCAL_VAD_THRESHOLD": ("local.vad_threshold", float),
        "LOCAL_VAD_NEG_THRESHOLD": ("local.vad_neg_threshold", float),
        "LOCAL_VAD_MIN_SPEECH_DURATION_MS": ("local.vad_min_speech_duration_ms", int),
        "LOCAL_VAD_MIN_SILENCE_DURATION_MS": ("local.vad_min_silence_duration_ms", int),
        "LOCAL_VAD_SPEECH_PAD_MS": ("local.vad_speech_pad_ms", int),

        "PROVIDER_OPENAI_ENABLED": ("providers.openai.enabled", _parse_bool),
        "PROVIDER_OPENAI_BASE_URL": ("providers.openai.base_url", str),
        "PROVIDER_OPENAI_API_KEY": ("providers.openai.api_key", str),
        "PROVIDER_OPENAI_MODEL": ("providers.openai.model", str),
        "PROVIDER_OPENAI_TRANSCRIPTIONS_PATH": ("providers.openai.transcriptions_path", str),
        "PROVIDER_OPENAI_TIMEOUT_SEC": ("providers.openai.timeout_sec", float),

        "PROVIDER_GROQ_ENABLED": ("providers.groq.enabled", _parse_bool),
        "PROVIDER_GROQ_BASE_URL": ("providers.groq.base_url", str),
        "PROVIDER_GROQ_API_KEY": ("providers.groq.api_key", str),
        "PROVIDER_GROQ_MODEL": ("providers.groq.model", str),
        "PROVIDER_GROQ_TRANSCRIPTIONS_PATH": ("providers.groq.transcriptions_path", str),
        "PROVIDER_GROQ_TIMEOUT_SEC": ("providers.groq.timeout_sec", float),

        "PROVIDER_CUSTOM_ENABLED": ("providers.custom.enabled", _parse_bool),
        "PROVIDER_CUSTOM_BASE_URL": ("providers.custom.base_url", str),
        "PROVIDER_CUSTOM_API_KEY": ("providers.custom.api_key", str),
        "PROVIDER_CUSTOM_MODEL": ("providers.custom.model", str),
        "PROVIDER_CUSTOM_TRANSCRIPTIONS_PATH": ("providers.custom.transcriptions_path", str),
        "PROVIDER_CUSTOM_TIMEOUT_SEC": ("providers.custom.timeout_sec", float),
        "PROVIDER_CUSTOM_AUTH_HEADER": ("providers.custom.auth_header", str),
        "PROVIDER_CUSTOM_AUTH_SCHEME": ("providers.custom.auth_scheme", str),

        "MIRRORS_HUGGINGFACE_BASE": ("mirrors.huggingface_base", str),

        "DOWNLOADS_ENABLED": ("downloads.enabled", _parse_bool),
        "DOWNLOADS_MAX_CONCURRENT_JOBS": ("downloads.max_concurrent_jobs", int),
        "DOWNLOADS_CHUNK_SIZE": ("downloads.chunk_size", int),
        "DOWNLOADS_TIMEOUT_SEC": ("downloads.timeout_sec", float),
        "DOWNLOADS_ALLOW_RESUME": ("downloads.allow_resume", _parse_bool),
        "DOWNLOADS_ALLOWED_DOMAINS": ("downloads.allowed_domains", _parse_csv),
    }

    merged = dict(config_dict)
    for env_name, (path, caster) in mapping.items():
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        _set_nested(merged, path, caster(raw))

    return merged


def _ensure_runtime_dirs(settings: Settings) -> None:
    for raw_path in [
        settings.storage.runtime_dir,
        settings.storage.upload_dir,
        settings.storage.output_dir,
        settings.storage.model_dir,
    ]:
        Path(raw_path).mkdir(parents=True, exist_ok=True)


def load_settings(config_file: str | None = None) -> Settings:
    load_dotenv(override=False)

    default_data = Settings().model_dump()
    cfg_path = Path(config_file or os.getenv("APP_CONFIG_FILE", "config/config.yml"))
    file_data = _load_yaml(cfg_path)
    merged = _deep_merge(default_data, file_data)
    merged = _apply_env_overrides(merged)

    try:
        settings = Settings.model_validate(merged)
    except ValidationError as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc

    _ensure_runtime_dirs(settings)
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
