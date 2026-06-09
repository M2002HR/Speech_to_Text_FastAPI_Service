# Realtime issue tracking

The realtime classroom dashboard can track actionable teacher hints as open issues and later mark them as probably addressed or resolved.

## Feature flags

```bash
LIVE_ISSUE_TRACKING_ENABLED=true
LIVE_ISSUE_RESOLUTION_ENABLED=true
LIVE_ISSUE_RESOLUTION_MIN_CONFIDENCE=0.68
```

- `LIVE_ISSUE_TRACKING_ENABLED=false` disables issue IDs, open issue state, and dashboard resolution status.
- `LIVE_ISSUE_RESOLUTION_ENABLED=false` keeps issue creation but disables automatic resolved/probably-addressed detection.
- `LIVE_ISSUE_RESOLUTION_MIN_CONFIDENCE` controls how confident the LLM must be before the dashboard status changes.

## Events

When enabled, actionable `teacher.hint` results become issues and the websocket can emit:

```text
teacher.issue.created
teacher.issue.updated
teacher.issue.resolved
```

Each tracked issue includes:

```json
{
  "issue_id": "...",
  "status": "open",
  "alert_category": "needs_example",
  "severity_label": "important",
  "resolution_criteria": "استاد باید یک مثال مشخص و مرتبط بزند."
}
```

For each later finalized transcript window, the LLM compares open issues against the new segment. If the teacher addresses the issue, the status becomes `probably_addressed` or `resolved` depending on confidence and evidence.
