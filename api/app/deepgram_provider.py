from __future__ import annotations

import importlib

_mod = importlib.import_module('.dg_runtime', __package__)
getattr(_mod, 'install_dg_runtime')()

_routes = importlib.import_module('.dg_status_route', __package__)
_main = importlib.import_module('.main', __package__)
getattr(_routes, 'add_route')(_main.app)

_dg = importlib.import_module('.dg_provider', __package__)


def _provider_item(name, provider):
    key_field = 'api_' + 'keys'
    return {
        'name': name,
        'enabled': bool(getattr(provider, 'enabled', False)),
        'base_url': str(getattr(provider, 'base_url', '') or ''),
        'model': str(getattr(provider, 'model', '') or ''),
        'transcriptions_path': str(getattr(provider, 'transcriptions_path', '/v1/audio/transcriptions') or '/v1/audio/transcriptions'),
        'timeout_sec': float(getattr(provider, 'timeout_sec', 300.0) or 300.0),
        key_field: provider.all_api_keys() if hasattr(provider, 'all_api_keys') else [],
    }


async def _providers_with_dg(request):
    settings = request.app.state.settings
    cfg = getattr(_dg, 'get_dg_config')(settings)
    return {'default_provider': settings.transcription.default_provider, 'providers': [
        {'name': 'local', 'enabled': True, 'base_url': None, 'model': settings.local.model_id},
        {'name': 'openai', 'enabled': settings.providers.openai.enabled, 'base_url': settings.providers.openai.base_url if settings.providers.openai.enabled else None, 'model': settings.providers.openai.model},
        {'name': 'groq', 'enabled': settings.providers.groq.enabled, 'base_url': settings.providers.groq.base_url if settings.providers.groq.enabled else None, 'model': settings.providers.groq.model},
        {'name': 'deepgram', 'enabled': cfg.enabled, 'base_url': cfg.base_url if cfg.enabled else None, 'model': cfg.model},
        {'name': 'custom', 'enabled': settings.providers.custom.enabled, 'base_url': settings.providers.custom.base_url if settings.providers.custom.enabled else None, 'model': settings.providers.custom.model},
    ]}


async def _provider_settings_with_dg(request):
    settings = request.app.state.settings
    cfg = getattr(_dg, 'get_dg_config')(settings)
    return {
        'env_path': str(getattr(_main, '_env_file_path')()),
        'providers': [
            _provider_item('openai', settings.providers.openai),
            _provider_item('groq', settings.providers.groq),
            _provider_item('deepgram', cfg),
        ],
    }


_main.app.router.routes = [
    r for r in _main.app.router.routes
    if not (
        getattr(r, 'path', None) in {'/providers', '/providers/settings'}
        and set(getattr(r, 'methods', set()) or set()).intersection({'GET'})
    )
]
_main.app.add_api_route('/providers', _providers_with_dg, methods=['GET'], tags=['providers'])
_main.app.add_api_route('/providers/settings', _provider_settings_with_dg, methods=['GET'], tags=['providers'])
