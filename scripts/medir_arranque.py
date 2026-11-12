#!/usr/bin/env python3
"""Mide tiempo de import de la API y (opcional) rutas con TestClient."""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def medir_import() -> float:
    t0 = time.perf_counter()
    import observatorio.api.main  # noqa: F401

    return time.perf_counter() - t0


def medir_rutas() -> dict[str, float]:
  from fastapi.testclient import TestClient
  from observatorio.api.main import crear_app

  app = crear_app()
  c = TestClient(app)
  out: dict[str, float] = {}
  for metodo, ruta in [("GET", "/api/salud"), ("GET", "/api/salud?db=1")]:
      t0 = time.perf_counter()
      if metodo == "GET":
          c.get(ruta.split("?")[0] + ("?" + ruta.split("?", 1)[1] if "?" in ruta else ""))
      out[ruta] = time.perf_counter() - t0
  return out


def main() -> None:
    imp = medir_import()
    print(f"import observatorio.api.main: {imp * 1000:.0f} ms")
    if os.getenv("MEDIR_RUTAS"):
        for ruta, seg in medir_rutas().items():
            print(f"  {ruta}: {seg * 1000:.0f} ms")


if __name__ == "__main__":
    main()
