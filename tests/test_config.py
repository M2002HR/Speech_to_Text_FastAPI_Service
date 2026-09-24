from __future__ import annotations

import os
import textwrap

import pytest

from api.app.config import Settings, configure_outbound_proxy_env, load_settings


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


def test_outbound_socks_proxy_is_applied_to_standard_environment(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://old-proxy:8080")
    settings = Settings.model_validate(
        {
            "network": {
                "proxy_enabled": True,
                "proxy_url": "socks5h://127.0.0.1:2080",
                "no_proxy": "localhost,127.0.0.1,::1",
            }
        }
    )

    configure_outbound_proxy_env(settings)

    assert os.environ["HTTP_PROXY"] == "socks5h://127.0.0.1:2080"
    assert os.environ["HTTPS_PROXY"] == "socks5h://127.0.0.1:2080"
    assert os.environ["ALL_PROXY"] == "socks5h://127.0.0.1:2080"
    assert os.environ["NO_PROXY"] == "localhost,127.0.0.1,::1"


def test_disabling_outbound_proxy_clears_inherited_proxy_environment(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://old-proxy:8080")
    monkeypatch.setenv("ALL_PROXY", "socks5://old-proxy:1080")

    configure_outbound_proxy_env(Settings())

    assert "HTTPS_PROXY" not in os.environ
    assert "ALL_PROXY" not in os.environ
