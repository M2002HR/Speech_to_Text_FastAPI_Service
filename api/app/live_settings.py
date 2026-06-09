from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List
from urllib.parse import urlencode


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_csv(name: str) -> List[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [x.strip() for x in raw.replace(";", ",").replace("\n", ",").split(",") if x.strip()]


def mask_secret(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if len(clean) < 10:
        return "***"
    return f"{clean[:3]}***{clean[-3:]}"


def clean_client_text(value: Any, max_len: int = 500) -> str:
    text = str(value or "").strip()
    return text[:max_len]


def client_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def client_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def client_float(value: Any, default: float, min_value: float, max_value: float) -> float:
    if value is None or value == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


@dataclass
class LiveSettings:
    enabled: bool = True
    deepgram_api_key: str = ""
    deepgram_base_url: str = "wss://api.deepgram.com/v1/listen"
    deepgram_model: str = "nova-3"
    language: str = "fa"
    interim_results: bool = True
    punctuate: bool = True
    smart_format: bool = True
    diarize: bool = False
    vad_events: bool = True
    endpointing_ms: int = 700
    utterance_end_ms: int = 1000
    encoding: str = "opus"
    sample_rate: int = 48000
    channels: int = 1
    keyterms: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    keepalive_sec: float = 5.0
    open_timeout_sec: float = 45.0
    close_timeout_sec: float = 10.0
    # 0 (or negative) disables the websockets client keepalive ping. Deepgram
    # does not answer protocol-level pings, so this stays off by default and
    # the app-level KeepAlive loop keeps the stream open instead.
    ping_interval_sec: float = 0.0
    ping_timeout_sec: float = 20.0
    connect_retries: int = 2
    connect_retry_backoff_sec: float = 2.0
    llm_enabled: bool = True
    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 700
    llm_timeout_sec: float = 25.0
    llm_min_chars: int = 220
    llm_interval_sec: float = 180.0
    analysis_interval_sec: float = 180.0
    llm_context_chars: int = 6000
    llm_strict_schema: bool = True
    issue_tracking_enabled: bool = True
    issue_resolution_enabled: bool = True
    issue_resolution_interval_sec: float = 300.0
    issue_resolution_min_confidence: float = 0.68

    @classmethod
    def from_env(cls) -> "LiveSettings":
        deepgram_key = os.getenv("DEEPGRAM_API_KEY") or os.getenv("PROVIDER_DEEPGRAM_API_KEY") or os.getenv("LIVE_DEEPGRAM_API_KEY") or ""
        groq_key = os.getenv("GROQ_API_KEY") or os.getenv("PROVIDER_GROQ_API_KEY") or os.getenv("LIVE_LLM_API_KEY") or ""
        analysis_interval = env_float("LIVE_ANALYSIS_INTERVAL_SEC", env_float("LIVE_LLM_INTERVAL_SEC", 180.0))
        return cls(
            enabled=env_bool("LIVE_ENABLED", True),
            deepgram_api_key=deepgram_key.strip(),
            deepgram_base_url=os.getenv("LIVE_DEEPGRAM_BASE_URL", "wss://api.deepgram.com/v1/listen").strip(),
            deepgram_model=os.getenv("LIVE_DEEPGRAM_MODEL", os.getenv("LIVE_STT_MODEL", "nova-3")).strip() or "nova-3",
            language=os.getenv("LIVE_LANGUAGE", "fa").strip() or "fa",
            interim_results=env_bool("LIVE_INTERIM_RESULTS", True),
            punctuate=env_bool("LIVE_PUNCTUATE", True),
            smart_format=env_bool("LIVE_SMART_FORMAT", True),
            diarize=env_bool("LIVE_DIARIZE", False),
            vad_events=env_bool("LIVE_VAD_EVENTS", True),
            endpointing_ms=env_int("LIVE_ENDPOINTING_MS", 700),
            utterance_end_ms=env_int("LIVE_UTTERANCE_END_MS", 1000),
            encoding=os.getenv("LIVE_DEEPGRAM_ENCODING", "opus").strip(),
            sample_rate=env_int("LIVE_DEEPGRAM_SAMPLE_RATE", 48000),
            channels=env_int("LIVE_DEEPGRAM_CHANNELS", 1),
            keyterms=env_csv("LIVE_DEEPGRAM_KEYTERMS"),
            keywords=env_csv("LIVE_DEEPGRAM_KEYWORDS"),
            keepalive_sec=env_float("LIVE_DEEPGRAM_KEEPALIVE_SEC", 5.0),
            open_timeout_sec=env_float("LIVE_DEEPGRAM_OPEN_TIMEOUT_SEC", 45.0),
            close_timeout_sec=env_float("LIVE_DEEPGRAM_CLOSE_TIMEOUT_SEC", 10.0),
            ping_interval_sec=env_float("LIVE_DEEPGRAM_PING_INTERVAL_SEC", 0.0),
            ping_timeout_sec=env_float("LIVE_DEEPGRAM_PING_TIMEOUT_SEC", 20.0),
            connect_retries=env_int("LIVE_DEEPGRAM_CONNECT_RETRIES", 2),
            connect_retry_backoff_sec=env_float("LIVE_DEEPGRAM_CONNECT_RETRY_BACKOFF_SEC", 2.0),
            llm_enabled=env_bool("LIVE_LLM_ENABLED", True),
            llm_provider=os.getenv("LIVE_LLM_PROVIDER", "groq").strip().lower() or "groq",
            llm_api_key=groq_key.strip(),
            llm_base_url=os.getenv("LIVE_LLM_BASE_URL", "https://api.groq.com/openai/v1").strip(),
            llm_model=os.getenv("LIVE_LLM_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b",
            llm_temperature=env_float("LIVE_LLM_TEMPERATURE", 0.1),
            llm_max_tokens=env_int("LIVE_LLM_MAX_TOKENS", 700),
            llm_timeout_sec=env_float("LIVE_LLM_TIMEOUT_SEC", 25.0),
            llm_min_chars=env_int("LIVE_LLM_MIN_CHARS", 220),
            llm_interval_sec=analysis_interval,
            analysis_interval_sec=analysis_interval,
            llm_context_chars=env_int("LIVE_LLM_CONTEXT_CHARS", 6000),
            llm_strict_schema=env_bool("LIVE_LLM_STRICT_SCHEMA", True),
            issue_tracking_enabled=env_bool("LIVE_ISSUE_TRACKING_ENABLED", True),
            issue_resolution_enabled=env_bool("LIVE_ISSUE_RESOLUTION_ENABLED", True),
            issue_resolution_interval_sec=env_float("LIVE_ISSUE_RESOLUTION_INTERVAL_SEC", 300.0),
            issue_resolution_min_confidence=env_float("LIVE_ISSUE_RESOLUTION_MIN_CONFIDENCE", 0.68),
        )

    def public_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "deepgram": {
                "configured": bool(self.deepgram_api_key),
                "api_key": mask_secret(self.deepgram_api_key),
                "model": self.deepgram_model,
                "language": self.language,
                "base_url": self.deepgram_base_url,
                "interim_results": self.interim_results,
                "endpointing_ms": self.endpointing_ms,
                "utterance_end_ms": self.utterance_end_ms,
                "encoding": self.encoding,
                "sample_rate": self.sample_rate,
                "channels": self.channels,
                "open_timeout_sec": self.open_timeout_sec,
                "connect_retries": self.connect_retries,
                "connect_retry_backoff_sec": self.connect_retry_backoff_sec,
            },
            "llm": {
                "enabled": self.llm_enabled,
                "configured": bool(self.llm_api_key),
                "api_key": mask_secret(self.llm_api_key),
                "provider": self.llm_provider,
                "base_url": self.llm_base_url,
                "model": self.llm_model,
                "interval_sec": self.analysis_interval_sec,
                "min_chars": self.llm_min_chars,
                "strict_schema": self.llm_strict_schema,
            },
            "issue_tracking": {
                "enabled": self.issue_tracking_enabled,
                "resolution_enabled": self.issue_resolution_enabled,
                "resolution_interval_sec": self.issue_resolution_interval_sec,
                "resolution_min_confidence": self.issue_resolution_min_confidence,
            },
        }


def apply_client_settings(settings: LiveSettings, message: Dict[str, Any]) -> LiveSettings:
    analysis_interval = client_float(message.get("analysis_interval_sec"), settings.analysis_interval_sec, 20.0, 3600.0)
    return replace(
        settings,
        llm_enabled=client_bool(message.get("llm_enabled"), settings.llm_enabled),
        llm_min_chars=client_int(message.get("llm_min_chars"), settings.llm_min_chars, 80, 3000),
        llm_interval_sec=analysis_interval,
        analysis_interval_sec=analysis_interval,
        issue_tracking_enabled=client_bool(message.get("issue_tracking_enabled"), settings.issue_tracking_enabled),
        issue_resolution_enabled=client_bool(message.get("issue_resolution_enabled"), settings.issue_resolution_enabled),
        issue_resolution_interval_sec=client_float(message.get("resolution_interval_sec"), settings.issue_resolution_interval_sec, 30.0, 7200.0),
        issue_resolution_min_confidence=client_float(message.get("issue_resolution_min_confidence"), settings.issue_resolution_min_confidence, 0.0, 1.0),
    )


def extract_client_options(message: Dict[str, Any], settings: LiveSettings) -> Dict[str, Any]:
    language = clean_client_text(message.get("language") or settings.language, 32) or settings.language
    topic = clean_client_text(message.get("topic"), 500)
    keyterms = message.get("keyterms")
    if isinstance(keyterms, str):
        keyterm_list = [x.strip() for x in keyterms.replace(";", ",").split(",") if x.strip()]
    elif isinstance(keyterms, list):
        keyterm_list = [str(x).strip() for x in keyterms if str(x).strip()]
    else:
        keyterm_list = []
    return {"language": language, "topic": topic, "keyterms": keyterm_list[:30], "diarize": bool(message.get("diarize", settings.diarize))}


def build_deepgram_url(settings: LiveSettings, client_options: Dict[str, Any]) -> str:
    query: Dict[str, Any] = {
        "model": settings.deepgram_model,
        "language": client_options.get("language") or settings.language,
        "interim_results": str(settings.interim_results).lower(),
        "punctuate": str(settings.punctuate).lower(),
        "smart_format": str(settings.smart_format).lower(),
        "diarize": str(bool(client_options.get("diarize", settings.diarize))).lower(),
        "vad_events": str(settings.vad_events).lower(),
        "endpointing": settings.endpointing_ms,
        "utterance_end_ms": settings.utterance_end_ms,
        "channels": settings.channels,
    }
    if settings.encoding:
        query["encoding"] = settings.encoding
    if settings.sample_rate > 0:
        query["sample_rate"] = settings.sample_rate
    keyterms = [*settings.keyterms, *client_options.get("keyterms", [])]
    if keyterms:
        query["keyterm"] = keyterms
    if settings.keywords:
        query["keywords"] = settings.keywords
    separator = "&" if "?" in settings.deepgram_base_url else "?"
    return settings.deepgram_base_url.rstrip("?&") + separator + urlencode(query, doseq=True)
