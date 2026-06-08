from __future__ import annotations

from . import live
from .live_prompt_guard import apply_live_prompt_guard
from .live_runtime_fixes import apply_live_runtime_fixes
from .main import app


def _ensure_live_routes() -> None:
    apply_live_prompt_guard(live)
    apply_live_runtime_fixes(live)
    paths = [getattr(route, "path", "") for route in getattr(app, "routes", [])]
    if "/live/ws" not in paths:
        try:
            app.state.live_routes_installed = False
        except Exception:
            pass
        live.install_live_routes(app)


_ensure_live_routes()
