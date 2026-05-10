from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    ffmpeg_available: bool
    ffprobe_available: bool
    default_provider: str
    now_utc: datetime


class ProviderInfo(BaseModel):
    name: str
    enabled: bool
    base_url: Optional[str] = None
    model: Optional[str] = None


class ProvidersResponse(BaseModel):
    default_provider: str
    providers: List[ProviderInfo]


class TranscribeOptions(BaseModel):
    provider: Optional[Literal["local", "openai", "groq", "custom"]] = None
    model: Optional[str] = None
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: Optional[Literal["text", "json", "verbose_json", "srt", "vtt"]] = None
    temperature: Optional[float] = None
    word_timestamps: Optional[bool] = None
    segment_timestamps: Optional[bool] = None
    vad_filter: Optional[bool] = None


class WordTimestamp(BaseModel):
    start: float
    end: float
    word: str
    probability: Optional[float] = None


class SegmentTimestamp(BaseModel):
    id: int
    start: float
    end: float
    text: str
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None
    words: Optional[List[WordTimestamp]] = None


class TranscriptionUsage(BaseModel):
    provider: str
    model: str
    audio_seconds: Optional[float] = None
    process_ms: float


class TranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    segments: Optional[List[SegmentTimestamp]] = None
    words: Optional[List[WordTimestamp]] = None
    usage: TranscriptionUsage
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MirrorInfoResponse(BaseModel):
    huggingface_base: str
    huggingface_mirror_base: str
    prefer_mirror: bool
    fallback_to_official: bool
    checked_at: datetime
    mirror_reachable: Optional[bool] = None
    official_reachable: Optional[bool] = None


class HuggingFaceFileUrlRequest(BaseModel):
    repo_id: str = Field(..., examples=["openai/whisper-large-v3"])
    filename: str = Field(..., examples=["config.json"])
    revision: str = Field(default="main")
    use_mirror: Optional[bool] = None


class ModelUrlResponse(BaseModel):
    source: Literal["mirror", "official"]
    url: str


class DownloadJobCreateRequest(BaseModel):
    source: Literal["url", "huggingface_file"]
    url: Optional[str] = None
    repo_id: Optional[str] = None
    filename: Optional[str] = None
    revision: str = "main"
    use_mirror: Optional[bool] = None
    output_subdir: str = "manual"
    output_filename: Optional[str] = None


class DownloadJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    source: str
    requested_url: str
    resolved_url: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    bytes_total: Optional[int] = None
    bytes_downloaded: int = 0
    progress_percent: Optional[float] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


class DownloadListResponse(BaseModel):
    total: int
    items: List[DownloadJobResponse]


class LocalModelPreset(BaseModel):
    name: str
    repo_id: str
    notes: str


class LocalModelPresetsResponse(BaseModel):
    total: int
    items: List[LocalModelPreset]


class EffectiveConfigResponse(BaseModel):
    generated_at: datetime
    precedence: str
    config: Dict[str, Any]
