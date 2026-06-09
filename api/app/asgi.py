from __future__ import annotations

from .main import app
from . import deepgram_provider
from .realtime_router import router as realtime_router

app.include_router(realtime_router)
