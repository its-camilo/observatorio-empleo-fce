"""Escritura de ofertas crudas tolerante a duplicados (varios fragmentos GHA en paralelo)."""
from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.exc import DisconnectionError, IntegrityError, OperationalError
from sqlalchemy.exc import PendingRollbackError, ResourceClosedError
from sqlalchemy.orm import Session

from observatorio.db.modelos import OfertaCruda


def ids_crudas_ejecucion_fuente(s: Session, id_ejecucion: str, fuente: str) -> set[str]:
    return set(
        s.scalars(
            select(OfertaCruda.id_fuente).where(
                OfertaCruda.id_ejecucion == id_ejecucion,
                OfertaCruda.fuente == fuente,
            )
        )
    )


def insertar_cruda(
    s: Session,
    *,
    id_ejecucion: str,
    fuente: str,
    id_fuente: str,
    termino: str,
    carrera_termino: str | None,
    ubicacion: str | None,
    datos: dict,
) -> bool:
    """Inserta una fila cruda; False si ya existe (otro worker o consulta previa)."""
    fila = OfertaCruda(
        id_ejecucion=id_ejecucion,
        fuente=fuente,
        id_fuente=id_fuente,
        termino=termino,
        carrera_termino=carrera_termino,
        ubicacion=ubicacion,
        datos=datos,
    )
    try:
        with s.begin_nested():
            s.add(fila)
            s.flush()
        return True
    except IntegrityError:
        return False


def commit_extraccion(s: Session) -> None:
    try:
        s.commit()
    except IntegrityError:
        s.rollback()


def asegurar_sesion_activa(s: Session) -> None:
    """Tras un error de BD, la sesión queda invalidada hasta hacer rollback."""
    if not s.is_active:
        try:
            s.rollback()
        except Exception:  # noqa: BLE001
            pass


ERRORES_CONEXION_BD = (OperationalError, ResourceClosedError, DisconnectionError, PendingRollbackError)


def es_error_conexion_bd(exc: BaseException) -> bool:
    if isinstance(exc, ERRORES_CONEXION_BD):
        return True
    if "invalid transaction is rolled back" in str(exc).lower():
        return True
    causa = getattr(exc, "orig", None)
    return isinstance(causa, ERRORES_CONEXION_BD)


def recuperar_sesion_db(s: Session) -> None:
    """Tras pérdida de conexión: revierte, invalida el socket y deja la sesión lista para un checkout nuevo."""
    try:
        s.rollback()
    except Exception:  # noqa: BLE001
        pass
    url = str(s.get_bind().url)
    if url.startswith("sqlite"):
        return
    try:
        s.connection().invalidate()
    except Exception:  # noqa: BLE001
        pass


def liberar_conexion_para_espera(s: Session) -> None:
    """Cierra la transacción y devuelve la conexión al pool antes de esperas largas (p. ej. OpenRouter).

    En SQLAlchemy 2.x basta con ``commit()`` (o ``rollback()`` si falló): la conexión vuelve al pool y
    no se mantiene SSL ocioso hacia Neon. No se llama a ``connection.invalidate()`` aquí: invalidar con
    la sesión aún ligada a una transacción deja ``PendingRollbackError`` en la siguiente operación.
    """
    try:
        s.commit()
    except Exception:  # noqa: BLE001
        try:
            s.rollback()
        except Exception:  # noqa: BLE001
            pass


def esperar_backoff_reintento(intento: int, base: float = 5.0) -> None:
    time.sleep(base * (intento + 1))
