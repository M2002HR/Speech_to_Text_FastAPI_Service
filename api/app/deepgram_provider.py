from __future__ import annotations

import importlib

_mod = importlib.import_module('.dg_runtime', __package__)
getattr(_mod, 'install_dg_runtime')()

_routes = importlib.import_module('.dg_status_route', __package__)
_main = importlib.import_module('.main', __package__)
getattr(_routes, 'add_route')(_main.app)
