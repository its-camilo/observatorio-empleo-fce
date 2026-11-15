"""Ajuste de proporciones en ofertas guardadas (±pp sobre plan) sin borrar filas."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.cupos_guardadas import FUENTE_INV, presupuestos_guardadas
from observatorio.db.modelos import Ejecucion, Oferta
from observatorio.normas_corrida import NOMBRES_FUENTE

log = logging.getLogger("observatorio.proporciones")

MOTIVO_AJUSTE = "ajuste_proporcion"
_PESO_CLASIF = {"reglas": 0, "reglas_termino": 1, "reglas_respaldo": 2, "llm": 3}


@dataclass
class OfertaScored:
    oferta: Oferta
    fuente_key: str
    carrera: str
    score_sort: tuple


def _config_ajuste(cfg: dict) -> tuple[bool, float]:
    raw = cfg.get("ajuste_proporcion_final") or {}
    if isinstance(raw, dict):
        if not raw.get("habilitado", True):
            return False, 0.0
        return True, float(raw.get("tolerancia_proporcion_pp", 5))
    tol = cfg.get("tolerancia_proporcion_pp")
    if tol is None:
        return True, 5.0
    if tol is False or (isinstance(tol, (int, float)) and float(tol) <= 0):
        return False, 0.0
    return True, float(tol)


def _pesos_plan(params: dict, cfg: dict) -> tuple[dict[str, float], dict[str, float]]:
    pf, pc, _pfc = presupuestos_guardadas(params, cfg)
    total_f = sum(int(v) for v in pf.values()) or 1
    total_c = sum(int(v) for v in pc.values()) or 1
    p_src = {f: int(v) / total_f for f, v in pf.items()}
    p_car = {c: int(v) / total_c for c, v in pc.items()}
    return p_src, p_car


def puntaje_omision(o: Oferta) -> tuple:
    rank = _PESO_CLASIF.get(o.clasificado_por or "", 5)
    desc_len = len(o.descripcion or "")
    fp: date | None = o.fecha_publicacion
    fp_ord = fp.toordinal() if fp else 0
    return (rank, desc_len, fp_ord, o.id_oferta)


def _contadores(pool: list[OfertaScored]) -> tuple[dict[str, int], dict[str, int]]:
    por_f: dict[str, int] = {}
    por_c: dict[str, int] = {}
    for s in pool:
        por_f[s.fuente_key] = por_f.get(s.fuente_key, 0) + 1
        por_c[s.carrera] = por_c.get(s.carrera, 0) + 1
    return por_f, por_c


def _pct(n: int, total: int) -> float:
    return 100.0 * n / total if total else 0.0


def _exceso_fuente(por_f: dict[str, int], total: int, p_src: dict[str, float], delta_pp: float) -> str | None:
    peor: tuple[float, str] | None = None
    for f, plan in p_src.items():
        actual = _pct(por_f.get(f, 0), total)
        plan_pct = plan * 100
        if actual > plan_pct + delta_pp + 1e-9:
            exceso = actual - (plan_pct + delta_pp)
            if peor is None or exceso > peor[0]:
                peor = (exceso, f)
    return peor[1] if peor else None


def _exceso_carrera(por_c: dict[str, int], total: int, p_car: dict[str, float], delta_pp: float) -> str | None:
    peor: tuple[float, str] | None = None
    for c, plan in p_car.items():
        actual = _pct(por_c.get(c, 0), total)
        plan_pct = plan * 100
        if actual > plan_pct + delta_pp + 1e-9:
            exceso = actual - (plan_pct + delta_pp)
            if peor is None or exceso > peor[0]:
                peor = (exceso, c)
    return peor[1] if peor else None


def dentro_tolerancia(
    por_f: dict[str, int],
    por_c: dict[str, int],
    total: int,
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
) -> bool:
    if total == 0:
        return True
    for f, plan in p_src.items():
        actual = _pct(por_f.get(f, 0), total)
        if abs(actual - plan * 100) > delta_pp + 1e-6:
            return False
    for c, plan in p_car.items():
        actual = _pct(por_c.get(c, 0), total)
        if abs(actual - plan * 100) > delta_pp + 1e-6:
            return False
    return True


def sin_sobre_representacion(
    por_f: dict[str, int],
    por_c: dict[str, int],
    total: int,
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
) -> bool:
    """Lo alcanzable omitiendo solo excedentes (no corrige sub-representación)."""
    if total == 0:
        return True
    for f, plan in p_src.items():
        if _pct(por_f.get(f, 0), total) > plan * 100 + delta_pp + 1e-6:
            return False
    for c, plan in p_car.items():
        if _pct(por_c.get(c, 0), total) > plan * 100 + delta_pp + 1e-6:
            return False
    return True


def seleccionar_por_omision(
    scored: list[OfertaScored],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
) -> set[str]:
    """Omite ofertas de celdas sobre-representadas hasta no queden excedentes por fuente/carrera."""
    if not scored:
        return set()

    def _ids(items: list[OfertaScored]) -> set[str]:
        return {s.oferta.id_oferta for s in items}

    pool = list(scored)
    mejor_ids: set[str] | None = None
    mejor_n = 0

    while len(pool) > 0:
        por_f, por_c = _contadores(pool)
        total = len(pool)
        if sin_sobre_representacion(por_f, por_c, total, p_src, p_car, delta_pp):
            if total > mejor_n:
                mejor_n = total
                mejor_ids = _ids(pool)
            break
        f_ex = _exceso_fuente(por_f, total, p_src, delta_pp)
        c_ex = _exceso_carrera(por_c, total, p_car, delta_pp)
        if f_ex is None and c_ex is None:
            break
        if f_ex is None:
            objetivo_f = False
            objetivo = c_ex
        elif c_ex is None:
            objetivo_f = True
            objetivo = f_ex
        elif _rank_exceso_f(por_f, total, p_src, delta_pp, f_ex) >= _rank_exceso_c(
            por_c, total, p_car, delta_pp, c_ex
        ):
            objetivo_f = True
            objetivo = f_ex
        else:
            objetivo_f = False
            objetivo = c_ex
        candidatos = (
            [s for s in pool if s.fuente_key == objetivo]
            if objetivo_f
            else [s for s in pool if s.carrera == objetivo]
        )
        if not candidatos:
            break
        elim = min(candidatos, key=lambda s: s.score_sort)
        pool.remove(elim)

    if mejor_ids is not None:
        return mejor_ids
    if len(pool) > 0:
        por_f, por_c = _contadores(pool)
        if sin_sobre_representacion(por_f, por_c, len(pool), p_src, p_car, delta_pp):
            return _ids(pool)
    return set()


def _rank_exceso_f(por_f, total, p_src, delta, f):
    return _pct(por_f.get(f, 0), total) - (p_src[f] * 100 + delta)


def _rank_exceso_c(por_c, total, p_car, delta, c):
    return _pct(por_c.get(c, 0), total) - (p_car[c] * 100 + delta)


def _score_ofertas(ofertas: Iterable[Oferta]) -> list[OfertaScored]:
    out: list[OfertaScored] = []
    for o in ofertas:
        fk = FUENTE_INV.get(o.fuente, o.fuente.lower())
        cp = (o.carrera_principal or "").strip()
        if not fk or not cp:
            continue
        out.append(OfertaScored(o, fk, cp, puntaje_omision(o)))
    out.sort(key=lambda s: s.score_sort)
    return out


def max_total_factible(
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
) -> int:
    """Máximo N tal que existe subconjunto con conteos por celda ≤ av y márgenes en tolerancia."""
    items: list[OfertaScored] = []
    for (f, c), n in av_fc.items():
        for i in range(n):
            stub = Oferta(
                id_oferta=f"{f}-{c}-{i}",
                fuente=NOMBRES_FUENTE.get(f, f),
                carrera_principal=c,
                clasificado_por="reglas",
                descripcion="x" * (10 + i),
            )
            items.append(OfertaScored(stub, f, c, (0, len(stub.descripcion or ""), i, stub.id_oferta)))
    kept = seleccionar_por_omision(items, p_src, p_car, delta_pp)
    return len(kept)


def factible_total(
    total: int,
    av_src: dict[str, int],
    av_car: dict[str, int],
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
) -> bool:
    return max_total_factible(av_fc, p_src, p_car, delta_pp) >= total


def recomputar_ajuste_proporcion(s: Session, ejec: Ejecucion, cfg: dict) -> dict:
    habilitado, delta_pp = _config_ajuste(cfg)
    params = ejec.parametros or {}
    if not habilitado:
        return {"aplicado": False, "motivo": "deshabilitado"}
    if getattr(ejec, "modo", None) == "prueba":
        return {"aplicado": False, "motivo": "modo_prueba"}

    ofertas = list(s.scalars(select(Oferta).where(Oferta.id_ejecucion == ejec.id_ejecucion)))
    for o in ofertas:
        if o.motivo_exclusion_corrida == MOTIVO_AJUSTE:
            o.excluida_resultado_corrida = False
            o.motivo_exclusion_corrida = None

    activas = [o for o in ofertas if not o.excluida_resultado_corrida]
    if not activas:
        return {"aplicado": False, "motivo": "sin_ofertas"}

    p_src, p_car = _pesos_plan(params, cfg)
    scored = _score_ofertas(activas)
    keep = seleccionar_por_omision(scored, p_src, p_car, delta_pp)

    omitidas_por_celda: dict[str, int] = {}
    total_omit = 0
    for o in activas:
        if o.id_oferta in keep:
            continue
        fk = FUENTE_INV.get(o.fuente, o.fuente.lower())
        cp = (o.carrera_principal or "").strip()
        o.excluida_resultado_corrida = True
        o.motivo_exclusion_corrida = MOTIVO_AJUSTE
        total_omit += 1
        clave = f"{NOMBRES_FUENTE.get(fk, fk)} · {cp}"
        omitidas_por_celda[clave] = omitidas_por_celda.get(clave, 0) + 1

    incluidas = [o for o in ofertas if not o.excluida_resultado_corrida]
    por_f, por_c = _contadores(_score_ofertas(incluidas))
    n = len(incluidas)
    plan_f = {NOMBRES_FUENTE.get(f, f): round(p * 100, 2) for f, p in p_src.items()}
    resumen = {
        "aplicado": True,
        "tolerancia_pp": delta_pp,
        "total_disponible": len(activas),
        "total_incluidas": n,
        "omitidas_ajuste": total_omit,
        "omitidas_por_celda": omitidas_por_celda,
        "plan_fuente_pct": plan_f,
        "plan_carrera_pct": {k: round(v * 100, 2) for k, v in p_car.items()},
        "final_fuente_pct": {NOMBRES_FUENTE.get(f, f): round(_pct(por_f.get(f, 0), n), 2) for f in p_src},
        "final_carrera_pct": {c: round(_pct(por_c.get(c, 0), n), 2) for c in p_car},
        "dentro_tolerancia": dentro_tolerancia(por_f, por_c, n, p_src, p_car, delta_pp),
    }
    log.info(
        "Ajuste proporción %s: %d incluidas, %d omitidas (±%.1f pp)",
        ejec.id_ejecucion,
        n,
        total_omit,
        delta_pp,
    )
    return resumen


def aplicar_tras_consolidar(s: Session, ejec: Ejecucion, cfg: dict) -> None:
    resumen = recomputar_ajuste_proporcion(s, ejec, cfg)
    if not resumen.get("aplicado"):
        return
    params = dict(ejec.parametros or {})
    params["ajuste_proporcion"] = resumen
    ejec.parametros = params
    if resumen.get("omitidas_ajuste"):
        det = list(ejec.errores_detalle or [])
        msg = (
            f"Ajuste de proporción: {resumen['omitidas_ajuste']} ofertas excluidas del resultado "
            f"({resumen['total_incluidas']} incluidas). Detalle por celda: {resumen.get('omitidas_por_celda')}"
        )
        if msg not in det:
            det.append(msg)
        ejec.errores_detalle = det