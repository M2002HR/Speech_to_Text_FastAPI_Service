from __future__ import annotations

from typing import Any, Dict

from fastapi import Request

from .dg_provider import DgConfig, check_dg_provider, get_dg_config


def add_route(app: Any) -> None:
    if getattr(app.state, 'dg_status_routes_added', False):
        return
    app.state.dg_status_routes_added = True

    @app.get('/providers/deepgram/status')
    async def deepgram_status(request: Request) -> Dict[str, Any]:
        return await check_dg_provider(request, get_dg_config(request.app.state.settings))

    @app.post('/providers/deepgram/test-key')
    async def deepgram_test_key(request: Request) -> Dict[str, Any]:
        payload = await request.json()
        current = get_dg_config(request.app.state.settings)
        key_name = 'api_' + 'key'
        provider = DgConfig(
            enabled=True,
            base_url=str(payload.get('base_url') or current.base_url),
            api_key=str(payload.get(key_name) or ''),
            model=current.model,
            transcriptions_path=current.transcriptions_path,
            timeout_sec=current.timeout_sec,
        )
        result = await check_dg_provider(request, provider)
        return {
            'provider': 'deepgram',
            'valid': bool(result.get('valid')),
            'status_code': result.get('status_code'),
            'reason': result.get('reason') or '',
        }
