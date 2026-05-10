from __future__ import annotations

import asyncio

from api.app.config import Settings
from api.app.services import DownloadManager


def _settings() -> Settings:
    s = Settings()
    s.downloads.allowed_domains = ["huggingface.co", "hf.devneeds.ir"]
    return s


def _run(coro):
    return asyncio.run(coro)


def test_build_hf_mirror_url() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    out = mgr.build_hf_file_url(
        repo_id="openai/whisper-large-v3",
        filename="config.json",
        revision="main",
        use_mirror=True,
    )
    assert out["source"] == "mirror"
    assert out["url"].startswith("https://hf.devneeds.ir/")


def test_build_hf_official_url() -> None:
    settings = _settings()
    mgr = DownloadManager(settings=settings, client=None)  # type: ignore[arg-type]

    out = mgr.build_hf_file_url(
        repo_id="openai/whisper-large-v3",
        filename="config.json",
        revision="main",
        use_mirror=False,
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
