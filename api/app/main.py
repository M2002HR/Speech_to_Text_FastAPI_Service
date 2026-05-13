from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Security, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .schemas import (
    DownloadBatchResponse,
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
    TranscriptionJobListResponse,
    TranscriptionJobResponse,
    TranscriptionResponse,
)
from .services import MODEL_PRESETS, ServiceContainer, now_utc

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


@app.get("/", include_in_schema=False, summary="Web UI")
async def ui_index() -> FileResponse:
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
