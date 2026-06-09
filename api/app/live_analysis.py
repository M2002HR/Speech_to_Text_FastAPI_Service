from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, WebSocket

from .live_settings import LiveSettings


@dataclass
class TranscriptChunk:
    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    confidence: Optional[float] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class LiveSessionState:
    session_id: str
    topic: str = ""
    final_chunks: List[TranscriptChunk] = field(default_factory=list)
    analyzed_index: int = 0
    last_analysis_at: float = 0.0
    analysis_task: Optional[asyncio.Task] = None

    def final_text(self) -> str:
        return " ".join(chunk.text for chunk in self.final_chunks if chunk.text).strip()

    def pending_text(self) -> str:
        return " ".join(chunk.text for chunk in self.final_chunks[self.analyzed_index:] if chunk.text).strip()

    def context_text(self, max_chars: int) -> str:
        return self.final_text()[-max_chars:]


async def send_event(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    event_type: str,
    **payload: Any,
) -> None:
    message = {"type": event_type, "ts": time.time(), **payload}
    async with send_lock:
        await websocket.send_json(message)


def analysis_schema(strict: bool) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "teacher_live_feedback",
            "strict": strict,
            "schema": {
                "type": "object",
                "properties": {
                    "should_alert_teacher": {"type": "boolean"},
                    "alert_level": {"type": "string", "enum": ["none", "low", "medium", "high", "critical"]},
                    "alert_category": {
                        "type": "string",
                        "enum": [
                            "none",
                            "needs_example",
                            "unclear_explanation",
                            "too_fast_or_dense",
                            "wrong_statement",
                            "teacher_slip",
                            "prerequisite_gap",
                            "student_check_needed",
                            "topic_management",
                            "positive_feedback",
                        ],
                    },
                    "severity_label": {
                        "type": "string",
                        "enum": [
                            "none",
                            "info",
                            "suggestion",
                            "important",
                            "urgent",
                            "critical_correction",
                        ],
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": [
                            "none",
                            "unclear_definition",
                            "missing_example",
                            "too_fast",
                            "topic_jump",
                            "prerequisite_gap",
                            "needs_check_for_understanding",
                            "incorrect_content",
                            "misleading_statement",
                            "teacher_misspoke",
                            "good_progress",
                        ],
                    },
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "مثال لازم دارد",
                                "توضیح مبهم",
                                "توضیح نامناسب",
                                "خیلی فشرده",
                                "خیلی سریع",
                                "اشتباه علمی",
                                "بیان گمراه‌کننده",
                                "سوتی یا لغزش کلامی",
                                "پیش‌نیاز جا افتاده",
                                "نیاز به سوال از کلاس",
                                "پرش موضوعی",
                                "شدید و فوری",
                                "قابل توجه",
                                "خوب پیش می‌رود",
                            ],
                        },
                        "minItems": 0,
                        "maxItems": 5,
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "short_feedback": {"type": "string"},
                    "suggested_teacher_action": {"type": "string"},
                    "suggested_example": {"type": "string"},
                    "evidence": {"type": "string"},
                    "segment_summary": {"type": "string"},
                },
                "required": [
                    "should_alert_teacher",
                    "alert_level",
                    "alert_category",
                    "severity_label",
                    "issue_type",
                    "tags",
                    "confidence",
                    "short_feedback",
                    "suggested_teacher_action",
                    "suggested_example",
                    "evidence",
                    "segment_summary",
                ],
                "additionalProperties": False,
            },
        },
    }


def analysis_system_prompt() -> str:
    return (
        "You are a real-time classroom feedback assistant. "
        "You observe a live Persian classroom transcript and help the teacher improve clarity. "
        "Be conservative: only alert when the transcript gives clear evidence. "
        "Prefer short, actionable teacher hints in Persian. "
        "Classify every hint with alert_category, severity_label, issue_type, and Persian tags. "
        "Use wrong_statement or critical_correction only when there is clear evidence that the content is incorrect, not merely incomplete. "
        "Use teacher_slip for obvious misspeaking, naming mistakes, number slips, or accidental wording that the teacher can quickly correct. "
        "Do not criticize tone or personality. Focus on pedagogy: unclear definitions, missing examples, prerequisite gaps, sudden topic jumps, dense explanations, and good moments worth continuing. "
        "Return only structured JSON matching the schema."
    )


def analysis_user_prompt(state: LiveSessionState, settings: LiveSettings, segment: str) -> str:
    context = state.context_text(settings.llm_context_chars)
    topic_block = f"Topic/context provided by teacher: {state.topic}\n" if state.topic else ""
    return (
        f"{topic_block}"
        "Analyze the latest finalized transcript segment.\n\n"
        "Recent transcript context:\n"
        f"{context}\n\n"
        "Latest segment to evaluate:\n"
        f"{segment}\n\n"
        "Classification guide:\n"
        "- needs_example: explanation is probably okay but would benefit from a concrete example.\n"
        "- unclear_explanation: explanation is vague, ambiguous, or hard to follow.\n"
        "- too_fast_or_dense: too many ideas or terms are compressed together.\n"
        "- wrong_statement: the transcript clearly says something factually or conceptually wrong.\n"
        "- teacher_slip: likely misspeaking or a small verbal slip that should be corrected.\n"
        "- prerequisite_gap: a required prior concept was used without explanation.\n"
        "- student_check_needed: teacher should ask a quick understanding question.\n"
        "- positive_feedback: the current explanation is clear and useful.\n\n"
        "Severity guide:\n"
        "- suggestion: helpful but not necessary.\n"
        "- important: likely affects student understanding.\n"
        "- urgent: should be addressed soon.\n"
        "- critical_correction: likely wrong or misleading content must be corrected.\n\n"
        "Decision rules:\n"
        "- If the explanation is acceptable, set should_alert_teacher=false and use alert_category=none or positive_feedback.\n"
        "- If an example would materially improve understanding, use alert_category=needs_example and include suggested_example.\n"
        "- If content seems wrong, be careful: flag wrong_statement only with concrete evidence from the transcript.\n"
        "- Feedback must be short enough to show on a teacher dashboard while teaching.\n"
        "- Use Persian for tags, short_feedback, suggested_teacher_action, suggested_example, and evidence."
    )


def extract_json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def _normalize_analysis_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    parsed.setdefault("should_alert_teacher", False)
    parsed.setdefault("alert_level", "none")
    parsed.setdefault("alert_category", "none")
    parsed.setdefault("severity_label", "none")
    parsed.setdefault("issue_type", "none")
    tags = parsed.get("tags")
    if not isinstance(tags, list):
        parsed["tags"] = []
    else:
        parsed["tags"] = [str(tag) for tag in tags[:5] if str(tag).strip()]
    parsed.setdefault("confidence", 0.0)
    parsed.setdefault("short_feedback", "")
    parsed.setdefault("suggested_teacher_action", "")
    parsed.setdefault("suggested_example", "")
    parsed.setdefault("evidence", "")
    parsed.setdefault("segment_summary", "")
    return parsed


async def call_groq_analysis(settings: LiveSettings, state: LiveSessionState, segment: str) -> Dict[str, Any]:
    if not settings.llm_api_key:
        return _normalize_analysis_result(
            {
                "should_alert_teacher": False,
                "short_feedback": "LLM API key تنظیم نشده است.",
            }
        )

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": analysis_system_prompt()},
            {"role": "user", "content": analysis_user_prompt(state, settings, segment)},
        ],
        "temperature": settings.llm_temperature,
        "max_completion_tokens": settings.llm_max_tokens,
        "response_format": analysis_schema(settings.llm_strict_schema),
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:700])

    data = resp.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") if isinstance(data, dict) else "")
    parsed = extract_json_object(str(content or ""))
    return _normalize_analysis_result(parsed)


async def run_analysis_task(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    state: LiveSessionState,
    settings: LiveSettings,
    segment: str,
    from_index: int,
    to_index: int,
) -> None:
    await send_event(websocket, send_lock, "analysis.started", session_id=state.session_id, from_index=from_index, to_index=to_index)
    try:
        if settings.llm_provider != "groq":
            raise HTTPException(status_code=400, detail=f"unsupported live LLM provider: {settings.llm_provider}")
        result = await call_groq_analysis(settings, state, segment)
        await send_event(websocket, send_lock, "teacher.hint", session_id=state.session_id, from_index=from_index, to_index=to_index, result=result)
    except Exception as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        await send_event(websocket, send_lock, "analysis.error", session_id=state.session_id, error=str(detail))


async def maybe_schedule_analysis(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    state: LiveSessionState,
    settings: LiveSettings,
    *,
    force: bool = False,
) -> None:
    if not settings.llm_enabled:
        return
    if state.analysis_task and not state.analysis_task.done():
        return

    pending = state.pending_text()
    if not pending:
        return

    now = time.time()
    enough_chars = len(pending) >= settings.llm_min_chars
    enough_time = (now - state.last_analysis_at) >= settings.llm_interval_sec

    if not force and not (enough_chars and enough_time):
        return

    from_index = state.analyzed_index
    to_index = len(state.final_chunks)
    state.analyzed_index = to_index
    state.last_analysis_at = now
    state.analysis_task = asyncio.create_task(run_analysis_task(websocket, send_lock, state, settings, pending, from_index, to_index))
