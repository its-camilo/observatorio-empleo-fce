"""Punto de entrada para Vercel (función Python). Expone la app FastAPI con carga perezosa."""
from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_app: Any = None


class _LazyApp:
    async def __call__(self, scope, receive, send):
        global _app
        if _app is None:
            from observatorio.api.main import get_app

            _app = get_app()
        await _app(scope, receive, send)


app = _LazyApp()
