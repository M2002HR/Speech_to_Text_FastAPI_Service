"""Unified ASGI entrypoint that exposes every Tootak service in one app.

This combines the three historical entrypoints into a single target so one
start command brings up everything:

- ``api.app.main``       -> base transcription API + user/lab web UIs
- ``api.app.realtime_router`` -> ``/realtime`` streaming classroom STT
- ``api.app.main_live``  -> ``/live`` websocket teacher feedback

Run with::

    uvicorn api.app.server:app --host 0.0.0.0 --port 8030
"""

from __future__ import annotations

# Registering the Deepgram provider has import side effects; keep it first.
from . import deepgram_provider  # noqa: F401
from .main import app as base_app
from .realtime_router import router as realtime_router

# Add the realtime routes onto the shared base app before it is wrapped by the
# live ASGI adapter below, so a single app serves transcribe + realtime + live.
_realtime_paths = {getattr(r, "path", None) for r in base_app.router.routes}
if "/realtime" not in _realtime_paths:
    base_app.include_router(realtime_router)

# ``main_live`` wraps the same ``base_app`` object (now carrying the realtime
# routes) and intercepts ``/live`` + ``/live/ws`` while delegating the rest.
from .main_live import app  # noqa: E402  (import after routes are attached)

__all__ = ["app"]
