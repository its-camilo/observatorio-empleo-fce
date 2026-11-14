"""Consolidación tolerante al LLM y modo solo_consolidar."""
from __future__ import annotations

import json
import observatorio.pipeline.llm as modulo
from observatorio.pipeline.llm import ClienteLLM
from observatorio.pipeline.procesar import Procesador


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


def test_json_invalido_no_tumba_clasificar_y_usa_respaldo(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def post(url, **kwargs):
        return _Resp(200, payload={"choices": [{"message": {"content": "no es json"}}]})

    monkeypatch.setattr(modulo.requests, "post", post)
    monkeypatch.setattr(modulo.time, "sleep", lambda *_a, **_k: None)
    c = ClienteLLM(
        sesion,
        {"habilitado": True, "tamano_lote": 2, "max_fallos_consecutivos_lote": 50, "solicitudes_por_minuto": 60},
        ["Economía"],
    )
    ofertas = [
        {"id": "1", "cargo": "auxiliar contable", "empresa": "ACME", "termino_busqueda": "contador", "descripcion": "datos"},
        {"id": "2", "cargo": "analista", "empresa": "ACME", "termino_busqueda": "economía", "descripcion": "excel"},
    ]
    out = c.clasificar(ofertas)
    assert out == {}
    assert c.errores >= 1
    assert c.habilitado


def test_muchos_fallos_consecutivos_abren_circuito_sin_excepcion(sesion, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def post(url, **kwargs):
        return _Resp(200, payload={"choices": [{"message": {"content": ""}}]})

    monkeypatch.setattr(modulo.requests, "post", post)
    monkeypatch.setattr(modulo.time, "sleep", lambda *_a, **_k: None)
    c = ClienteLLM(
        sesion,
        {
            "habilitado": True,
            "tamano_lote": 1,
            "max_fallos_consecutivos_lote": 3,
            "solicitudes_por_minuto": 60,
            "max_solicitudes_corrida": 100,
        },
        ["Economía"],
    )
    ofertas = [{"id": str(i), "cargo": "x", "empresa": "y", "termino_busqueda": "z", "descripcion": "d"} for i in range(5)]
    out = c.clasificar(ofertas)
    assert not out
    assert not c.habilitado
    assert "demasiados fallos" in c.motivo_inactivo


def test_procesar_bloque_tolera_excepcion_llm(sesion, monkeypatch):
    from sqlalchemy import select

    from observatorio.db.modelos import Ejecucion, OfertaCruda
    from observatorio.parametros import leer_config
    from observatorio.pipeline.clasificacion import Clasificacion
    import observatorio.pipeline.procesar as mod_procesar

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def clasificar_reglas(*_a, **_k):
        return Clasificacion("dudosa", [], {}, "dudosa", "reglas")

    monkeypatch.setattr(mod_procesar.ClasificadorReglas, "clasificar", staticmethod(clasificar_reglas))

    ejec = Ejecucion(id_ejecucion="t-llm-fallo", semestre="2026-II", corte="Mitad", estado="en_curso")
    sesion.add(ejec)
    sesion.add(
        OfertaCruda(
            id_ejecucion="t-llm-fallo",
            fuente="Indeed",
            id_fuente="indeed-1",
            datos={
                "cargo": "auxiliar administrativo",
                "descripcion": "soporte procesos y excel",
                "ubicacion": "Bogotá, Colombia",
            },
            termino="administración",
            carrera_termino="Administración de Empresas",
        )
    )
    sesion.commit()
    cfg = leer_config(sesion)
    proc = Procesador(sesion, ejec, cfg, usar_llm=True)

    def boom(_ofertas):
        raise RuntimeError("fallo simulado del cliente")

    proc.llm.clasificar = boom  # type: ignore[method-assign]
    crudas = list(sesion.scalars(select(OfertaCruda)))
    r = proc.procesar_bloque(crudas)
    assert r.crudas == 1
    assert r.por_respaldo >= 0


def test_preparar_solo_consolidar_congela_presupuestos(sesion):
    from sqlalchemy import func, select

    from observatorio import orquestador as orq
    from observatorio.db.modelos import Ejecucion, Particion

    orq.preparar(sesion, "2026-II", "mitad", "solo-cong", modo="completa", ejecutor="test")
    e = sesion.get(Ejecucion, "solo-cong")
    presu_viejo = dict((e.parametros or {}).get("presupuesto_fuentes") or {})
    n_part = sesion.scalar(select(func.count()).select_from(Particion).where(Particion.id_ejecucion == "solo-cong"))
    e2 = orq.preparar(sesion, "2026-II", "mitad", "solo-cong", solo_consolidar=True)
    assert (e2.parametros or {}).get("presupuesto_fuentes") == presu_viejo
    assert e2.fase == "procesando"
    assert n_part > 0
    n_despues = sesion.scalar(select(func.count()).select_from(Particion).where(Particion.id_ejecucion == "solo-cong"))
    assert n_despues == n_part