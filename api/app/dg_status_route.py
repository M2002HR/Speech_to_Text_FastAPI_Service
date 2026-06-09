from __future__ import annotations

from typing import Any, Dict

from fastapi import Request

from .dg_provider import check_dg_provider, get_dg_config


def add_route(app: Any) -> None:
    @app.get('/providers/deepgram/status')
    async def deepgram_status(request: Request) -> Dict[str, Any]:
        return await check_dg_provider(request, get_dg_config(request.app.state.settings))
