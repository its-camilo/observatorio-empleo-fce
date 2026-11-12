"""OpenRouter: modelo fijo, 429 con Retry-After y circuit breaker."""
from __future__ import annotations

import json

import observatorio.pipeline.llm as modulo
from observatorio.pipeline.llm import ClienteLLM


class _Resp:
    def __init__(self, status_code: int, *, headers=None, payload=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload
        self.text = text or json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_modelo_fijo_openrouter_free(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    c = ClienteLLM(sesion, {"habilitado": True}, ["Economía"])
    assert c.modelo == "openrouter/free"


def test_429_reintenta_con_retry_after_y_luego_ok(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    llamadas = []

    def post(url, **kwargs):
        llamadas.append(kwargs)
        n = len(llamadas)
        if n == 1:
            return _Resp(429, headers={"Retry-After": "0"}, payload={"error": {"message": "rate limited"}})
        return _Resp(
            200,
            payload={"choices": [{"message": {"content": '{"resultados":[]}'}}]},
        )

    monkeypatch.setattr(modulo.requests, "post", post)
    monkeypatch.setattr(modulo.time, "sleep", lambda *_a, **_k: None)
    c = ClienteLLM(sesion, {"habilitado": True, "solicitudes_por_minuto": 60}, ["Economía"])
    datos, modelo = c._llamar([{"role": "user", "content": "{}"}])
    assert datos == {"resultados": []}
    assert modelo == "openrouter/free"
    assert len(llamadas) == 2
    assert all(k["json"]["model"] == "openrouter/free" for k in llamadas)
    assert c.habilitado


def test_429_persistentes_abren_circuito(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def post(url, **kwargs):
        return _Resp(429, payload={"error": {"message": "Too Many Requests"}})

    monkeypatch.setattr(modulo.requests, "post", post)
    monkeypatch.setattr(modulo.time, "sleep", lambda *_a, **_k: None)
    c = ClienteLLM(sesion, {"habilitado": True, "solicitudes_por_minuto": 60}, ["Economía"])
    assert c._llamar([{"role": "user", "content": "{}"}]) == (None, "")
    assert not c.habilitado
    assert "HTTP 429" in c.motivo_inactivo
    assert "Too Many Requests" in c.motivo_inactivo
    resumen = c.resumen()
    assert resumen["motivo_inactivo"] == c.motivo_inactivo


def test_402_abre_circuito_y_resumen(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def post(url, **kwargs):
        return _Resp(402, payload={"error": {"message": "Insufficient credits"}})

    monkeypatch.setattr(modulo.requests, "post", post)
    monkeypatch.setattr(modulo.time, "sleep", lambda *_a, **_k: None)
    c = ClienteLLM(sesion, {"habilitado": True}, ["Economía"])
    c._llamar([{"role": "user", "content": "{}"}])
    assert "HTTP 402" in c.resumen()["motivo_inactivo"]
    assert "Insufficient credits" in c.resumen()["motivo_inactivo"]


def test_clasificar_deja_de_llamar_tras_circuito(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    n_post = {"v": 0}

    def post(url, **kwargs):
        n_post["v"] += 1
        return _Resp(429, payload={"error": {"message": "rate"}})

    monkeypatch.setattr(modulo.requests, "post", post)
    monkeypatch.setattr(modulo.time, "sleep", lambda *_a, **_k: None)
    c = ClienteLLM(sesion, {"habilitado": True, "tamano_lote": 1, "solicitudes_por_minuto": 60}, ["Economía"])
    # dos lotes; tras circuito en el primero no debe haber más POST
    ofertas = [
        {"id": "1", "cargo": "X", "empresa": "Y", "termino_busqueda": "z", "descripcion": "d"},
        {"id": "2", "cargo": "A", "empresa": "B", "termino_busqueda": "z", "descripcion": "d"},
    ]
    out = c.clasificar(ofertas)
    assert out == {}
    assert n_post["v"] == modulo.MAX_REINTENTOS
    assert not c.habilitado
