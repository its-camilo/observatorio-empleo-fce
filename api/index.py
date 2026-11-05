"""Punto de entrada para Vercel (función Python). Expone la app FastAPI."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observatorio.api.main import app  # noqa: E402,F401
