from __future__ import annotations


def _register_live_routes_when_app_is_created() -> None:
    try:
        from fastapi import FastAPI
    except Exception:  # pragma: no cover
        return

    if getattr(FastAPI, "_tootak_live_registered", False):
        return

    original = FastAPI.__init__

    def wrapped(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        original(self, *args, **kwargs)
        try:
            from . import live
            from .live_runtime_fixes import apply_live_runtime_fixes

            apply_live_runtime_fixes(live)
            live.install_live_routes(self)
        except Exception as exc:  # pragma: no cover
            try:
                self.state.live_routes_error = f"{exc.__class__.__name__}: {exc}"
            except Exception:
                pass

    setattr(FastAPI, "__init__", wrapped)
    setattr(FastAPI, "_tootak_live_registered", True)


_register_live_routes_when_app_is_created()
