from __future__ import annotations

from typing import Any, Dict


async def _fake_transcribe_upload(file, options):
    return {
        "text": "hello world",
        "language": "en",
        "duration_seconds": 1.23,
        "segments": [{"id": 0, "start": 0.0, "end": 1.23, "text": "hello world"}],
        "words": [{"start": 0.0, "end": 0.5, "word": "hello", "probability": 0.9}],
        "usage": {"provider": "local", "model": "small", "audio_seconds": 1.23, "process_ms": 10.0},
        "metadata": {},
    }


async def _fake_create_job(**kwargs):
    class _Job:
        def to_dict(self) -> Dict[str, Any]:
            return {
                "job_id": "job123",
                "status": "pending",
                "source": kwargs["source"],
                "requested_url": kwargs["requested_url"],
                "resolved_url": kwargs["resolved_url"],
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": None,
                "completed_at": None,
                "bytes_total": None,
                "bytes_downloaded": 0,
                "progress_percent": None,
                "output_path": None,
                "error": None,
            }

    return _Job()


async def _fake_resolve_hf_file_url(**kwargs):
    return {
        "source": "official",
        "url": f"https://huggingface.co/{kwargs['repo_id']}/resolve/{kwargs['revision']}/{kwargs['filename']}",
    }


async def _fake_create_local_model_jobs(**kwargs):
    class _Job:
        def __init__(self, idx: int) -> None:
            self.idx = idx

        def to_dict(self) -> Dict[str, Any]:
            return {
                "job_id": f"job{self.idx}",
                "status": "pending",
                "source": "huggingface_file",
                "requested_url": "hf://Systran/faster-whisper-small@main/config.json",
                "resolved_url": "https://huggingface.co/Systran/faster-whisper-small/resolve/main/config.json",
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": None,
                "completed_at": None,
                "bytes_total": None,
                "bytes_downloaded": 0,
                "progress_percent": None,
                "output_path": None,
                "error": None,
            }

    return [_Job(1), _Job(2)]


async def _fake_create_transcription_job(file, options):
    class _Job:
        def to_dict(self) -> Dict[str, Any]:
            return {
                "job_id": "trjob1",
                "status": "running",
                "provider": str(options.get("provider") or "local"),
                "model": str(options.get("model") or "tiny"),
                "source_filename": "a.wav",
                "source_content_type": "audio/wav",
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:00:01Z",
                "completed_at": None,
                "progress_percent": 42.0,
                "stage": "transcribing",
                "error": None,
                "result": None,
            }

    return _Job()


def test_health_and_providers(client_factory) -> None:
    with client_factory() as client:
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["status"] == "ok"

        p = client.get("/providers")
        assert p.status_code == 200
        assert p.json()["default_provider"] == "local"


def test_transcribe_endpoint_mocked(client_factory) -> None:
    with client_factory() as client:
        client.app.state.services.transcription.transcribe_upload = _fake_transcribe_upload

        files = {"file": ("a.wav", b"RIFFfake", "audio/wav")}
        resp = client.post("/transcribe", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "hello world"
        assert body["usage"]["provider"] == "local"


def test_transcribe_job_endpoints_mocked(client_factory) -> None:
    with client_factory() as client:
        svc = client.app.state.services.transcription
        svc.create_transcription_job = _fake_create_transcription_job  # type: ignore[assignment]
        svc.get_transcription_job = lambda job_id: type("X", (), {  # type: ignore[assignment]
            "to_dict": lambda self: {
                "job_id": job_id,
                "status": "completed",
                "provider": "local",
                "model": "tiny",
                "source_filename": "a.wav",
                "source_content_type": "audio/wav",
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:00:01Z",
                "completed_at": "2026-01-01T00:00:10Z",
                "progress_percent": 100.0,
                "stage": "completed",
                "error": None,
                "result": {"text": "ok", "usage": {"provider": "local", "model": "tiny", "audio_seconds": 1, "process_ms": 1}},
            }
        })()
        svc.list_transcription_jobs = lambda: [svc.get_transcription_job("trjob1")]  # type: ignore[assignment]

        files = {"file": ("a.wav", b"RIFFfake", "audio/wav")}
        created = client.post("/transcribe/jobs", files=files, data={"provider": "local", "model": "tiny"})
        assert created.status_code == 200
        assert created.json()["job_id"] == "trjob1"

        listed = client.get("/transcribe/jobs")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        fetched = client.get("/transcribe/jobs/trjob1")
        assert fetched.status_code == 200
        assert fetched.json()["status"] == "completed"


def test_admin_download_create_with_hf_source(client_factory) -> None:
    with client_factory() as client:
        mgr = client.app.state.services.transcription.downloads
        mgr.create_job = _fake_create_job
        mgr.resolve_hf_file_url = _fake_resolve_hf_file_url  # type: ignore[assignment]

        resp = client.post(
            "/admin/downloads",
            json={
                "source": "huggingface_file",
                "repo_id": "openai/whisper-large-v3",
                "filename": "config.json",
                "revision": "main",
                "output_subdir": "whisper",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "job123"
        assert "huggingface.co" in body["resolved_url"]


def test_admin_auth_required(client_factory) -> None:
    with client_factory({"ADMIN_REQUIRE_AUTH": "true", "ADMIN_TOKEN": "secret"}) as client:
        denied = client.get("/admin/system/config-effective")
        assert denied.status_code == 401

        allowed = client.get("/admin/system/config-effective", headers={"x-admin-token": "secret"})
        assert allowed.status_code == 200


def test_admin_local_models_and_batch_download(client_factory) -> None:
    with client_factory() as client:
        mgr = client.app.state.services.transcription.downloads
        mgr.list_local_models = lambda: [  # type: ignore[assignment]
            {
                "model_id": "/tmp/runtime/models/faster-whisper-small",
                "display_name": "faster-whisper-small",
                "path": "/tmp/runtime/models/faster-whisper-small",
                "total_size_bytes": 123,
                "file_count": 5,
                "updated_at": "2026-01-01T00:00:00Z",
                "files": [{"path": "config.json", "size_bytes": 10}],
            }
        ]
        mgr.create_local_model_jobs = _fake_create_local_model_jobs  # type: ignore[assignment]

        local_resp = client.get("/admin/models/local")
        assert local_resp.status_code == 200
        assert local_resp.json()["total"] == 1

        dl_resp = client.post(
            "/admin/models/local/download",
            json={
                "preset_name": "faster-whisper-small",
                "revision": "main",
                "output_subdir": "faster-whisper-small",
            },
        )
        assert dl_resp.status_code == 200
        assert dl_resp.json()["total"] == 2


def test_admin_remote_models_endpoints(client_factory) -> None:
    with client_factory() as client:
        mgr = client.app.state.services.transcription.downloads
        async def _fake_search_remote_model_repos(**kwargs):
            return [{"repo_id": "Systran/faster-whisper-tiny", "downloads": 1, "likes": 1, "last_modified": "2026-01-01T00:00:00Z", "private": False, "gated": False}]

        async def _fake_fetch_remote_repo_files(**kwargs):
            return [
                {"path": "config.json", "size_bytes": 100, "lfs_size_bytes": None},
                {"path": "model.bin", "size_bytes": 1000, "lfs_size_bytes": 1000},
            ]

        mgr.search_remote_model_repos = _fake_search_remote_model_repos  # type: ignore[assignment]
        mgr.fetch_remote_repo_files = _fake_fetch_remote_repo_files  # type: ignore[assignment]

        repos_resp = client.get("/admin/models/remote/repos?query=faster-whisper&limit=5")
        assert repos_resp.status_code == 200
        assert repos_resp.json()["total"] == 1

        files_resp = client.get("/admin/models/remote/files?repo_id=Systran/faster-whisper-tiny&revision=main")
        assert files_resp.status_code == 200
        assert files_resp.json()["recommended_files"] == ["config.json", "model.bin"]
