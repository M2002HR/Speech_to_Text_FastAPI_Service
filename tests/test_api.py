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


def test_admin_download_create_with_hf_source(client_factory) -> None:
    with client_factory() as client:
        mgr = client.app.state.services.transcription.downloads
        mgr.create_job = _fake_create_job

        resp = client.post(
            "/admin/downloads",
            json={
                "source": "huggingface_file",
                "repo_id": "openai/whisper-large-v3",
                "filename": "config.json",
                "revision": "main",
                "use_mirror": True,
                "output_subdir": "whisper",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "job123"
        assert "hf.devneeds.ir" in body["resolved_url"]


def test_admin_auth_required(client_factory) -> None:
    with client_factory({"ADMIN_REQUIRE_AUTH": "true", "ADMIN_TOKEN": "secret"}) as client:
        denied = client.get("/admin/system/config-effective")
        assert denied.status_code == 401

        allowed = client.get("/admin/system/config-effective", headers={"x-admin-token": "secret"})
        assert allowed.status_code == 200
