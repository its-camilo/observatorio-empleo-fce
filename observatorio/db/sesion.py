"""Conexión a la base de datos (Postgres en producción, SQLite para pruebas)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from observatorio.config import ajustes

_motores: dict[str, Engine] = {}


def motor(url: str | None = None) -> Engine:
    url = url or ajustes().database_url
    if url not in _motores:
        kwargs: dict = {"pool_pre_ping": True, "future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs.update(pool_size=3, max_overflow=2, pool_recycle=300)
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
