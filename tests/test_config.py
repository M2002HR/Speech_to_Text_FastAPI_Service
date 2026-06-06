from __future__ import annotations

import textwrap

import pytest

from api.app.config import Settings, load_settings


def test_default_settings() -> None:
    s = Settings()
    assert s.transcription.default_provider == "local"
    assert s.storage.max_upload_mb > 0
    assert s.mirrors.huggingface_base.startswith("https://")


def test_load_settings_env_override(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(
        textwrap.dedent(
            """
            app:
              port: 1111
            storage:
              max_upload_mb: 100
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("APP_PORT", "9999")
    monkeypatch.setenv("STORAGE_MAX_UPLOAD_MB", "256")
    monkeypatch.setenv("PROVIDER_OPENAI_ENABLED", "false")

    s = load_settings(config_file=str(cfg))
    assert s.app.port == 9999
    assert s.storage.max_upload_mb == 256


def test_openai_enabled_allows_empty_key_for_panel_setup(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(
        textwrap.dedent(
            """
            providers:
              openai:
                enabled: true
                base_url: https://api.openai.com
                api_key: ""
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PROVIDER_OPENAI_ENABLED", "true")
    s = load_settings(config_file=str(cfg))
    assert s.providers.openai.enabled is True
    assert s.providers.openai.all_api_keys() == []


def test_openai_enabled_requires_base_url() -> None:
    data = Settings().model_dump()
    data["providers"]["openai"]["enabled"] = True
    data["providers"]["openai"]["base_url"] = ""
    with pytest.raises(ValueError, match="providers.openai"):
        Settings.model_validate(data)
