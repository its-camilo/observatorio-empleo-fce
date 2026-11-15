"""Consolidar no debe llamar a OpenRouter."""
from __future__ import annotations

import requests

from observatorio import orquestador as orq
from tests.test_pipeline import crudas


def test_consolidar_sin_http_openrouter(sesion, monkeypatch):
    llamadas: list[str] = []

    def post(url, *args, **kwargs):
        llamadas.append(str(url))
        if "openrouter.ai" in str(url).lower():
            raise AssertionError(f"Llamada HTTP prohibida a OpenRouter: {url}")
        raise AssertionError(f"HTTP inesperado durante consolidar: {url}")

    def get(url, *args, **kwargs):
        llamadas.append(str(url))
        if "openrouter.ai" in str(url).lower():
            raise AssertionError(f"Llamada HTTP prohibida a OpenRouter: {url}")
        raise AssertionError(f"HTTP inesperado durante consolidar: {url}")

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests.Session, "post", post)
    monkeypatch.setattr(requests.Session, "get", get)

    orq.preparar(sesion, "2026-II", "inicio", "t-open", fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
    sesion.commit()
    crudas(sesion, "t-open", [
        dict(
            fuente="LinkedIn",
            id_fuente="x1",
            url="u",
            cargo="Analista financiero",
            empresa="Firma",
            ubicacion="Bogotá, Colombia",
            fecha_publicacion="2026-11-01",
            descripcion="Economía, Excel y análisis de datos",
            carrera="Economía",
        ),
    ])
    ej = orq.consolidar(sesion, "t-open")
    assert ej.fase == "terminada"
    assert not any("openrouter.ai" in u.lower() for u in llamadas)