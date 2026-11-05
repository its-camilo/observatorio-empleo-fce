"""Configuración común: base SQLite temporal y secretos de prueba."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


@pytest.fixture()
def bd(tmp_path, monkeypatch):
    """Base SQLite nueva por prueba, con tablas y semilla."""
    url = f"sqlite:///{tmp_path / 'prueba.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET", "secreto-de-prueba-suficientemente-largo-123456")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cliente-prueba.apps.googleusercontent.com")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("AUTH_DEV_MODE", raising=False)
    from observatorio.db.semilla import sembrar_todo
    from observatorio.db.sesion import crear_tablas, fabrica_sesiones

    crear_tablas(url)
    with fabrica_sesiones(url)() as s:
        sembrar_todo(s)
        s.commit()
    return url


@pytest.fixture()
def sesion(bd):
    from observatorio.db.sesion import fabrica_sesiones

    with fabrica_sesiones(bd)() as s:
        yield s


@pytest.fixture()
def detector(sesion):
    from observatorio.pipeline.software import DetectorSoftware

    return DetectorSoftware.desde_bd(sesion)
