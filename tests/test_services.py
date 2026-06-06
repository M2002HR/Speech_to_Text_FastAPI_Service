from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException
import pytest

from api.app.config import Settings
from api.app.services import APITranscriber, DownloadManager, LocalTranscriber, TranscriptionService, normalize_proxy_env


def _settings() -> Settings:
    s = Settings()
    s.downloads.allowed_domains = ["huggingface.co"]
    return s


def _run(coro):
    return asyncio.run(coro)


def test_build_hf_url() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    out = mgr.build_hf_file_url(
        repo_id="openai/whisper-large-v3",
        filename="config.json",
        revision="main",
    )
    assert out["source"] == "official"
    assert out["url"].startswith("https://huggingface.co/")


def test_domain_restriction() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    try:
        _run(
            mgr.create_job(
                source="url",
                requested_url="https://example.com/file.bin",
                resolved_url="https://example.com/file.bin",
                output_subdir="x",
                output_filename="a.bin",
            )
        )
        assert False, "expected domain restriction"
    except Exception as exc:
        assert "not in DOWNLOADS_ALLOWED_DOMAINS" in str(exc)


def test_create_local_model_jobs_with_preset() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    async def _fake_fetch_remote_repo_files(**kwargs):
        return [
            {"path": "config.json", "size_bytes": 100, "lfs_size_bytes": None},
            {"path": "model.bin", "size_bytes": 1000, "lfs_size_bytes": 1000},
            {"path": "tokenizer.json", "size_bytes": 100, "lfs_size_bytes": None},
            {"path": "vocabulary.txt", "size_bytes": 100, "lfs_size_bytes": None},
        ]

    async def _fake_resolve_hf_file_url(**kwargs):
        return {"source": "official", "url": f"https://huggingface.co/{kwargs['repo_id']}/resolve/{kwargs['revision']}/{kwargs['filename']}"}

    mgr.fetch_remote_repo_files = _fake_fetch_remote_repo_files  # type: ignore[assignment]
    mgr.resolve_hf_file_url = _fake_resolve_hf_file_url  # type: ignore[assignment]

    created = _run(
        mgr.create_local_model_jobs(
            preset_name="faster-whisper-small",
            repo_id=None,
            revision="main",
            output_subdir=None,
            files=None,
        )
    )
    assert len(created) == 4
    assert all("huggingface.co" in job.resolved_url for job in created)


def test_create_local_model_jobs_with_explicit_files_without_remote_fetch() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    async def _boom_fetch_remote_repo_files(**kwargs):
        raise AssertionError("should not be called when explicit files are provided")

    async def _fake_resolve_hf_file_url(**kwargs):
        return {"source": "official", "url": f"https://huggingface.co/{kwargs['repo_id']}/resolve/{kwargs['revision']}/{kwargs['filename']}"}

    mgr.fetch_remote_repo_files = _boom_fetch_remote_repo_files  # type: ignore[assignment]
    mgr.resolve_hf_file_url = _fake_resolve_hf_file_url  # type: ignore[assignment]

    created = _run(
        mgr.create_local_model_jobs(
            preset_name=None,
            repo_id="Systran/faster-whisper-small",
            revision="main",
            output_subdir="x",
            files=["config.json", "model.bin"],
        )
    )
    assert len(created) == 2


def test_create_local_model_jobs_keeps_hf_token_private() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    async def _fake_resolve_hf_file_url(**kwargs):
        return {"source": "official", "url": f"https://huggingface.co/{kwargs['repo_id']}/resolve/{kwargs['revision']}/{kwargs['filename']}"}

    mgr.resolve_hf_file_url = _fake_resolve_hf_file_url  # type: ignore[assignment]

    created = _run(
        mgr.create_local_model_jobs(
            preset_name=None,
            repo_id="Systran/faster-whisper-base",
            revision="main",
            output_subdir="x",
            files=["config.json"],
            auth_token="hf_secret",
        )
    )
    assert len(created) == 1
    assert created[0].auth_token == "hf_secret"
    assert "auth_token" not in created[0].to_dict()


def test_create_local_model_jobs_fallback_when_remote_unreachable() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    async def _fake_fetch_remote_repo_files(**kwargs):
        raise HTTPException(status_code=503, detail="network")

    async def _fake_resolve_hf_file_url(**kwargs):
        return {"source": "official", "url": f"https://huggingface.co/{kwargs['repo_id']}/resolve/{kwargs['revision']}/{kwargs['filename']}"}

    mgr.fetch_remote_repo_files = _fake_fetch_remote_repo_files  # type: ignore[assignment]
    mgr.resolve_hf_file_url = _fake_resolve_hf_file_url  # type: ignore[assignment]

    created = _run(
        mgr.create_local_model_jobs(
            preset_name=None,
            repo_id="Systran/faster-whisper-small",
            revision="main",
            output_subdir="x",
            files=None,
        )
    )
    assert len(created) == 4


def test_list_local_models_detects_faster_whisper_layout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = _settings()
        settings.storage.model_dir = tmp
        mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

        model_dir = Path(tmp) / "faster-whisper-small"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
        (model_dir / "model.bin").write_bytes(b"1234")
        (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        (model_dir / "vocabulary.txt").write_text("a", encoding="utf-8")

        items = mgr.list_local_models()
        assert len(items) == 1
        assert items[0]["display_name"] == "faster-whisper-small"
        assert items[0]["variant"] == "small"
        assert items[0]["parameters_million"] == 244


def test_local_transcriber_resolve_model_id_alias_and_local_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = _settings()
        settings.storage.model_dir = tmp
        transcriber = LocalTranscriber(settings)

        local_dir = Path(tmp) / "faster-whisper-tiny"
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "config.json").write_text("{}", encoding="utf-8")
        (local_dir / "model.bin").write_bytes(b"x")
        (local_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        (local_dir / "vocabulary.txt").write_text("a", encoding="utf-8")

        assert transcriber._resolve_model_id("faster-whisper-tiny") == str(local_dir)
        assert transcriber._resolve_model_id("Systran/faster-whisper-small") == "small"

        small_dir = Path(tmp) / "faster-whisper-small"
        small_dir.mkdir(parents=True, exist_ok=True)
        (small_dir / "config.json").write_text("{}", encoding="utf-8")
        (small_dir / "model.bin").write_bytes(b"x")
        (small_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        (small_dir / "vocabulary.txt").write_text("a", encoding="utf-8")
        assert transcriber._resolve_model_id("small") == str(small_dir)


@pytest.mark.parametrize(
    "input_model,expected_model",
    [
        ("faster-whisper-tiny", "tiny"),
        ("Systran/faster-whisper-base", "base"),
        ("Systran/faster-whisper-small.en", "small.en"),
        ("Systran/faster-whisper-medium", "medium"),
        ("Systran/faster-whisper-large-v2", "large-v2"),
        ("openai/whisper-large-v3", "large-v3"),
        ("openai-whisper-large-v3", "large-v3"),
        ("openai/whisper-large-v3-turbo", "large-v3-turbo"),
        ("distil-whisper/distil-large-v3.5", "distil-large-v3.5"),
        ("systran/faster-distil-whisper-large-v2", "distil-large-v2"),
    ],
)
def test_local_transcriber_resolve_model_id_canonical_aliases(input_model: str, expected_model: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = _settings()
        settings.storage.model_dir = tmp
        transcriber = LocalTranscriber(settings)
        assert transcriber._resolve_model_id(input_model) == expected_model


def test_local_transcriber_resolve_model_id_prefers_local_dir_for_large_v2() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = _settings()
        settings.storage.model_dir = tmp
        transcriber = LocalTranscriber(settings)

        local_dir = Path(tmp) / "Systran--faster-whisper-large-v2"
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "config.json").write_text("{}", encoding="utf-8")
        (local_dir / "model.bin").write_bytes(b"x")
        (local_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        (local_dir / "vocabulary.txt").write_text("a", encoding="utf-8")

        assert transcriber._resolve_model_id("Systran/faster-whisper-large-v2") == str(local_dir)


def test_api_transcription_chunks_for_visible_progress() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = _settings()
        settings.storage.runtime_dir = tmp
        settings.storage.output_dir = tmp
        svc = TranscriptionService(settings)
        prepared = Path(tmp) / "input.wav"
        prepared.write_bytes(b"fake")
        calls = []
        updates = []
        partials = []

        async def _fake_extract_audio_window(_input_path: Path, start_sec: float, end_sec: float) -> Path:
            out = Path(tmp) / f"chunk-{len(calls)}.wav"
            out.write_bytes(b"chunk")
            return out

        class _FakeAPI:
            async def transcribe(self, provider_name: str, audio_path: Path, options):
                calls.append((provider_name, audio_path.name, dict(options)))
                idx = len(calls)
                return {
                    "text": f"part {idx}",
                    "language": "en",
                    "duration_seconds": 120.0,
                    "segments": None,
                    "words": None,
                    "usage": {
                        "provider": provider_name,
                        "model": str(options.get("model") or "whisper-large-v3"),
                        "audio_seconds": 120.0,
                        "process_ms": 100.0,
                    },
                    "metadata": {},
                }

        svc.media.extract_audio_window = _fake_extract_audio_window  # type: ignore[assignment]
        svc.api = _FakeAPI()  # type: ignore[assignment]
        try:
            out = _run(
                svc._transcribe_api_with_optional_chunking(
                    provider="groq",
                    prepared_path=prepared,
                    options={
                        "model": "whisper-large-v3",
                        "chunking_enabled": True,
                        "chunk_minutes": 10,
                        "chunk_overlap_minutes": 5,
                        "segment_timestamps": True,
                    },
                    duration=300.0,
                    checkpoint_id="job-checkpoint",
                    progress_cb=lambda p: updates.append(p),
                    partial_text_cb=lambda text: partials.append(text),
                )
            )
            calls_after_first = len(calls)
            resumed = _run(
                svc._transcribe_api_with_optional_chunking(
                    provider="groq",
                    prepared_path=prepared,
                    options={
                        "model": "whisper-large-v3",
                        "chunking_enabled": True,
                        "chunk_minutes": 10,
                        "chunk_overlap_minutes": 5,
                        "segment_timestamps": True,
                    },
                    duration=300.0,
                    checkpoint_id="job-checkpoint",
                    progress_cb=lambda p: updates.append(p),
                    partial_text_cb=lambda text: partials.append(text),
                )
            )
        finally:
            _run(svc.close())

        assert len(calls) >= 2
        assert len(calls) == calls_after_first
        assert updates
        assert updates[-1] >= 99.0
        assert partials
        assert "part" in out["text"]
        assert resumed["text"] == out["text"]
        assert out["metadata"]["chunking"]["used"] is True
        assert out["metadata"]["chunking"]["progress_mode"] == "time-window-chunks"


def test_api_transcriber_rotates_provider_keys_on_rate_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings = _settings()
        settings.providers.groq.enabled = True
        settings.providers.groq.api_key = "key-1"
        settings.providers.groq.api_keys = ["key-2"]
        settings.providers.groq.base_url = "https://api.groq.com/openai"
        settings.providers.groq.model = "whisper-large-v3"
        audio = Path(tmp) / "a.wav"
        audio.write_bytes(b"wav")
        seen_headers = []

        class _Resp:
            def __init__(self, status_code: int, payload=None, text: str = "") -> None:
                self.status_code = status_code
                self._payload = payload or {}
                self.text = text
                self.headers = {"content-type": "application/json"}

            def json(self):
                return self._payload

        class _Client:
            async def post(self, *args, **kwargs):
                auth = kwargs["headers"]["Authorization"]
                seen_headers.append(auth)
                if auth.endswith("key-1"):
                    return _Resp(429, text='{"error":"rate limit"}')
                return _Resp(200, {"text": "ok", "duration": 1.0, "language": "en"})

        transcriber = APITranscriber(settings, _Client())  # type: ignore[arg-type]
        out = _run(transcriber.transcribe("groq", audio, {"model": "whisper-large-v3"}))

        assert out["text"] == "ok"
        assert seen_headers == ["Bearer key-1", "Bearer key-2"]
        assert out["metadata"]["provider_key_index"] == 2


def test_local_transcriber_transcribe_uses_duration_hint_for_progress() -> None:
    settings = _settings()
    transcriber = LocalTranscriber(settings)

    class _Seg:
        def __init__(self, seg_id: int, start: float, end: float, text: str):
            self.id = seg_id
            self.start = start
            self.end = end
            self.text = text
            self.avg_logprob = None
            self.no_speech_prob = None
            self.words = []

    class _Info:
        duration = None
        language = "fa"

    class _Model:
        def transcribe(self, _path: str, **_kwargs):
            return iter([_Seg(0, 0.0, 1.0, "a"), _Seg(1, 1.0, 2.0, "b")]), _Info()

    async def _fake_get_model(_model_id: str):
        return _Model()

    transcriber._get_model = _fake_get_model  # type: ignore[method-assign]
    updates = []
    out = _run(
        transcriber.transcribe(
            Path("/tmp/fake.wav"),
            {"model": "small", "word_timestamps": False, "segment_timestamps": True},
            duration_hint=2.0,
            progress_cb=lambda p: updates.append(p),
        )
    )
    assert out["text"] == "a b"
    assert updates
    assert updates[-1] >= 99.0


def test_normalize_proxy_env_socks_scheme(monkeypatch) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:2080/")
    normalize_proxy_env()
    assert (os.getenv("ALL_PROXY") or "").startswith("socks5://")


def test_consume_segments_iter_reports_progress() -> None:
    settings = _settings()
    transcriber = LocalTranscriber(settings)
    updates = []

    class _Seg:
        def __init__(self, end: float):
            self.end = end

    out = transcriber._consume_segments_iter(
        iter([_Seg(1.0), _Seg(2.5), _Seg(4.0)]),
        duration_for_progress=4.0,
        progress_cb=lambda p: updates.append(p),
    )
    assert len(out) == 3
    assert updates
    assert updates[-1] >= 99.0
