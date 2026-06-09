from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request

from .services import APITranscriber, sanitize_language_code


@dataclass
class DgConfig:
    enabled: bool = False
    base_url: str = "https://api.deepgram.com"
    api_key: str = ""
    api_keys: List[str] = field(default_factory=list)
    model: str = "nova-3"
    transcriptions_path: str = "/v1/listen"
    timeout_sec: float = 300.0

    def all_api_keys(self) -> List[str]:
        keys: List[str] = []
        for key in [self.api_key, *self.api_keys]:
            clean = str(key or "").strip()
            if clean and clean not in keys:
                keys.append(clean)
        return keys


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _csv(name: str) -> List[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [x.strip() for x in raw.replace(";", ",").replace("\n", ",").split(",") if x.strip()]


def get_dg_config(settings: Any = None) -> DgConfig:
    provider = getattr(getattr(settings, "providers", None), "deepgram", None) if settings is not None else None
    if provider is not None:
        return DgConfig(
            enabled=bool(getattr(provider, "enabled", False)),
            base_url=str(getattr(provider, "base_url", "https://api.deepgram.com") or "https://api.deepgram.com"),
            api_key=str(getattr(provider, "api_key", "") or "") or (os.getenv("DEEPGRAM_API_KEY") or ""),
            api_keys=list(getattr(provider, "api_keys", []) or []),
            model=str(getattr(provider, "model", "nova-3") or "nova-3"),
            transcriptions_path=str(getattr(provider, "transcriptions_path", "/v1/listen") or "/v1/listen"),
            timeout_sec=float(getattr(provider, "timeout_sec", 300.0) or 300.0),
        )
    return DgConfig(
        enabled=_bool("PROVIDER_DEEPGRAM_ENABLED", False),
        base_url=os.getenv("PROVIDER_DEEPGRAM_BASE_URL", "https://api.deepgram.com").strip() or "https://api.deepgram.com",
        api_key=(os.getenv("PROVIDER_DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_API_KEY") or "").strip(),
        api_keys=_csv("PROVIDER_DEEPGRAM_API_KEYS"),
        model=os.getenv("PROVIDER_DEEPGRAM_MODEL", "nova-3").strip() or "nova-3",
        transcriptions_path=os.getenv("PROVIDER_DEEPGRAM_TRANSCRIPTIONS_PATH", "/v1/listen").strip() or "/v1/listen",
        timeout_sec=_float("PROVIDER_DEEPGRAM_TIMEOUT_SEC", 300.0),
    )


def _join(base_url: str, path: str) -> str:
    base = str(base_url or "").rstrip("/")
    suffix = str(path or "").strip() or "/v1/listen"
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    return base + suffix


def _words(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        word = str(item.get("punctuated_word") or item.get("word") or "").strip()
        if not word:
            continue
        out.append({
            "word": word,
            "start": float(item.get("start") or 0.0),
            "end": float(item.get("end") or item.get("start") or 0.0),
            "probability": item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None,
        })
    return out


def _parse(payload: Dict[str, Any], model_name: str, process_ms: float) -> Dict[str, Any]:
    results = payload.get("results") if isinstance(payload.get("results"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    channels = results.get("channels") if isinstance(results.get("channels"), list) else []
    alt: Dict[str, Any] = {}
    if channels and isinstance(channels[0], dict):
        alternatives = channels[0].get("alternatives") if isinstance(channels[0].get("alternatives"), list) else []
        if alternatives and isinstance(alternatives[0], dict):
            alt = alternatives[0]
    text = str(alt.get("transcript") or "").strip()
    all_words = _words(alt.get("words"))
    duration = metadata.get("duration") if isinstance(metadata.get("duration"), (int, float)) else None
    segments: List[Dict[str, Any]] = []
    utterances = results.get("utterances") if isinstance(results.get("utterances"), list) else []
    for idx, utt in enumerate(utterances):
        if not isinstance(utt, dict):
            continue
        segment_text = str(utt.get("transcript") or "").strip()
        if not segment_text:
            continue
        segments.append({
            "id": idx,
            "start": float(utt.get("start") or 0.0),
            "end": float(utt.get("end") or utt.get("start") or 0.0),
            "text": segment_text,
            "avg_logprob": None,
            "no_speech_prob": None,
            "words": _words(utt.get("words")),
        })
    if not segments and text:
        segments.append({"id": 0, "start": 0.0, "end": float(duration or 0.0), "text": text, "avg_logprob": None, "no_speech_prob": None, "words": all_words})
    languages = alt.get("languages") if isinstance(alt.get("languages"), list) else []
    return {
        "text": text,
        "language": languages[0] if languages else None,
        "duration_seconds": duration,
        "segments": segments,
        "words": all_words,
        "usage": {"provider": "deepgram", "model": model_name, "audio_seconds": duration, "process_ms": round(process_ms, 2)},
        "metadata": {"upstream_raw": payload, "deepgram_request_id": metadata.get("request_id")},
    }


async def transcribe_dg(client: httpx.AsyncClient, provider: DgConfig, audio_path: Path, options: Dict[str, Any], api_key: str, key_index: int, key_total: int) -> Dict[str, Any]:
    if not provider.enabled:
        raise HTTPException(status_code=400, detail="provider 'deepgram' is disabled")
    if not provider.base_url or not api_key:
        raise HTTPException(status_code=500, detail="provider 'deepgram' is missing base_url/api_key")
    model_name = str(options.get("model") or provider.model or "nova-3")
    params: Dict[str, Any] = {"model": model_name, "punctuate": "true", "smart_format": "true", "utterances": "true"}
    language = sanitize_language_code(options.get("language"))
    if language:
        params["language"] = language
    if options.get("word_timestamps") is not False:
        params["words"] = "true"
    url = _join(provider.base_url, provider.transcriptions_path) + "?" + urlencode(params, doseq=True)
    started = time.perf_counter()
    try:
        resp = await client.post(url, content=audio_path.read_bytes(), headers={"Authorization": f"Token {api_key}"}, timeout=provider.timeout_sec)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"upstream deepgram timeout with key {key_index + 1}/{key_total}: {exc.__class__.__name__}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"upstream deepgram request error with key {key_index + 1}/{key_total}: {exc.__class__.__name__}") from exc
    process_ms = (time.perf_counter() - started) * 1000.0
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"upstream deepgram transcription error with key {key_index + 1}/{key_total}: {resp.text[:600]}")
    out = _parse(resp.json(), model_name, process_ms)
    out.setdefault("metadata", {})["provider_key_index"] = key_index + 1
    out.setdefault("metadata", {})["provider_key_count"] = key_total
    return out


async def transcribe_dg_with_rotation(api: APITranscriber, provider: DgConfig, audio_path: Path, options: Dict[str, Any]) -> Dict[str, Any]:
    keys = provider.all_api_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="provider 'deepgram' is missing api_key")
    offset = api._key_offsets.get("deepgram", 0) % len(keys)
    ordered = keys[offset:] + keys[:offset]
    errors: List[str] = []
    last_status = 500
    for key in ordered:
        index = keys.index(key)
        try:
            out = await transcribe_dg(api.client, provider, audio_path, options, key, index, len(keys))
            api._mark_key_success("deepgram", index, len(keys))
            return out
        except HTTPException as exc:
            errors.append(str(exc.detail))
            last_status = int(exc.status_code)
            api._mark_key_limited("deepgram", index, len(keys))
            if not api._is_retryable_key_error(last_status):
                break
    raise HTTPException(status_code=last_status, detail=" | ".join(errors) or "no deepgram provider key succeeded")


async def check_dg_provider(request: Request, provider: Optional[DgConfig] = None) -> Dict[str, Any]:
    provider = provider or get_dg_config(request.app.state.settings)
    keys = provider.all_api_keys()
    out: Dict[str, Any] = {"name": "deepgram", "configured": bool(provider.enabled), "key_present": bool(keys), "valid": False, "enabled_for_user": False, "model": provider.model, "base_url": provider.base_url if provider.enabled else None, "status_code": None, "reason": ""}
    if not provider.enabled:
        out["reason"] = "provider is disabled in config"
        return out
    if not keys:
        out["reason"] = "provider api key is empty"
        return out
    client = request.app.state.services.transcription.client
    last_status: Optional[int] = None
    for idx, key in enumerate(keys):
        try:
            resp = await client.get(_join(provider.base_url, "/v1/projects"), headers={"Authorization": f"Token {key}"}, timeout=min(float(provider.timeout_sec or 30), 30.0))
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
