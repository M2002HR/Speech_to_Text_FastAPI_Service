from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request

from .config import Settings
from .services import APITranscriber, sanitize_language_code


@dataclass
class DeepgramProviderConfig:
    enabled: bool = False
    base_url: str = "https://api.deepgram.com"
    api_key: str = ""
    api_keys: List[str] = field(default_factory=list)
    model: str = "nova-3"
    transcriptions_path: str = "/v1/listen"
    timeout_sec: float = 300.0

    def all_api_keys(self) -> List[str]:
        out: List[str] = []
        for key in [self.api_key, *self.api_keys]:
            clean = str(key or "").strip()
            if clean and clean not in out:
                out.append(clean)
        return out


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_csv(name: str) -> List[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [x.strip() for x in raw.replace(";", ",").replace("\n", ",").split(",") if x.strip()]


def join_deepgram_url(base_url: str, path: str) -> str:
    base = str(base_url or "").rstrip("/")
    suffix = str(path or "").strip() or "/v1/listen"
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    return base + suffix


def deepgram_provider(settings: Optional[Settings] = None) -> DeepgramProviderConfig:
    provider = getattr(getattr(settings, "providers", None), "deepgram", None) if settings is not None else None
    if provider is not None:
        return DeepgramProviderConfig(
            enabled=bool(getattr(provider, "enabled", False)),
            base_url=str(getattr(provider, "base_url", "https://api.deepgram.com") or "https://api.deepgram.com"),
            api_key=(str(getattr(provider, "api_key", "") or "") or os.getenv("DEEPGRAM_API_KEY") or ""),
            api_keys=list(getattr(provider, "api_keys", []) or []),
            model=str(getattr(provider, "model", "nova-3") or "nova-3"),
            transcriptions_path=str(getattr(provider, "transcriptions_path", "/v1/listen") or "/v1/listen"),
            timeout_sec=float(getattr(provider, "timeout_sec", 300.0) or 300.0),
        )
    return DeepgramProviderConfig(
        enabled=_env_bool("PROVIDER_DEEPGRAM_ENABLED", False),
        base_url=os.getenv("PROVIDER_DEEPGRAM_BASE_URL", "https://api.deepgram.com").strip() or "https://api.deepgram.com",
        api_key=(os.getenv("PROVIDER_DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_API_KEY") or "").strip(),
        api_keys=_env_csv("PROVIDER_DEEPGRAM_API_KEYS"),
        model=os.getenv("PROVIDER_DEEPGRAM_MODEL", "nova-3").strip() or "nova-3",
        transcriptions_path=os.getenv("PROVIDER_DEEPGRAM_TRANSCRIPTIONS_PATH", "/v1/listen").strip() or "/v1/listen",
        timeout_sec=_env_float("PROVIDER_DEEPGRAM_TIMEOUT_SEC", 300.0),
    )


def normalize_deepgram_words(words: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(words, list):
        return out
    for item in words:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word") or item.get("punctuated_word") or "").strip()
        if not word:
            continue
        out.append({"word": word, "start": float(item.get("start") or 0.0), "end": float(item.get("end") or item.get("start") or 0.0), "probability": item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None})
    return out


def parse_deepgram_payload(payload: Dict[str, Any], *, model_name: str, process_ms: float) -> Dict[str, Any]:
    results = payload.get("results") if isinstance(payload.get("results"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    channels = results.get("channels") if isinstance(results.get("channels"), list) else []
    first_alt: Dict[str, Any] = {}
    if channels:
        alternatives = (channels[0].get("alternatives") or []) if isinstance(channels[0], dict) else []
        if alternatives and isinstance(alternatives[0], dict):
            first_alt = alternatives[0]
    text = str(first_alt.get("transcript") or "").strip()
    words = normalize_deepgram_words(first_alt.get("words"))
    segments: List[Dict[str, Any]] = []
    for idx, utt in enumerate(results.get("utterances") if isinstance(results.get("utterances"), list) else []):
        if not isinstance(utt, dict):
            continue
        seg_text = str(utt.get("transcript") or "").strip()
        if not seg_text:
            continue
        segments.append({"id": idx, "start": float(utt.get("start") or 0.0), "end": float(utt.get("end") or utt.get("start") or 0.0), "text": seg_text, "avg_logprob": None, "no_speech_prob": None, "words": normalize_deepgram_words(utt.get("words"))})
    duration_seconds = metadata.get("duration") if isinstance(metadata.get("duration"), (int, float)) else None
    if not segments and text:
        segments = [{"id": 0, "start": 0.0, "end": float(duration_seconds or 0.0), "text": text, "avg_logprob": None, "no_speech_prob": None, "words": words}]
    langs = first_alt.get("languages") if isinstance(first_alt.get("languages"), list) else []
    return {"text": text, "language": langs[0] if langs else None, "duration_seconds": duration_seconds, "segments": segments, "words": words, "usage": {"provider": "deepgram", "model": model_name, "audio_seconds": duration_seconds, "process_ms": round(process_ms, 2)}, "metadata": {"upstream_raw": payload, "deepgram_request_id": metadata.get("request_id")}}


async def call_deepgram_batch(client: httpx.AsyncClient, provider: DeepgramProviderConfig, audio_path: Path, options: Dict[str, Any], api_key: str, key_index: int, key_total: int) -> Dict[str, Any]:
    if not provider.enabled:
        raise HTTPException(status_code=400, detail="provider 'deepgram' is disabled")
    if not provider.base_url or not api_key:
        raise HTTPException(status_code=500, detail="provider 'deepgram' is missing base_url/api_key")
    model_name = str(options.get("model") or provider.model or "nova-3")
    params: Dict[str, Any] = {"model": model_name, "punctuate": "true", "smart_format": "true", "utterances": "true", "diarize": "false"}
    language_code = sanitize_language_code(options.get("language"))
    if language_code:
        params["language"] = language_code
    if options.get("word_timestamps") is not False:
        params["words"] = "true"
    if options.get("vocabulary_bias"):
        terms = [x.strip() for x in str(options["vocabulary_bias"]).replace("،", ",").split(",") if x.strip()]
        if terms:
            params["keyterm"] = terms[:50]
    url = join_deepgram_url(provider.base_url, provider.transcriptions_path) + "?" + urlencode(params, doseq=True)
    started = time.perf_counter()
    content = audio_path.read_bytes()
    try:
        resp = await client.post(url, content=content, headers={"Authorization": f"Token {api_key}"}, timeout=provider.timeout_sec)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"upstream deepgram timeout with key {key_index + 1}/{key_total}: {exc.__class__.__name__}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"upstream deepgram request error with key {key_index + 1}/{key_total}: {exc.__class__.__name__}") from exc
    process_ms = (time.perf_counter() - started) * 1000.0
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"upstream deepgram transcription error with key {key_index + 1}/{key_total}: {resp.text[:600]}")
    out = parse_deepgram_payload(resp.json(), model_name=model_name, process_ms=process_ms)
    out.setdefault("metadata", {})["provider_key_index"] = key_index + 1
    out.setdefault("metadata", {})["provider_key_count"] = key_total
    return out


async def call_deepgram_with_rotation(api: APITranscriber, provider: DeepgramProviderConfig, audio_path: Path, options: Dict[str, Any]) -> Dict[str, Any]:
    keys = provider.all_api_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="provider 'deepgram' is missing api_key")
    offset = api._key_offsets.get("deepgram", 0) % len(keys)
    ordered = keys[offset:] + keys[:offset]
    errors: List[str] = []
    last_status = 500
    for key in ordered:
        idx = keys.index(key)
        try:
            out = await call_deepgram_batch(api.client, provider, audio_path, options, key, idx, len(keys))
            api._mark_key_success("deepgram", idx, len(keys))
            return out
        except HTTPException as exc:
            errors.append(str(exc.detail))
            last_status = int(exc.status_code)
            api._mark_key_limited("deepgram", idx, len(keys))
            if not api._is_retryable_key_error(last_status):
                break
    raise HTTPException(status_code=last_status, detail=" | ".join(errors) or "no deepgram provider key succeeded")


async def check_deepgram_provider(request: Request, provider: Optional[DeepgramProviderConfig] = None) -> Dict[str, Any]:
    provider = provider or deepgram_provider(request.app.state.settings)
    keys = provider.all_api_keys()
    out: Dict[str, Any] = {"name": "deepgram", "configured": bool(provider.enabled), "key_present": bool(keys), "valid": False, "enabled_for_user": False, "model": provider.model or None, "base_url": provider.base_url if provider.enabled else None, "status_code": None, "reason": ""}
    if not provider.enabled:
        out["reason"] = "provider is disabled in config"
        return out
    if not provider.base_url:
        out["reason"] = "provider base_url is empty"
        return out
    if not keys:
        out["reason"] = "provider api key is empty"
        return out
    client = request.app.state.services.transcription.client
    url = join_deepgram_url(provider.base_url, "/v1/projects")
    last_status: Optional[int] = None
    for idx, key in enumerate(keys):
        try:
            resp = await client.get(url, headers={"Authorization": f"Token {key}"}, timeout=min(float(provider.timeout_sec or 30), 30.0))
        except Exception as exc:
            out["reason"] = f"validation request failed: {exc.__class__.__name__}"
            return out
        last_status = resp.status_code
        if 200 <= resp.status_code < 400:
            out.update({"valid": True, "enabled_for_user": True, "status_code": resp.status_code, "reason": f"ok (key {idx + 1}/{len(keys)})"})
            return out
    out["status_code"] = last_status
    out["reason"] = "all configured api keys were rejected by provider" if last_status in {401, 403} else f"provider returned HTTP {last_status}"
    return out
