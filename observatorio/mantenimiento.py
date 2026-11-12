"""Tareas de mantenimiento de datos (términos retirados, purga por reglas de relevancia)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Oferta, TerminoBusqueda, Validacion
from observatorio.parametros import leer_config, valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo
from observatorio.pipeline.software import DetectorSoftware
from observatorio.pipeline.valor_formativo import oferta_tiene_valor_formativo, tiene_descripcion_util
from observatorio.texto import limpiar_espacios

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
MOTIVO_SIN_DESCRIPCION = "sin_descripcion"

# Motivos que no se borran con --aplicar por defecto (solo informativos en vista previa).
MOTIVOS_NO_PURGABLES = frozenset({MOTIVO_SIN_DESCRIPCION})

_FRAGMENTO_DESC = 160


def patrones_exclusion_operativa(s: Session | None = None) -> list[str]:
    if s is not None:
        return list(leer_config(s).get("exclusion_operativa_titulo") or [])
    return list(valores_por_defecto().get("exclusion_operativa_titulo") or [])


def config_purga(s: Session) -> dict:
    return leer_config(s)


def _fragmento_descripcion(descripcion: str | None) -> str:
    d = limpiar_espacios(descripcion or "")
    if not d:
        return ""
    return d[:_FRAGMENTO_DESC] + ("…" if len(d) > _FRAGMENTO_DESC else "")


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
        if not tiene_descripcion_util(descripcion):
            return MOTIVO_SIN_DESCRIPCION
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
) -> tuple[list[str], dict[str, int], dict[str, int], dict[str, list[str]], list[dict]]:
    ids_purgables: list[str] = []
    conteos: dict[str, int] = defaultdict(int)
    por_fuente: dict[str, int] = defaultdict(int)
    ejemplos_cargo: dict[str, list[str]] = defaultdict(list)
    ejemplos_detalle: list[dict] = []
    ultimo = ""
    while True:
        filas = s.execute(
            select(Oferta.id_oferta, Oferta.cargo, Oferta.descripcion, Oferta.empresa, Oferta.fuente)
            .where(Oferta.id_oferta > ultimo)
            .order_by(Oferta.id_oferta)
            .limit(2000)
        ).all()
        if not filas:
            break
        for oid, cargo, descripcion, empresa, fuente in filas:
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
            conteos[motivo] += 1
            if motivo not in MOTIVOS_NO_PURGABLES:
                ids_purgables.append(oid)
                por_fuente[fuente or "Sin dato"] += 1
            if cargo and len(ejemplos_cargo[motivo]) < max_ejemplos and cargo not in ejemplos_cargo[motivo]:
                ejemplos_cargo[motivo].append(cargo)
            if len(ejemplos_detalle) < max_ejemplos:
                ejemplos_detalle.append(
                    {
                        "id_oferta": oid,
                        "cargo": cargo,
                        "fuente": fuente,
                        "motivo": motivo,
                        "descripcion_fragmento": _fragmento_descripcion(descripcion),
                        "purgable": motivo not in MOTIVOS_NO_PURGABLES,
                    }
                )
    return ids_purgables, dict(conteos), dict(por_fuente), dict(ejemplos_cargo), ejemplos_detalle


def purgar_por_reglas(s: Session, *, aplicar: bool = False, max_ejemplos: int = 20) -> dict:
    """Reevalúa todas las ofertas con exclusión operativa y valor formativo (sin LLM)."""
    cfg = config_purga(s)
    patrones = list(cfg.get("exclusion_operativa_titulo") or [])
    requiere = bool(cfg.get("requiere_software_o_habilidad", True))
    detector = DetectorSoftware.desde_bd(s)
    total_ofertas = s.scalar(select(func.count()).select_from(Oferta)) or 0
    ids, conteos, por_fuente, ejemplos, ejemplos_detalle = _scan_ofertas_por_reglas(
        s, patrones, detector, requiere, max_ejemplos=max_ejemplos,
    )
    salida: dict = {
        "total_ofertas": total_ofertas,
        "candidatas_purgables": len(ids),
        "candidatas": len(ids),
        "eliminadas": 0,
        "validaciones": 0,
        "por_motivo": conteos,
        "por_fuente_purgables": por_fuente,
        "requiere_software_o_habilidad": requiere,
        "motivos_no_purgables": sorted(MOTIVOS_NO_PURGABLES),
    }
    if not aplicar:
        if ejemplos:
            salida["ejemplos_por_motivo"] = ejemplos
        if ejemplos_detalle:
            salida["ejemplos"] = ejemplos_detalle
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
