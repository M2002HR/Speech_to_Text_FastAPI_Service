from __future__ import annotations


def _load_tootak_live_guard() -> None:
    try:
        from api.app import live
        from api.app.live_prompt_guard import apply_live_prompt_guard
        from api.app.live_runtime_fixes import apply_live_runtime_fixes

        apply_live_prompt_guard(live)
        apply_live_runtime_fixes(live)
        _ensure_live_routes_registered(live)
    except Exception:
        # Keep Python startup resilient. The normal app import will surface route errors if any.
        return


def _ensure_live_routes_registered(live_module) -> None:  # type: ignore[no-untyped-def]
    try:
        from api.app import main as main_module
    except Exception:
        return

    app = getattr(main_module, "app", None)
    if app is None:
        return

    route_paths = [getattr(route, "path", "") for route in getattr(app, "routes", [])]
    if "/live/ws" in route_paths:
        return

    try:
        app.state.live_routes_installed = False
    except Exception:
        pass
    live_module.install_live_routes(app)


_load_tootak_live_guard()
