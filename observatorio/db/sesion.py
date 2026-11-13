"""Conexión a la base de datos (Postgres en producción, SQLite para pruebas)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from observatorio.config import ajustes

_motores: dict[str, Engine] = {}


def _serverless_postgres() -> bool:
    return bool(os.getenv("VERCEL")) or os.getenv("OBSERVATORIO_SERVERLESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def motor(url: str | None = None) -> Engine:
    url = url or ajustes().database_url
    if url not in _motores:
        kwargs: dict = {"pool_pre_ping": True, "future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        elif _serverless_postgres():
            kwargs["poolclass"] = NullPool
            kwargs["connect_args"] = {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "8") or 8)}
        else:
            kwargs.update(pool_size=3, max_overflow=2, pool_recycle=240)
            # Keepalives TCP: los runners de GitHub (Azure) cortan conexiones inactivas ~4 min y Neon cierra el SSL.
            # Pasa mientras se espera a OpenRouter o a una fuente con la transacción abierta.
            kwargs["connect_args"] = {
                "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10") or 10),
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }
        eng = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(eng, "connect")
            def _fk(dbapi_con, _):  # activa claves foráneas en SQLite
                cur = dbapi_con.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        _motores[url] = eng
    return _motores[url]


def fabrica_sesiones(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=motor(url), expire_on_commit=False, future=True)


@contextmanager
def sesion(url: str | None = None) -> Iterator[Session]:
    s = fabrica_sesiones(url)()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def crear_tablas(url: str | None = None) -> None:
    """Crea las tablas directamente (SQLite/pruebas). En Postgres use Alembic."""
    from observatorio.db.modelos import Base

    Base.metadata.create_all(motor(url))


def latencia_bd_segundos() -> float:
    """Consulta liviana `SELECT 1` (incluye conexión y cold start de Neon si aplica)."""
    import time

    t0 = time.perf_counter()
    with motor().connect() as con:
        con.execute(text("SELECT 1"))
    return time.perf_counter() - t0
