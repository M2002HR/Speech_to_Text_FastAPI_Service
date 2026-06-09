from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from .dg_provider import DgConfig, check_dg_provider, get_dg_config


def _ui_dir() -> Path:
    return Path(__file__).resolve().parent / 'ui'


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

    async def patched_user_index() -> HTMLResponse:
        html_path = _ui_dir() / 'user.html'
        html = html_path.read_text(encoding='utf-8')
        script = '<script src="/dg-ui.js?v=20260609b" defer></script>'
        if script not in html:
            html = html.replace('</body>', f'  {script}\n</body>')
        return HTMLResponse(html)

    async def dg_ui_js() -> Response:
        js = """
(() => {
  const ready = () => {
    if (typeof normalizeProviderSettingsPayload !== 'function' || typeof renderProviderSelect !== 'function') {
      setTimeout(ready, 50);
      return;
    }
    if (typeof I18N !== 'undefined') {
      I18N.fa.provider_deepgram = 'Deepgram API';
      I18N.en.provider_deepgram = 'Deepgram API';
    }
    const oldNormalize = normalizeProviderSettingsPayload;
    normalizeProviderSettingsPayload = function(payload) {
      const out = oldNormalize(payload);
      const incoming = Array.isArray(payload?.providers) ? payload.providers : [];
      const found = incoming.find((item) => String(item?.name || '').toLowerCase() === 'deepgram');
      const field = 'api_' + 'keys';
      const dg = Object.assign({ name: 'deepgram', enabled: false, base_url: 'https://api.deepgram.com', model: 'nova-3', transcriptions_path: '/v1/listen', timeout_sec: 300, [field]: [] }, found || {});
      dg[field] = Array.isArray(dg[field]) ? dg[field] : [];
      out.providers = out.providers.filter((item) => item.name !== 'deepgram').concat([dg]);
      return out;
    };
    renderProviderSelect = function() {
      if (!els.providerSelect) return;
      const providers = state.providerStatus?.providers || [{ name: 'local', enabled_for_user: true, valid: true, model: state.runtimeSettings.model, reason: 'local backend is available' }];
      els.providerSelect.innerHTML = '';
      providers.filter((item) => ['local', 'openai', 'groq', 'deepgram'].includes(item.name)).forEach((item) => {
        const opt = document.createElement('option');
        opt.value = item.name;
        opt.disabled = !item.enabled_for_user;
        const suffix = item.enabled_for_user ? '' : ` - ${item.reason || 'disabled'}`;
        opt.textContent = `${providerLabel(item.name)}${suffix}`;
        els.providerSelect.appendChild(opt);
      });
      if (!providerEnabled(state.selectedProvider)) {
        state.selectedProvider = 'local';
        localStorage.setItem(PROVIDER_SELECTION_KEY, state.selectedProvider);
      }
      els.providerSelect.value = state.selectedProvider;
      updateProviderHint();
    };
    const oldLoadStatus = loadProviderStatus;
    loadProviderStatus = async function() {
      await oldLoadStatus();
      try {
        const dg = await apiFetch('/providers/deepgram/status', { timeoutMs: 12000 });
        const providers = Array.isArray(state.providerStatus?.providers) ? state.providerStatus.providers : [];
        state.providerStatus.providers = providers.filter((item) => item.name !== 'deepgram').concat([dg]);
        renderProviderSelect();
      } catch {}
    };
    const oldTest = testProviderKey;
    testProviderKey = async function(button) {
      const providerName = String(button.getAttribute('data-provider') || '');
      if (providerName !== 'deepgram') return oldTest(button);
      const row = button.closest('.provider-key-row');
      const card = button.closest('.provider-settings-card');
      const key = String(row?.querySelector('.provider-key-input')?.value || '').trim();
      const statusEl = row?.querySelector('.provider-key-status');
      if (!key) { if (statusEl) statusEl.textContent = 'Key is empty'; return; }
      if (statusEl) statusEl.textContent = 'Testing...';
      button.disabled = true;
      try {
        const out = await apiFetch('/providers/deepgram/test-key', { method: 'POST', body: { provider: providerName, ['api_' + 'key']: key, base_url: String(card?.querySelector('.provider-base-url-input')?.value || '').trim() }, timeoutMs: 45000 });
        if (statusEl) {
          statusEl.textContent = out.valid ? `Valid (${out.reason || 'ok'})` : `Invalid: ${out.reason || out.status_code || '-'}`;
          statusEl.className = `hint provider-key-status ${out.valid ? 'ok' : 'bad'}`;
        }
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = `Failed: ${err.message || err}`;
          statusEl.className = 'hint provider-key-status bad';
        }
      } finally {
        button.disabled = false;
      }
    };
  };
  ready();
})();
"""
        return Response(js, media_type='application/javascript')

    app.router.routes = [route for route in app.router.routes if getattr(route, 'path', None) != '/']
    app.add_api_route('/', patched_user_index, methods=['GET'], include_in_schema=False)
    app.add_api_route('/dg-ui.js', dg_ui_js, methods=['GET'], include_in_schema=False)
