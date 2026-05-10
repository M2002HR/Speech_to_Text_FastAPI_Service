from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app.config import get_settings
from api.app.main import app


BASE_ENV: Dict[str, str] = {
    "ADMIN_ENABLED": "true",
    "ADMIN_REQUIRE_AUTH": "false",
    "ADMIN_TOKEN": "",
    "MIRRORS_HUGGINGFACE_MIRROR_BASE": "https://hf.devneeds.ir",
    "MIRRORS_HUGGINGFACE_BASE": "https://huggingface.co",
    "DOWNLOADS_ENABLED": "true",
    "DOWNLOADS_ALLOWED_DOMAINS": "huggingface.co,hf.devneeds.ir",
    "PROVIDER_OPENAI_ENABLED": "false",
    "PROVIDER_GROQ_ENABLED": "false",
    "PROVIDER_CUSTOM_ENABLED": "false",
}


@contextmanager
def client_with_env(overrides: Dict[str, str] | None = None) -> Iterator[TestClient]:
    overrides = overrides or {}
    touched: Dict[str, str | None] = {}

    with tempfile.TemporaryDirectory() as tmp:
        runtime = os.path.join(tmp, "runtime")
        uploads = os.path.join(runtime, "uploads")
        outputs = os.path.join(runtime, "outputs")
        models = os.path.join(runtime, "models")

        env_values = {
            **BASE_ENV,
            "STORAGE_RUNTIME_DIR": runtime,
            "STORAGE_UPLOAD_DIR": uploads,
            "STORAGE_OUTPUT_DIR": outputs,
            "STORAGE_MODEL_DIR": models,
            **overrides,
        }

        for key, value in env_values.items():
            touched[key] = os.environ.get(key)
            os.environ[key] = value

        get_settings.cache_clear()
        try:
            with TestClient(app) as client:
                yield client
        finally:
            for key, old in touched.items():
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old
            get_settings.cache_clear()


@pytest.fixture
def client_factory():
    return client_with_env
