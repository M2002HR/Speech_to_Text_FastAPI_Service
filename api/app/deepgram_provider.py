from __future__ import annotations

import importlib

from starlette.requests import Request

_mod = importlib.import_module('.dg_runtime', __package__)
getattr(_mod, 'install_dg_runtime')()

_routes = importlib.import_module('.dg_status_route', __package__)
_main = importlib.import_module('.main', __package__)
getattr(_routes, 'add_route')(_main.app)

_dg = importlib.import_module('.dg_provider', __package__)


async def _providers_with_dg(request: Request):
    settings = request.app.state.settings
    cfg = getattr(_dg, 'get_dg_config')(settings)
    return {'default_provider': settings.transcription.default_provider, 'providers': [
        {'name': 'local', 'enabled': True, 'base_url': None, 'model': settings.local.model_id},
        {'name': 'openai', 'enabled': settings.providers.openai.enabled, 'base_url': settings.providers.openai.base_url if settings.providers.openai.enabled else None, 'model': settings.providers.openai.model},
        {'name': 'groq', 'enabled': settings.providers.groq.enabled, 'base_url': settings.providers.groq.base_url if settings.providers.groq.enabled else None, 'model': settings.providers.groq.model},
        {'name': 'deepgram', 'enabled': cfg.enabled, 'base_url': cfg.base_url if cfg.enabled else None, 'model': cfg.model},
        {'name': 'custom', 'enabled': settings.providers.custom.enabled, 'base_url': settings.providers.custom.base_url if settings.providers.custom.enabled else None, 'model': settings.providers.custom.model},
    ]}


_main.app.router.routes = [r for r in _main.app.router.routes if getattr(r, 'path', None) != '/providers']
_main.app.add_api_route('/providers', _providers_with_dg, methods=['GET'], tags=['providers'])
