"""Integración Postgres: liberar conexión antes de espera LLM sin PendingRollbackError."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.orm import Session

from observatorio.db.crudas import liberar_conexion_para_espera, recuperar_sesion_db
from observatorio.db.modelos import Ejecucion, OfertaCruda
from observatorio.db.semilla import sembrar_todo
from observatorio.db.sesion import fabrica_sesiones, motor


def _postgres_url() -> str | None:
    url = os.getenv("OBSERVATORIO_TEST_POSTGRES_URL") or os.getenv("TEST_POSTGRES_URL")
    if not url:
        return None
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@pytest.fixture(scope="module")
def postgres_url():
    url = _postgres_url()
    if not url:
        pytest.skip("Define OBSERVATORIO_TEST_POSTGRES_URL para pruebas Postgres")
    return url


@pytest.fixture()
def sesion_pg(postgres_url, monkeypatch):
    from observatorio.db.modelos import Base

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    eng = motor(postgres_url)
    Base.metadata.create_all(eng)
    with fabrica_sesiones(postgres_url)() as s:
        sembrar_todo(s)
        s.commit()
    with fabrica_sesiones(postgres_url)() as s:
        yield s
        s.rollback()


def test_liberar_tras_lectura_permite_flush_como_tras_espera_llm(sesion_pg: Session):
    """Replica el flujo: lecturas en bloque → liberar (espera LLM) → escritura."""
    idx = "pg-liberar-1"
    sesion_pg.add(
        Ejecucion(id_ejecucion=idx, semestre="2026-II", corte="Mitad", estado="en_curso", modo="completa")
    )
    sesion_pg.commit()

    list(
        sesion_pg.scalars(
            select(OfertaCruda).where(OfertaCruda.id_ejecucion == idx, OfertaCruda.procesada.is_(False))
        )
    )
    liberar_conexion_para_espera(sesion_pg)

    sesion_pg.add(
        OfertaCruda(
            id_ejecucion=idx,
            fuente="Indeed",
            id_fuente="pg-1",
            termino="contador",
            carrera_termino="Contaduría Pública",
            datos={"cargo": "contador", "ubicacion": "Bogotá"},
        )
    )
    sesion_pg.flush()
    sesion_pg.rollback()


def test_invalidate_sin_rollback_previo_deja_pending_rollback(sesion_pg: Session):
    """Documenta la regresión de #20: invalidate con sesión sucia → PendingRollbackError."""
    sesion_pg.execute(text("SELECT 1"))
    conn = sesion_pg.connection()
    conn.invalidate()
    with pytest.raises(PendingRollbackError):
        sesion_pg.execute(text("SELECT 2"))
    recuperar_sesion_db(sesion_pg)
    sesion_pg.execute(text("SELECT 3"))