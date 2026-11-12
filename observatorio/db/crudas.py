"""Escritura de ofertas crudas tolerante a duplicados (varios fragmentos GHA en paralelo)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
        s.rollback()
