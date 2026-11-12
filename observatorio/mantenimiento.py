"""Tareas de mantenimiento de datos (términos retirados, ofertas operativas)."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Oferta, TerminoBusqueda, Validacion
from observatorio.parametros import valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo

# Términos que dejaron de usarse en terminos.json; se desactivan en bases ya sembradas.
TERMINOS_BUSQUEDA_RETIRADOS: tuple[str, ...] = (
    "asistente administrativo",
    "auxiliar administrativo",
    "coordinador administrativo",
    "aprendiz administrativo",
    "practicante administrativo",
    "gestión administrativa",
)


def patrones_exclusion_operativa(s: Session | None = None) -> list[str]:
    if s is not None:
        from observatorio.parametros import leer_config

        return list(leer_config(s).get("exclusion_operativa_titulo") or [])
    return list(valores_por_defecto().get("exclusion_operativa_titulo") or [])


def desactivar_terminos_retirados(s: Session) -> int:
    """Marca como inactivos los términos de búsqueda operativos retirados del catálogo."""
    terminos = list(
        s.scalars(
            select(TerminoBusqueda).where(
                TerminoBusqueda.termino.in_(TERMINOS_BUSQUEDA_RETIRADOS),
                TerminoBusqueda.activo.is_(True),
            )
        )
    )
    for t in terminos:
        t.activo = False
    s.flush()
    return len(terminos)


def _scan_ofertas_operativas(
    s: Session, patrones: list[str], *, max_ejemplos: int = 20
) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    ejemplos: list[str] = []
    ultimo = ""
    while True:
        filas = s.execute(
            select(Oferta.id_oferta, Oferta.cargo)
            .where(Oferta.id_oferta > ultimo)
            .order_by(Oferta.id_oferta)
            .limit(2000)
        ).all()
        if not filas:
            break
        for oid, cargo in filas:
            ultimo = oid
            if cargo and titulo_excluido_operativo(cargo, patrones):
                ids.append(oid)
                if len(ejemplos) < max_ejemplos and cargo not in ejemplos:
                    ejemplos.append(cargo)
    return ids, ejemplos


def purgar_ofertas_operativas(s: Session, *, aplicar: bool = False, max_ejemplos: int = 20) -> dict:
    """Elimina ofertas cuyo cargo coincide con exclusion_operativa_titulo."""
    patrones = patrones_exclusion_operativa(s)
    ids, ejemplos = _scan_ofertas_operativas(s, patrones, max_ejemplos=max_ejemplos)
    if not aplicar or not ids:
        salida: dict = {"candidatas": len(ids), "eliminadas": 0, "validaciones": 0}
        if not aplicar and ejemplos:
            salida["ejemplos_cargos"] = ejemplos
        return salida
    n_val = s.scalar(select(func.count()).select_from(Validacion).where(Validacion.id_oferta.in_(ids))) or 0
    if n_val:
        s.execute(delete(Validacion).where(Validacion.id_oferta.in_(ids)))
    r = s.execute(delete(Oferta).where(Oferta.id_oferta.in_(ids)))
    s.flush()
    return {"candidatas": len(ids), "eliminadas": r.rowcount or 0, "validaciones": n_val}
