from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
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
class TeacherIssue:
    issue_id: str
    status: str
    alert_category: str
    severity_label: str
    issue_type: str
    tags: List[str]
    short_feedback: str
    suggested_teacher_action: str
    suggested_example: str
    evidence: str
    segment_summary: str
    resolution_criteria: str
    created_from_index: int
    created_to_index: int
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolution_confidence: float = 0.0
    resolution_evidence: str = ""
    resolution_message: str = ""

    def public_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LiveSessionState:
    session_id: str
    topic: str = ""
    final_chunks: List[TranscriptChunk] = field(default_factory=list)
    analyzed_index: int = 0
    last_analysis_at: float = 0.0
    analysis_task: Optional[asyncio.Task] = None
    tracked_issues: Dict[str, TeacherIssue] = field(default_factory=dict)

    def final_text(self) -> str:
        return " ".join(chunk.text for chunk in self.final_chunks if chunk.text).strip()

    def pending_text(self) -> str:
        return " ".join(chunk.text for chunk in self.final_chunks[self.analyzed_index:] if chunk.text).strip()

    def context_text(self, max_chars: int) -> str:
        return self.final_text()[-max_chars:]

    def open_issues(self) -> List[TeacherIssue]:
        return [issue for issue in self.tracked_issues.values() if issue.status in {"open", "probably_addressed"}]


async def send_event(websocket: WebSocket, send_lock: asyncio.Lock, event_type: str, **payload: Any) -> None:
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
                    "severity_label": {"type": "string", "enum": ["none", "info", "suggestion", "important", "urgent", "critical_correction"]},
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
                    "resolution_criteria": {"type": "string"},
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
                    "resolution_criteria",
                ],
                "additionalProperties": False,
            },
        },
    }


def resolution_schema(strict: bool) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "teacher_issue_resolution_check",
            "strict": strict,
            "schema": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "issue_id": {"type": "string"},
                                "status": {"type": "string", "enum": ["open", "probably_addressed", "resolved"]},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "resolution_evidence": {"type": "string"},
                                "dashboard_message": {"type": "string"},
                            },
                            "required": ["issue_id", "status", "confidence", "resolution_evidence", "dashboard_message"],
                            "additionalProperties": False,
                        },
                        "maxItems": 8,
                    }
                },
                "required": ["updates"],
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
        "For every actionable alert, write resolution_criteria: what must happen later in the lecture for this issue to be considered fixed. "
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
        "Resolution criteria guide:\n"
        "- For needs_example, require a concrete relevant example.\n"
        "- For unclear_explanation, require a clearer rephrasing or step-by-step explanation.\n"
        "- For wrong_statement or teacher_slip, require an explicit correction.\n"
        "- For prerequisite_gap, require explaining the missing prerequisite.\n"
        "- For student_check_needed, require asking a check-for-understanding question.\n\n"
        "Decision rules:\n"
        "- If the explanation is acceptable, set should_alert_teacher=false and use alert_category=none or positive_feedback.\n"
        "- If an example would materially improve understanding, use alert_category=needs_example and include suggested_example.\n"
        "- If content seems wrong, be careful: flag wrong_statement only with concrete evidence from the transcript.\n"
        "- Feedback must be short enough to show on a teacher dashboard while teaching.\n"
        "- Use Persian for tags, short_feedback, suggested_teacher_action, suggested_example, evidence, and resolution_criteria."
    )


def resolution_system_prompt() -> str:
    return (
        "You are tracking open classroom teaching issues. "
        "Given a new Persian transcript segment and a list of open issues with resolution criteria, decide whether each issue is still open, probably addressed, or resolved. "
        "Be conservative. Mark resolved only when the new segment clearly satisfies the issue's resolution criteria. "
        "For probably_addressed, evidence is suggestive but not fully enough. "
        "Return only structured JSON matching the schema."
    )


def resolution_user_prompt(state: LiveSessionState, issues: List[TeacherIssue], segment: str) -> str:
    issue_payload = [
        {
            "issue_id": issue.issue_id,
            "status": issue.status,
            "alert_category": issue.alert_category,
            "severity_label": issue.severity_label,
            "short_feedback": issue.short_feedback,
            "resolution_criteria": issue.resolution_criteria,
            "evidence": issue.evidence,
        }
        for issue in issues
    ]
    return (
        "Open issues:\n"
        f"{json.dumps(issue_payload, ensure_ascii=False)}\n\n"
        "New transcript segment:\n"
        f"{segment}\n\n"
        "For each issue, update status only if the new segment provides evidence. "
        "Use Persian for resolution_evidence and dashboard_message. "
        "If there is no evidence, keep status=open with low confidence."
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
    parsed.setdefault("resolution_criteria", "")
    return parsed


def _is_trackable_issue(result: Dict[str, Any]) -> bool:
    if not result.get("should_alert_teacher"):
        return False
    return result.get("alert_category") not in {"none", "positive_feedback"} and result.get("severity_label") != "none"


def _create_issue_from_result(result: Dict[str, Any], from_index: int, to_index: int) -> TeacherIssue:
    criteria = str(result.get("resolution_criteria") or "").strip()
    if not criteria:
        action = str(result.get("suggested_teacher_action") or "").strip()
        criteria = action or "استاد باید این هشدار را در ادامه توضیح، اصلاح یا با مثال مناسب رفع کند."
    return TeacherIssue(
        issue_id=uuid.uuid4().hex,
        status="open",
        alert_category=str(result.get("alert_category") or "none"),
        severity_label=str(result.get("severity_label") or "none"),
        issue_type=str(result.get("issue_type") or "none"),
        tags=[str(tag) for tag in result.get("tags", []) if str(tag).strip()],
        short_feedback=str(result.get("short_feedback") or ""),
        suggested_teacher_action=str(result.get("suggested_teacher_action") or ""),
        suggested_example=str(result.get("suggested_example") or ""),
        evidence=str(result.get("evidence") or ""),
        segment_summary=str(result.get("segment_summary") or ""),
        resolution_criteria=criteria,
        created_from_index=from_index,
        created_to_index=to_index,
    )


async def call_groq_analysis(settings: LiveSettings, state: LiveSessionState, segment: str) -> Dict[str, Any]:
    if not settings.llm_api_key:
        return _normalize_analysis_result({"should_alert_teacher": False, "short_feedback": "LLM API key تنظیم نشده است."})

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
    return _normalize_analysis_result(extract_json_object(str(content or "")))


async def call_groq_resolution_check(settings: LiveSettings, state: LiveSessionState, segment: str) -> List[Dict[str, Any]]:
    issues = state.open_issues()
    if not settings.llm_api_key or not issues:
        return []
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": resolution_system_prompt()},
            {"role": "user", "content": resolution_user_prompt(state, issues, segment)},
        ],
        "temperature": 0,
        "max_completion_tokens": min(max(settings.llm_max_tokens, 700), 1200),
        "response_format": resolution_schema(settings.llm_strict_schema),
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:700])
    data = resp.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") if isinstance(data, dict) else "")
    parsed = extract_json_object(str(content or ""))
    updates = parsed.get("updates", [])
    return updates if isinstance(updates, list) else []


async def _resolve_open_issues(websocket: WebSocket, send_lock: asyncio.Lock, state: LiveSessionState, settings: LiveSettings, segment: str) -> None:
    if not (settings.issue_tracking_enabled and settings.issue_resolution_enabled):
        return
    if not state.open_issues():
        return
    updates = await call_groq_resolution_check(settings, state, segment)
    for update in updates:
        issue_id = str(update.get("issue_id") or "")
        issue = state.tracked_issues.get(issue_id)
        if issue is None:
            continue
        new_status = str(update.get("status") or "open")
        confidence = float(update.get("confidence") or 0.0)
        if new_status not in {"probably_addressed", "resolved"}:
            continue
        if confidence < settings.issue_resolution_min_confidence:
            continue
        issue.status = new_status
        issue.resolution_confidence = confidence
        issue.resolution_evidence = str(update.get("resolution_evidence") or "")
        issue.resolution_message = str(update.get("dashboard_message") or "")
        if new_status == "resolved":
            issue.resolved_at = time.time()
            await send_event(websocket, send_lock, "teacher.issue.resolved", session_id=state.session_id, issue=issue.public_dict())
        else:
            await send_event(websocket, send_lock, "teacher.issue.updated", session_id=state.session_id, issue=issue.public_dict())


async def run_analysis_task(websocket: WebSocket, send_lock: asyncio.Lock, state: LiveSessionState, settings: LiveSettings, segment: str, from_index: int, to_index: int) -> None:
    await send_event(websocket, send_lock, "analysis.started", session_id=state.session_id, from_index=from_index, to_index=to_index)
    try:
        if settings.llm_provider != "groq":
            raise HTTPException(status_code=400, detail=f"unsupported live LLM provider: {settings.llm_provider}")
        await _resolve_open_issues(websocket, send_lock, state, settings, segment)
        result = await call_groq_analysis(settings, state, segment)
        if settings.issue_tracking_enabled and _is_trackable_issue(result):
            issue = _create_issue_from_result(result, from_index, to_index)
            state.tracked_issues[issue.issue_id] = issue
            result["issue_id"] = issue.issue_id
            result["issue_status"] = issue.status
            result["resolution_criteria"] = issue.resolution_criteria
            await send_event(websocket, send_lock, "teacher.issue.created", session_id=state.session_id, issue=issue.public_dict())
        await send_event(websocket, send_lock, "teacher.hint", session_id=state.session_id, from_index=from_index, to_index=to_index, result=result)
    except Exception as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        await send_event(websocket, send_lock, "analysis.error", session_id=state.session_id, error=str(detail))


async def maybe_schedule_analysis(websocket: WebSocket, send_lock: asyncio.Lock, state: LiveSessionState, settings: LiveSettings, *, force: bool = False) -> None:
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
