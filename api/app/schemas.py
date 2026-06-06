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


class ProviderRuntimeStatus(BaseModel):
    name: str
    configured: bool
    key_present: bool
    valid: bool
    enabled_for_user: bool
    model: Optional[str] = None
    base_url: Optional[str] = None
    status_code: Optional[int] = None
    reason: str = ""


class ProviderRuntimeStatusResponse(BaseModel):
    default_provider: str
    providers: List[ProviderRuntimeStatus]


class ProviderPanelConfig(BaseModel):
    name: Literal["openai", "groq"]
    enabled: bool = False
    base_url: str = ""
    model: str = ""
    transcriptions_path: str = "/v1/audio/transcriptions"
    timeout_sec: float = 300.0
    api_keys: List[str] = Field(default_factory=list)


class ProviderPanelSettingsResponse(BaseModel):
    env_path: str
    providers: List[ProviderPanelConfig]


class ProviderPanelSettingsUpdateRequest(BaseModel):
    providers: List[ProviderPanelConfig]


class ProviderKeyTestRequest(BaseModel):
    provider: Literal["openai", "groq"]
    api_key: str
    base_url: Optional[str] = None


class ProviderKeyTestResponse(BaseModel):
    provider: str
    valid: bool
    status_code: Optional[int] = None
    reason: str = ""


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
    beam_size: Optional[int] = None
    best_of: Optional[int] = None
    patience: Optional[float] = None
    condition_on_previous_text: Optional[bool] = None
    initial_prompt: Optional[str] = None
    repetition_penalty: Optional[float] = None
    no_repeat_ngram_size: Optional[int] = None
    compression_ratio_threshold: Optional[float] = None
    log_prob_threshold: Optional[float] = None
    no_speech_threshold: Optional[float] = None
    prompt_reset_on_temperature: Optional[float] = None
    hallucination_silence_threshold: Optional[float] = None
    max_new_tokens: Optional[int] = None
    vad_threshold: Optional[float] = None
    vad_neg_threshold: Optional[float] = None
    vad_min_speech_duration_ms: Optional[int] = None
    vad_min_silence_duration_ms: Optional[int] = None
    vad_speech_pad_ms: Optional[int] = None
    chunking_enabled: Optional[bool] = None
    chunk_minutes: Optional[float] = None
    chunk_overlap_minutes: Optional[float] = None
    chunk_min_duration_minutes: Optional[float] = None
    vocabulary_bias: Optional[str] = None


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


class TranscriptionJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    provider: str
    model: str
    source_filename: str
    source_content_type: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float = 0.0
    stage: str = "queued"
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class TranscriptionJobListResponse(BaseModel):
    total: int
    items: List[TranscriptionJobResponse]


class HuggingFaceFileUrlRequest(BaseModel):
    repo_id: str = Field(..., examples=["openai/whisper-large-v3"])
    filename: str = Field(..., examples=["config.json"])
    revision: str = Field(default="main")


class ModelUrlResponse(BaseModel):
    source: Literal["official"]
    url: str


class DownloadJobCreateRequest(BaseModel):
    source: Literal["url", "huggingface_file"]
    url: Optional[str] = None
    repo_id: Optional[str] = None
    filename: Optional[str] = None
    revision: str = "main"
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
    variant: Optional[str] = None
    parameters_million: Optional[int] = None
    estimated_model_bin_mb: Optional[int] = None
    estimated_vram_gb: Optional[float] = None
    context_tokens: Optional[int] = None
    multilingual: Optional[bool] = None


class LocalModelPresetsResponse(BaseModel):
    total: int
    items: List[LocalModelPreset]


class LocalModelFileInfo(BaseModel):
    path: str
    size_bytes: int


class LocalModelInfo(BaseModel):
    model_id: str
    display_name: str
    path: str
    total_size_bytes: int
    model_bin_size_bytes: Optional[int] = None
    file_count: int
    updated_at: datetime
    files: List[LocalModelFileInfo]
    variant: Optional[str] = None
    parameters_million: Optional[int] = None
    estimated_model_bin_mb: Optional[int] = None
    estimated_vram_gb: Optional[float] = None
    context_tokens: Optional[int] = None
    multilingual: Optional[bool] = None


class LocalModelsResponse(BaseModel):
    total: int
    model_root: str
    items: List[LocalModelInfo]


class LocalModelDownloadRequest(BaseModel):
    preset_name: Optional[str] = None
    repo_id: Optional[str] = None
    revision: str = "main"
    output_subdir: Optional[str] = None
    files: Optional[List[str]] = None


class UserLocalModelDownloadRequest(BaseModel):
    model: str = Field(default="large-v3")
    hf_token: Optional[str] = None


class UserLocalModelStatusResponse(BaseModel):
    model: str
    canonical_model: str
    present: bool
    matched_model: Optional[LocalModelInfo] = None
    preset_name: str
    repo_id: str
    revision: str
    output_subdir: str
    estimated_model_bin_mb: Optional[int] = None
    estimated_total_mb: Optional[int] = None
    estimated_vram_gb: Optional[float] = None
    hf_token_present: bool
    hf_token_help_url: str


class DownloadBatchResponse(BaseModel):
    total: int
    items: List[DownloadJobResponse]


class RemoteModelRepoInfo(BaseModel):
    repo_id: str
    downloads: Optional[int] = None
    likes: Optional[int] = None
    last_modified: Optional[datetime] = None
    private: Optional[bool] = None
    gated: Optional[bool] = None


class RemoteModelRepoListResponse(BaseModel):
    total: int
    items: List[RemoteModelRepoInfo]


class RemoteModelFileInfo(BaseModel):
    path: str
    size_bytes: Optional[int] = None
    lfs_size_bytes: Optional[int] = None


class RemoteModelFilesResponse(BaseModel):
    repo_id: str
    revision: str
    total: int
    recommended_files: List[str]
    items: List[RemoteModelFileInfo]


class EffectiveConfigResponse(BaseModel):
    generated_at: datetime
    precedence: str
    config: Dict[str, Any]


class EditableConfigResponse(BaseModel):
    generated_at: datetime
    config_path: str
    file_config: Dict[str, Any]
    effective_config: Dict[str, Any]
    precedence: str


class EditableConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]
    persist_to_file: bool = True
    reload_runtime: bool = True
