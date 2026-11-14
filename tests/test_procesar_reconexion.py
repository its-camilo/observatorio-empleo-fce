"""Reintento de procesamiento tras pérdida de conexión Neon/SQLAlchemy."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import ResourceClosedError

from observatorio.db.modelos import Ejecucion, Oferta, OfertaCruda
from observatorio.parametros import leer_config
from observatorio.pipeline.procesar import Procesador
import observatorio.pipeline.procesar as mod_procesar


def _cruda(id_ejecucion: str, sufijo: str, cargo: str) -> OfertaCruda:
    return OfertaCruda(
        id_ejecucion=id_ejecucion,
        fuente="Indeed",
        id_fuente=f"indeed-{sufijo}",
        termino="contador",
        carrera_termino="Contaduría Pública",
        datos={
            "cargo": cargo,
            "descripcion": "contabilidad NIIF análisis financiero",
            "ubicacion": "Bogotá, Colombia",
        },
    )


def test_procesar_pendientes_reintenta_bloque_sin_duplicar(sesion, monkeypatch):
    monkeypatch.setattr(mod_procesar, "TAMANO_BLOQUE", 1)
    monkeypatch.setattr(mod_procesar, "REINTENTOS_BLOQUE", 3)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    idx = "recon-bd-1"
    sesion.add(Ejecucion(id_ejecucion=idx, semestre="2026-II", corte="Mitad", estado="en_curso"))
    sesion.add(_cruda(idx, "a", "contador público"))
    sesion.add(_cruda(idx, "b", "contador auditoría"))
    sesion.commit()

    ejec = sesion.get(Ejecucion, idx)
    proc = Procesador(sesion, ejec, leer_config(sesion), usar_llm=False)

    commits = {"n": 0}
    real_commit = sesion.commit

    def commit_con_fallo_en_segundo_bloque():
        commits["n"] += 1
        if commits["n"] == 2:
            raise ResourceClosedError("simulado")
        return real_commit()

    monkeypatch.setattr(sesion, "commit", commit_con_fallo_en_segundo_bloque)

    proc.procesar_pendientes()

    pendientes = sesion.scalar(
        select(func.count())
        .select_from(OfertaCruda)
        .where(OfertaCruda.id_ejecucion == idx, OfertaCruda.procesada.is_(False))
    )
    assert pendientes == 0
    assert commits["n"] >= 3


def test_liberar_invalida_en_lugar_de_cerrar(monkeypatch):
    from observatorio.db.crudas import liberar_conexion_para_espera
    from unittest.mock import MagicMock

    cerrado = {"close": 0, "invalidate": 0}
    conn = MagicMock()
    conn.close = lambda: cerrado.__setitem__("close", cerrado["close"] + 1)
    conn.invalidate = lambda: cerrado.__setitem__("invalidate", cerrado["invalidate"] + 1)
    s = MagicMock()
    s.get_bind.return_value.url = "postgresql://user@host/db"
    s.commit = MagicMock()
    s.connection.return_value = conn

    liberar_conexion_para_espera(s)
    assert cerrado["invalidate"] == 1
    assert cerrado["close"] == 0