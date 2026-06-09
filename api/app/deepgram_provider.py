from __future__ import annotations

import importlib

_mod = importlib.import_module('.dg_runtime', __package__)
getattr(_mod, 'install_dg_runtime')()
