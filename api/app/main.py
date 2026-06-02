from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Security, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from .config import ProviderSection, Settings, get_settings, load_settings
from .schemas import (
    DownloadBatchResponse,
    EditableConfigResponse,
    EditableConfigUpdateRequest,
    DownloadJobCreateRequest,
    DownloadJobResponse,
    DownloadListResponse,
    EffectiveConfigResponse,
    HealthResponse,
    HuggingFaceFileUrlRequest,
    LocalModelDownloadRequest,
    LocalModelsResponse,
    LocalModelPresetsResponse,
    RemoteModelFilesResponse,
    RemoteModelRepoListResponse,
    ModelUrlResponse,
    ProviderInfo,
    ProvidersResponse,
    ProviderRuntimeStatusResponse,
    TranscriptionJobListResponse,
    TranscriptionJobResponse,
    TranscriptionResponse,
    UserLocalModelDownloadRequest,
    UserLocalModelStatusResponse,
)
from .services import (
    MODEL_PRESETS,
    VARIANT_TO_LOCAL_DIR_ALIASES,
    WHISPER_VARIANT_METADATA,
    ServiceContainer,
    canonicalize_faster_whisper_model_id,
    detect_whisper_variant,
    normalize_model_token,
    now_utc,
)

_RUNTIME_SETTINGS = get_settings()
_DOCS_ENABLED = bool(_RUNTIME_SETTINGS.app.enable_docs)
_UI_DIR = Path(__file__).resolve().parent / "ui"

_ADMIN_API_KEY = APIKeyHeader(
    name=_RUNTIME_SETTINGS.admin.header_name,
    auto_error=False,
    scheme_name="AdminTokenAuth",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.services = ServiceContainer(settings=settings)
    try:
        yield
    finally:
        await app.state.services.close()


app = FastAPI(
    title=_RUNTIME_SETTINGS.app.name,
    version=_RUNTIME_SETTINGS.app.version,
    description=(
        "Audio/Video to Text service with local and API backends, ffmpeg preprocessing, "
        "and model download management via Hugging Face."
    ),
    docs_url=_RUNTIME_SETTINGS.app.docs_url if _DOCS_ENABLED else None,
    redoc_url=_RUNTIME_SETTINGS.app.redoc_url if _DOCS_ENABLED else None,
    openapi_url=_RUNTIME_SETTINGS.app.openapi_url if _DOCS_ENABLED else None,
    swagger_ui_parameters={
        "tryItOutEnabled": True,
        "displayRequestDuration": True,
        "persistAuthorization": True,
    },
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Runtime health and diagnostics."},
        {"name": "transcription", "description": "Upload audio/video and get transcription."},
        {"name": "providers", "description": "Configured transcription providers."},
        {"name": "admin-system", "description": "Effective runtime config and system state."},
        {"name": "admin-models", "description": "Local presets + Hugging Face model tools."},
        {"name": "admin-downloads", "description": "Model download jobs management."},
    ],
)
app.mount("/ui-assets", StaticFiles(directory=str(_UI_DIR)), name="ui-assets")


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) < 10:
        return "***"
    return value[:3] + "***" + value[-3:]


def _redacted_config(settings: Settings) -> Dict[str, Any]:
    data = settings.model_dump()
    data["providers"]["openai"]["api_key"] = _mask_secret(data["providers"]["openai"].get("api_key", ""))
    data["providers"]["groq"]["api_key"] = _mask_secret(data["providers"]["groq"].get("api_key", ""))
    data["providers"]["custom"]["api_key"] = _mask_secret(data["providers"]["custom"].get("api_key", ""))
    data["admin"]["token"] = _mask_secret(data["admin"].get("token", ""))
    return data


def _models_url_for_provider(base_url: str) -> str:
    base = str(base_url or "").rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


async def _check_openai_compatible_provider(
    request: Request,
    *,
    provider_name: str,
    provider: ProviderSection,
) -> Dict[str, Any]:
    configured = bool(provider.enabled)
    key_present = bool(provider.api_key)
    base_url = provider.base_url if configured else None
    model = provider.model or None

    out: Dict[str, Any] = {
        "name": provider_name,
        "configured": configured,
        "key_present": key_present,
        "valid": False,
        "enabled_for_user": False,
        "model": model,
        "base_url": base_url,
        "status_code": None,
        "reason": "",
    }

    if not configured:
        out["reason"] = "provider is disabled in config"
        return out
    if not provider.base_url:
        out["reason"] = "provider base_url is empty"
        return out
    if not key_present:
        out["reason"] = "provider api key is empty"
        return out

    headers = {"Authorization": f"Bearer {provider.api_key}"}
    url = _models_url_for_provider(provider.base_url)
    client = request.app.state.services.transcription.client
    try:
        resp = await client.get(url, headers=headers, timeout=min(float(provider.timeout_sec or 30), 30.0))
    except Exception as exc:
        out["reason"] = f"validation request failed: {exc.__class__.__name__}"
        return out

    out["status_code"] = resp.status_code
    if 200 <= resp.status_code < 400:
        out["valid"] = True
        out["enabled_for_user"] = True
        out["reason"] = "ok"
        return out

    if resp.status_code in {401, 403}:
        out["reason"] = "api key rejected by provider"
    else:
        out["reason"] = f"provider returned HTTP {resp.status_code}"
    return out


def _config_file_path() -> Path:
    return Path(os.getenv("APP_CONFIG_FILE", "config/config.yml"))


def _load_file_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=500, detail=f"config file is not a mapping: {path}")
    return raw


async def _apply_runtime_settings(request: Request, settings: Settings) -> None:
    current_services: Optional[ServiceContainer] = getattr(request.app.state, "services", None)
    new_services = ServiceContainer(settings=settings)
    request.app.state.settings = settings
    request.app.state.services = new_services
    if current_services is not None:
        await current_services.close()


async def _require_admin(request: Request, admin_token: Optional[str] = Security(_ADMIN_API_KEY)) -> None:
    settings: Settings = request.app.state.settings
    if not settings.admin.enabled:
        raise HTTPException(status_code=404, detail="admin endpoints are disabled")
    if not settings.admin.require_auth:
        return
    expected = settings.admin.token
    provided = admin_token or ""
    if not expected or provided != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")


@app.get("/", include_in_schema=False, summary="User Web UI")
async def ui_user_index() -> FileResponse:
    return FileResponse(_UI_DIR / "user.html")


@app.get("/lab", include_in_schema=False, summary="Lab Web UI")
async def ui_lab_index() -> FileResponse:
    return FileResponse(_UI_DIR / "index.html")


@app.get("/health", response_model=HealthResponse, tags=["health"], summary="Service health")
async def health(request: Request) -> Dict[str, Any]:
    settings: Settings = request.app.state.settings
    media = request.app.state.services.transcription.media
    return {
        "status": "ok",
        "service": settings.app.name,
        "version": settings.app.version,
        "ffmpeg_available": media.ffmpeg_available(),
        "ffprobe_available": media.ffprobe_available(),
        "default_provider": settings.transcription.default_provider,
        "now_utc": datetime.now(timezone.utc),
    }


@app.get("/providers", response_model=ProvidersResponse, tags=["providers"], summary="Configured providers")
async def providers(request: Request) -> Dict[str, Any]:
    settings: Settings = request.app.state.settings

    items = [
        ProviderInfo(name="local", enabled=True, base_url=None, model=settings.local.model_id),
        ProviderInfo(
            name="openai",
            enabled=settings.providers.openai.enabled,
            base_url=settings.providers.openai.base_url if settings.providers.openai.enabled else None,
            model=settings.providers.openai.model,
        ),
        ProviderInfo(
            name="groq",
            enabled=settings.providers.groq.enabled,
            base_url=settings.providers.groq.base_url if settings.providers.groq.enabled else None,
            model=settings.providers.groq.model,
        ),
        ProviderInfo(
            name="custom",
            enabled=settings.providers.custom.enabled,
            base_url=settings.providers.custom.base_url if settings.providers.custom.enabled else None,
            model=settings.providers.custom.model,
        ),
    ]

    return {
        "default_provider": settings.transcription.default_provider,
        "providers": [x.model_dump() for x in items],
    }


@app.get(
    "/providers/status",
    response_model=ProviderRuntimeStatusResponse,
    tags=["providers"],
    summary="Configured providers with runtime key validation",
)
async def provider_status(request: Request) -> Dict[str, Any]:
    settings: Settings = request.app.state.settings

    items: List[Dict[str, Any]] = [
        {
            "name": "local",
            "configured": True,
            "key_present": False,
            "valid": True,
            "enabled_for_user": True,
            "model": settings.local.model_id,
            "base_url": None,
            "status_code": None,
            "reason": "local backend is available",
        }
    ]

    for provider_name, provider in [
        ("openai", settings.providers.openai),
        ("groq", settings.providers.groq),
    ]:
        items.append(
            await _check_openai_compatible_provider(
                request,
                provider_name=provider_name,
                provider=provider,
            )
        )

    return {
        "default_provider": settings.transcription.default_provider,
        "providers": items,
    }


def _local_model_download_plan(model: str) -> Dict[str, Any]:
    requested = str(model or "").strip() or "large-v3"
    canonical = canonicalize_faster_whisper_model_id(requested) or normalize_model_token(requested)
    canonical = {
        "tiny.en": "tiny",
        "base.en": "base",
        "small.en": "small",
        "medium.en": "medium",
        "large": "large-v3",
    }.get(canonical, canonical)

    repo_map: Dict[str, Dict[str, str]] = {
        "tiny": {
            "preset_name": "faster-whisper-tiny",
            "repo_id": "Systran/faster-whisper-tiny",
            "output_subdir": "faster-whisper-tiny",
            "variant": "tiny",
        },
        "base": {
            "preset_name": "faster-whisper-base",
            "repo_id": "Systran/faster-whisper-base",
            "output_subdir": "faster-whisper-base",
            "variant": "base",
        },
        "small": {
            "preset_name": "faster-whisper-small",
            "repo_id": "Systran/faster-whisper-small",
            "output_subdir": "faster-whisper-small",
            "variant": "small",
        },
        "medium": {
            "preset_name": "faster-whisper-medium",
            "repo_id": "Systran/faster-whisper-medium",
            "output_subdir": "faster-whisper-medium",
            "variant": "medium",
        },
        "large-v2": {
            "preset_name": "faster-whisper-large-v2",
            "repo_id": "Systran/faster-whisper-large-v2",
            "output_subdir": "faster-whisper-large-v2",
            "variant": "large",
        },
        "large-v3": {
            "preset_name": "faster-whisper-large-v3",
            "repo_id": "Systran/faster-whisper-large-v3",
            "output_subdir": "faster-whisper-large-v3",
            "variant": "large-v3",
        },
    }
    plan = repo_map.get(canonical)
    if plan is None:
        raise HTTPException(status_code=422, detail=f"unsupported local model for panel download: {requested}")

    meta = WHISPER_VARIANT_METADATA.get(plan["variant"], {})
    estimated_model_bin_mb = meta.get("estimated_model_bin_mb")
    estimated_total_mb = int(round(float(estimated_model_bin_mb or 0) * 1.08 + 15)) if estimated_model_bin_mb else None
    return {
        "model": requested,
        "canonical_model": canonical,
        "revision": "main",
        "estimated_model_bin_mb": estimated_model_bin_mb,
        "estimated_total_mb": estimated_total_mb,
        "estimated_vram_gb": meta.get("estimated_vram_gb"),
        **plan,
    }


def _local_model_aliases(canonical_model: str, output_subdir: str) -> List[str]:
    variant = detect_whisper_variant(canonical_model) or canonical_model
    aliases = {canonical_model, output_subdir, f"faster-whisper-{canonical_model}"}
    aliases.update(VARIANT_TO_LOCAL_DIR_ALIASES.get(variant, []))
    if canonical_model == "large-v2":
        aliases.add("faster-whisper-large-v2")
    if canonical_model == "large-v3":
        aliases.update({"large", "faster-whisper-large", "openai-whisper-large-v3"})
    return sorted(normalize_model_token(x) for x in aliases if x)


def _find_matching_local_model(local_models: List[Dict[str, Any]], plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    canonical = str(plan["canonical_model"])
    aliases = _local_model_aliases(canonical, str(plan["output_subdir"]))
    strict_alias_match = canonical == "large-v2"
    expected_variant = detect_whisper_variant(canonical)

    for item in local_models:
        names = [
            item.get("display_name"),
            item.get("model_id"),
            item.get("path"),
        ]
        normalized_names = [normalize_model_token(str(x)) for x in names if x]
        if any(alias and any(alias in value for value in normalized_names) for alias in aliases):
            return item
        if not strict_alias_match and expected_variant and item.get("variant") == expected_variant:
            return item
    return None


def _local_model_status_payload(request: Request, model: str) -> Dict[str, Any]:
    settings: Settings = request.app.state.settings
    downloads = request.app.state.services.transcription.downloads
    plan = _local_model_download_plan(model or settings.local.model_id)
    items = downloads.list_local_models()
    matched = _find_matching_local_model(items, plan)
    return {
        "model": plan["model"],
        "canonical_model": plan["canonical_model"],
        "present": matched is not None,
        "matched_model": matched,
        "preset_name": plan["preset_name"],
        "repo_id": plan["repo_id"],
        "revision": plan["revision"],
        "output_subdir": plan["output_subdir"],
        "estimated_model_bin_mb": plan["estimated_model_bin_mb"],
        "estimated_total_mb": plan["estimated_total_mb"],
        "estimated_vram_gb": plan["estimated_vram_gb"],
        "hf_token_present": bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")),
        "hf_token_help_url": "https://huggingface.co/settings/tokens",
    }


@app.get(
    "/models/local/status",
    response_model=UserLocalModelStatusResponse,
    tags=["providers"],
    summary="Check whether a panel local model is downloaded",
)
async def user_local_model_status(request: Request, model: str = "large-v3") -> Dict[str, Any]:
    return _local_model_status_payload(request, model)


@app.post(
    "/models/local/download",
    response_model=DownloadBatchResponse,
    tags=["providers"],
    summary="Download a panel local model from Hugging Face",
)
async def user_download_local_model(request: Request, payload: UserLocalModelDownloadRequest) -> Dict[str, Any]:
    status_payload = _local_model_status_payload(request, payload.model)
    if status_payload["present"]:
        return {"total": 0, "items": []}

    downloads = request.app.state.services.transcription.downloads
    jobs = await downloads.create_local_model_jobs(
        preset_name=None,
        repo_id=status_payload["repo_id"],
        revision=status_payload["revision"],
        output_subdir=status_payload["output_subdir"],
        files=None,
        auth_token=(payload.hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or None),
    )
    items = [x.to_dict() for x in jobs]
    return {"total": len(items), "items": items}


@app.get(
    "/models/local/downloads/{job_id}",
    response_model=DownloadJobResponse,
    tags=["providers"],
    summary="Get a panel local model download job",
)
async def user_get_local_model_download(request: Request, job_id: str) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    return downloads.get(job_id).to_dict()


@app.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    tags=["transcription"],
    summary="Transcribe uploaded audio/video",
)
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    provider: Optional[str] = Form(default=None),
    model: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
    prompt: Optional[str] = Form(default=None),
    response_format: Optional[str] = Form(default=None),
    temperature: Optional[float] = Form(default=None),
    word_timestamps: Optional[bool] = Form(default=None),
    segment_timestamps: Optional[bool] = Form(default=None),
    vad_filter: Optional[bool] = Form(default=None),
    beam_size: Optional[int] = Form(default=None),
    best_of: Optional[int] = Form(default=None),
    patience: Optional[float] = Form(default=None),
    condition_on_previous_text: Optional[bool] = Form(default=None),
    initial_prompt: Optional[str] = Form(default=None),
    repetition_penalty: Optional[float] = Form(default=None),
    no_repeat_ngram_size: Optional[int] = Form(default=None),
    compression_ratio_threshold: Optional[float] = Form(default=None),
    log_prob_threshold: Optional[float] = Form(default=None),
    no_speech_threshold: Optional[float] = Form(default=None),
    prompt_reset_on_temperature: Optional[float] = Form(default=None),
    hallucination_silence_threshold: Optional[float] = Form(default=None),
    max_new_tokens: Optional[int] = Form(default=None),
    vad_threshold: Optional[float] = Form(default=None),
    vad_neg_threshold: Optional[float] = Form(default=None),
    vad_min_speech_duration_ms: Optional[int] = Form(default=None),
    vad_min_silence_duration_ms: Optional[int] = Form(default=None),
    vad_speech_pad_ms: Optional[int] = Form(default=None),
    chunking_enabled: Optional[bool] = Form(default=None),
    chunk_minutes: Optional[float] = Form(default=None),
    chunk_overlap_minutes: Optional[float] = Form(default=None),
    chunk_min_duration_minutes: Optional[float] = Form(default=None),
    vocabulary_bias: Optional[str] = Form(default=None),
    x_request_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "provider": provider,
        "model": model,
        "language": language,
        "prompt": prompt,
        "response_format": response_format,
        "temperature": temperature,
        "word_timestamps": word_timestamps,
        "segment_timestamps": segment_timestamps,
        "vad_filter": vad_filter,
        "beam_size": beam_size,
        "best_of": best_of,
        "patience": patience,
        "condition_on_previous_text": condition_on_previous_text,
        "initial_prompt": initial_prompt,
        "repetition_penalty": repetition_penalty,
        "no_repeat_ngram_size": no_repeat_ngram_size,
        "compression_ratio_threshold": compression_ratio_threshold,
        "log_prob_threshold": log_prob_threshold,
        "no_speech_threshold": no_speech_threshold,
        "prompt_reset_on_temperature": prompt_reset_on_temperature,
        "hallucination_silence_threshold": hallucination_silence_threshold,
        "max_new_tokens": max_new_tokens,
        "vad_threshold": vad_threshold,
        "vad_neg_threshold": vad_neg_threshold,
        "vad_min_speech_duration_ms": vad_min_speech_duration_ms,
        "vad_min_silence_duration_ms": vad_min_silence_duration_ms,
        "vad_speech_pad_ms": vad_speech_pad_ms,
        "chunking_enabled": chunking_enabled,
        "chunk_minutes": chunk_minutes,
        "chunk_overlap_minutes": chunk_overlap_minutes,
        "chunk_min_duration_minutes": chunk_min_duration_minutes,
        "vocabulary_bias": vocabulary_bias,
        "request_id": x_request_id,
    }

    output = await request.app.state.services.transcription.transcribe_upload(file, options)
    output.setdefault("metadata", {})["request_id"] = x_request_id
    return output


@app.post(
    "/transcribe/jobs",
    response_model=TranscriptionJobResponse,
    tags=["transcription"],
    summary="Create async transcription job",
)
async def transcribe_job_create(
    request: Request,
    file: UploadFile = File(...),
    provider: Optional[str] = Form(default=None),
    model: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
    prompt: Optional[str] = Form(default=None),
    response_format: Optional[str] = Form(default=None),
    temperature: Optional[float] = Form(default=None),
    word_timestamps: Optional[bool] = Form(default=None),
    segment_timestamps: Optional[bool] = Form(default=None),
    vad_filter: Optional[bool] = Form(default=None),
    beam_size: Optional[int] = Form(default=None),
    best_of: Optional[int] = Form(default=None),
    patience: Optional[float] = Form(default=None),
    condition_on_previous_text: Optional[bool] = Form(default=None),
    initial_prompt: Optional[str] = Form(default=None),
    repetition_penalty: Optional[float] = Form(default=None),
    no_repeat_ngram_size: Optional[int] = Form(default=None),
    compression_ratio_threshold: Optional[float] = Form(default=None),
    log_prob_threshold: Optional[float] = Form(default=None),
    no_speech_threshold: Optional[float] = Form(default=None),
    prompt_reset_on_temperature: Optional[float] = Form(default=None),
    hallucination_silence_threshold: Optional[float] = Form(default=None),
    max_new_tokens: Optional[int] = Form(default=None),
    vad_threshold: Optional[float] = Form(default=None),
    vad_neg_threshold: Optional[float] = Form(default=None),
    vad_min_speech_duration_ms: Optional[int] = Form(default=None),
    vad_min_silence_duration_ms: Optional[int] = Form(default=None),
    vad_speech_pad_ms: Optional[int] = Form(default=None),
    chunking_enabled: Optional[bool] = Form(default=None),
    chunk_minutes: Optional[float] = Form(default=None),
    chunk_overlap_minutes: Optional[float] = Form(default=None),
    chunk_min_duration_minutes: Optional[float] = Form(default=None),
    vocabulary_bias: Optional[str] = Form(default=None),
    x_request_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "provider": provider,
        "model": model,
        "language": language,
        "prompt": prompt,
        "response_format": response_format,
        "temperature": temperature,
        "word_timestamps": word_timestamps,
        "segment_timestamps": segment_timestamps,
        "vad_filter": vad_filter,
        "beam_size": beam_size,
        "best_of": best_of,
        "patience": patience,
        "condition_on_previous_text": condition_on_previous_text,
        "initial_prompt": initial_prompt,
        "repetition_penalty": repetition_penalty,
        "no_repeat_ngram_size": no_repeat_ngram_size,
        "compression_ratio_threshold": compression_ratio_threshold,
        "log_prob_threshold": log_prob_threshold,
        "no_speech_threshold": no_speech_threshold,
        "prompt_reset_on_temperature": prompt_reset_on_temperature,
        "hallucination_silence_threshold": hallucination_silence_threshold,
        "max_new_tokens": max_new_tokens,
        "vad_threshold": vad_threshold,
        "vad_neg_threshold": vad_neg_threshold,
        "vad_min_speech_duration_ms": vad_min_speech_duration_ms,
        "vad_min_silence_duration_ms": vad_min_silence_duration_ms,
        "vad_speech_pad_ms": vad_speech_pad_ms,
        "chunking_enabled": chunking_enabled,
        "chunk_minutes": chunk_minutes,
        "chunk_overlap_minutes": chunk_overlap_minutes,
        "chunk_min_duration_minutes": chunk_min_duration_minutes,
        "vocabulary_bias": vocabulary_bias,
        "request_id": x_request_id,
    }
    job = await request.app.state.services.transcription.create_transcription_job(file, options)
    return job.to_dict()


@app.get(
    "/transcribe/jobs",
    response_model=TranscriptionJobListResponse,
    tags=["transcription"],
    summary="List async transcription jobs",
)
async def transcribe_job_list(request: Request) -> Dict[str, Any]:
    items = [x.to_dict() for x in request.app.state.services.transcription.list_transcription_jobs()]
    return {"total": len(items), "items": items}


@app.get(
    "/transcribe/jobs/{job_id}",
    response_model=TranscriptionJobResponse,
    tags=["transcription"],
    summary="Get async transcription job",
)
async def transcribe_job_get(request: Request, job_id: str) -> Dict[str, Any]:
    job = request.app.state.services.transcription.get_transcription_job(job_id)
    return job.to_dict()


@app.post(
    "/transcribe/jobs/{job_id}/cancel",
    response_model=TranscriptionJobResponse,
    tags=["transcription"],
    summary="Cancel async transcription job",
)
async def transcribe_job_cancel(request: Request, job_id: str) -> Dict[str, Any]:
    job = request.app.state.services.transcription.cancel_transcription_job(job_id)
    return job.to_dict()


@app.get(
    "/admin/system/config-effective",
    response_model=EffectiveConfigResponse,
    tags=["admin-system"],
    dependencies=[Depends(_require_admin)],
    summary="Resolved effective config",
)
async def admin_config(request: Request) -> Dict[str, Any]:
    settings: Settings = request.app.state.settings
    return {
        "generated_at": now_utc(),
        "precedence": "env > config.yml > defaults",
        "config": _redacted_config(settings),
    }


@app.get(
    "/admin/system/config-editable",
    response_model=EditableConfigResponse,
    tags=["admin-system"],
    dependencies=[Depends(_require_admin)],
    summary="Editable config payload (file + effective)",
)
async def admin_config_editable(request: Request) -> Dict[str, Any]:
    cfg_path = _config_file_path()
    settings: Settings = request.app.state.settings
    file_config = _load_file_config(cfg_path)
    return {
        "generated_at": now_utc(),
        "config_path": str(cfg_path),
        "file_config": file_config,
        "effective_config": settings.model_dump(),
        "precedence": "env > config.yml > defaults",
    }


@app.put(
    "/admin/system/config-editable",
    response_model=EditableConfigResponse,
    tags=["admin-system"],
    dependencies=[Depends(_require_admin)],
    summary="Update config file and reload runtime settings",
)
async def admin_config_editable_update(request: Request, payload: EditableConfigUpdateRequest) -> Dict[str, Any]:
    cfg_path = _config_file_path()

    Settings.model_validate(payload.config)

    if payload.persist_to_file:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload.config, f, allow_unicode=True, sort_keys=False)

    if payload.reload_runtime:
        if payload.persist_to_file:
            get_settings.cache_clear()
            refreshed = load_settings(config_file=str(cfg_path))
        else:
            refreshed = Settings.model_validate(payload.config)
        await _apply_runtime_settings(request, refreshed)

    settings: Settings = request.app.state.settings
    file_config = _load_file_config(cfg_path)
    return {
        "generated_at": now_utc(),
        "config_path": str(cfg_path),
        "file_config": file_config,
        "effective_config": settings.model_dump(),
        "precedence": "env > config.yml > defaults",
    }


@app.get(
    "/admin/models/presets",
    response_model=LocalModelPresetsResponse,
    tags=["admin-models"],
    dependencies=[Depends(_require_admin)],
    summary="List model presets",
)
async def admin_model_presets() -> Dict[str, Any]:
    return {
        "total": len(MODEL_PRESETS),
        "items": MODEL_PRESETS,
    }


@app.get(
    "/admin/models/local",
    response_model=LocalModelsResponse,
    tags=["admin-models"],
    dependencies=[Depends(_require_admin)],
    summary="List downloaded local models",
)
async def admin_local_models(request: Request) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    items = downloads.list_local_models()
    return {
        "total": len(items),
        "model_root": request.app.state.settings.storage.model_dir,
        "items": items,
    }


@app.get(
    "/admin/models/remote/repos",
    response_model=RemoteModelRepoListResponse,
    tags=["admin-models"],
    dependencies=[Depends(_require_admin)],
    summary="Search remote model repositories from HuggingFace API",
)
async def admin_remote_model_repos(
    request: Request,
    query: str = "faster-whisper",
    limit: int = 30,
) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    items = await downloads.search_remote_model_repos(query=query, limit=limit)
    return {"total": len(items), "items": items}


@app.get(
    "/admin/models/remote/files",
    response_model=RemoteModelFilesResponse,
    tags=["admin-models"],
    dependencies=[Depends(_require_admin)],
    summary="Fetch remote model file list from HuggingFace API",
)
async def admin_remote_model_files(
    request: Request,
    repo_id: str,
    revision: str = "main",
) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    items = await downloads.fetch_remote_repo_files(repo_id=repo_id, revision=revision)
    recommended = downloads.choose_download_files([x["path"] for x in items], requested_files=None)
    return {
        "repo_id": repo_id,
        "revision": revision,
        "total": len(items),
        "recommended_files": recommended,
        "items": items,
    }


@app.post(
    "/admin/models/local/download",
    response_model=DownloadBatchResponse,
    tags=["admin-models"],
    dependencies=[Depends(_require_admin)],
    summary="Download local model files from HuggingFace",
)
async def admin_download_local_model(request: Request, payload: LocalModelDownloadRequest) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    jobs = await downloads.create_local_model_jobs(
        preset_name=payload.preset_name,
        repo_id=payload.repo_id,
        revision=payload.revision,
        output_subdir=payload.output_subdir,
        files=payload.files,
    )
    items = [x.to_dict() for x in jobs]
    return {"total": len(items), "items": items}


@app.post(
    "/admin/models/url/huggingface-file",
    response_model=ModelUrlResponse,
    tags=["admin-models"],
    dependencies=[Depends(_require_admin)],
    summary="Build direct URL for a HuggingFace file",
)
async def admin_build_hf_file_url(request: Request, payload: HuggingFaceFileUrlRequest) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    out = await downloads.resolve_hf_file_url(
        repo_id=payload.repo_id,
        filename=payload.filename,
        revision=payload.revision,
    )
    return out


@app.post(
    "/admin/downloads",
    response_model=DownloadJobResponse,
    tags=["admin-downloads"],
    dependencies=[Depends(_require_admin)],
    summary="Create model download job",
)
async def admin_create_download(request: Request, payload: DownloadJobCreateRequest) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads

    if payload.source == "url":
        if not payload.url:
            raise HTTPException(status_code=422, detail="url is required when source=url")
        requested_url = payload.url
        resolved_url = payload.url
    else:
        if not payload.repo_id or not payload.filename:
            raise HTTPException(status_code=422, detail="repo_id and filename are required for source=huggingface_file")
        built = await downloads.resolve_hf_file_url(
            repo_id=payload.repo_id,
            filename=payload.filename,
            revision=payload.revision,
        )
        requested_url = f"hf://{payload.repo_id}@{payload.revision}/{payload.filename}"
        resolved_url = built["url"]

    job = await downloads.create_job(
        source=payload.source,
        requested_url=requested_url,
        resolved_url=resolved_url,
        output_subdir=payload.output_subdir,
        output_filename=payload.output_filename,
    )
    return job.to_dict()


@app.get(
    "/admin/downloads",
    response_model=DownloadListResponse,
    tags=["admin-downloads"],
    dependencies=[Depends(_require_admin)],
    summary="List download jobs",
)
async def admin_list_downloads(request: Request) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    items = [x.to_dict() for x in downloads.list()]
    return {"total": len(items), "items": items}


@app.get(
    "/admin/downloads/{job_id}",
    response_model=DownloadJobResponse,
    tags=["admin-downloads"],
    dependencies=[Depends(_require_admin)],
    summary="Get download job",
)
async def admin_get_download(request: Request, job_id: str) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    return downloads.get(job_id).to_dict()


@app.post(
    "/admin/downloads/{job_id}/cancel",
    response_model=DownloadJobResponse,
    tags=["admin-downloads"],
    dependencies=[Depends(_require_admin)],
    summary="Cancel download job",
)
async def admin_cancel_download(request: Request, job_id: str) -> Dict[str, Any]:
    downloads = request.app.state.services.transcription.downloads
    job = downloads.cancel(job_id)
    return job.to_dict()
