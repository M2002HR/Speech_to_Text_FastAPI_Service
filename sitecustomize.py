from __future__ import annotations


def _load_tootak_live_guard() -> None:
    try:
        from api.app import live
        from api.app.live_prompt_guard import apply_live_prompt_guard
        from api.app.live_runtime_fixes import apply_live_runtime_fixes

        apply_live_prompt_guard(live)
        apply_live_runtime_fixes(live)
    except Exception:
        # Keep Python startup resilient. The normal app import will surface route errors if any.
        return


_load_tootak_live_guard()
