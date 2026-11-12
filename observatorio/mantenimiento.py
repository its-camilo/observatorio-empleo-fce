"""Tareas de mantenimiento de datos (términos retirados, purga por reglas de relevancia)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Oferta, TerminoBusqueda, Validacion
from observatorio.parametros import leer_config, valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo
from observatorio.pipeline.software import DetectorSoftware
from observatorio.pipeline.valor_formativo import oferta_tiene_valor_formativo

# Términos que dejaron de usarse en terminos.json; se desactivan en bases ya sembradas.
TERMINOS_BUSQUEDA_RETIRADOS: tuple[str, ...] = (
    "asistente administrativo",
    "auxiliar administrativo",
    "coordinador administrativo",
    "aprendiz administrativo",
    "practicante administrativo",
    "gestión administrativa",
)

MOTIVO_OPERATIVO = "cargo_operativo"
MOTIVO_SIN_FORMATIVO = "sin_software_ni_habilidad"


def patrones_exclusion_operativa(s: Session | None = None) -> list[str]:
    if s is not None:
        return list(leer_config(s).get("exclusion_operativa_titulo") or [])
    return list(valores_por_defecto().get("exclusion_operativa_titulo") or [])


def config_purga(s: Session) -> dict:
    return leer_config(s)


def motivo_purga_oferta(
    cargo: str,
    descripcion: str | None,
    empresa: str | None,
    *,
    patrones: list[str],
    detector: DetectorSoftware,
    requiere_formativo: bool,
) -> str | None:
    """Motivo de borrado por reglas (sin LLM), o None si la oferta se conserva."""
    if titulo_excluido_operativo(cargo or "", patrones):
        return MOTIVO_OPERATIVO
    if requiere_formativo:
        ok, _ = oferta_tiene_valor_formativo(cargo or "", descripcion or "", detector, empresa=empresa or "")
        if not ok:
            return MOTIVO_SIN_FORMATIVO
    return None


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


def _scan_ofertas_por_reglas(
    s: Session,
    patrones: list[str],
    detector: DetectorSoftware,
    requiere_formativo: bool,
    *,
    max_ejemplos: int = 20,
) -> tuple[list[str], dict[str, int], dict[str, list[str]]]:
    ids: list[str] = []
    conteos: dict[str, int] = defaultdict(int)
    ejemplos: dict[str, list[str]] = defaultdict(list)
    ultimo = ""
    while True:
        filas = s.execute(
            select(Oferta.id_oferta, Oferta.cargo, Oferta.descripcion, Oferta.empresa)
            .where(Oferta.id_oferta > ultimo)
            .order_by(Oferta.id_oferta)
            .limit(2000)
        ).all()
        if not filas:
            break
        for oid, cargo, descripcion, empresa in filas:
            ultimo = oid
            motivo = motivo_purga_oferta(
                cargo or "",
                descripcion,
                empresa,
                patrones=patrones,
                detector=detector,
                requiere_formativo=requiere_formativo,
            )
            if not motivo:
                continue
            ids.append(oid)
            conteos[motivo] += 1
            if cargo and len(ejemplos[motivo]) < max_ejemplos and cargo not in ejemplos[motivo]:
                ejemplos[motivo].append(cargo)
    return ids, dict(conteos), dict(ejemplos)


def purgar_por_reglas(s: Session, *, aplicar: bool = False, max_ejemplos: int = 20) -> dict:
    """Reevalúa todas las ofertas con exclusión operativa y valor formativo (sin LLM)."""
    cfg = config_purga(s)
    patrones = list(cfg.get("exclusion_operativa_titulo") or [])
    requiere = bool(cfg.get("requiere_software_o_habilidad", True))
    detector = DetectorSoftware.desde_bd(s)
    ids, conteos, ejemplos = _scan_ofertas_por_reglas(
        s, patrones, detector, requiere, max_ejemplos=max_ejemplos,
    )
    salida: dict = {
        "candidatas": len(ids),
        "eliminadas": 0,
        "validaciones": 0,
        "por_motivo": conteos,
        "requiere_software_o_habilidad": requiere,
    }
    if not aplicar:
        if ejemplos:
            salida["ejemplos_por_motivo"] = ejemplos
        # Compatibilidad con salida anterior de purga operativa
        ops = ejemplos.get(MOTIVO_OPERATIVO, [])
        if ops:
            salida["ejemplos_cargos"] = ops
        return salida
    if not ids:
        return salida
    n_val = s.scalar(select(func.count()).select_from(Validacion).where(Validacion.id_oferta.in_(ids))) or 0
    if n_val:
        s.execute(delete(Validacion).where(Validacion.id_oferta.in_(ids)))
    r = s.execute(delete(Oferta).where(Oferta.id_oferta.in_(ids)))
    s.flush()
    salida["eliminadas"] = r.rowcount or 0
    salida["validaciones"] = n_val
    return salida


def purgar_ofertas_operativas(s: Session, *, aplicar: bool = False, max_ejemplos: int = 20) -> dict:
    """Alias histórico: aplica la purga completa por reglas (operativo + valor formativo)."""
    return purgar_por_reglas(s, aplicar=aplicar, max_ejemplos=max_ejemplos)
