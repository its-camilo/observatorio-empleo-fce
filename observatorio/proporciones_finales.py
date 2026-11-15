"""Ajuste de proporciones en ofertas guardadas (±pp sobre plan) sin borrar filas."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
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


def _pesos_plan(params: dict, cfg: dict) -> tuple[dict[str, float], dict[str, float], dict[tuple[str, str], float]]:
    pf, pc, pfc = presupuestos_guardadas(params, cfg)
    total_f = sum(int(v) for v in pf.values()) or 1
    total_c = sum(int(v) for v in pc.values()) or 1
    total_fc = sum(int(v) for row in pfc.values() for v in row.values()) or 1
    p_src = {f: int(v) / total_f for f, v in pf.items()}
    p_car = {c: int(v) / total_c for c, v in pc.items()}
    p_fc: dict[tuple[str, str], float] = {}
    for f, row in pfc.items():
        fk = f if f in p_src else FUENTE_INV.get(f, f)
        for c, v in row.items():
            p_fc[(fk, c)] = int(v) / total_fc
    return p_src, p_car, p_fc


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
        if abs(actual - plan * 100) > delta_pp + 1e-4:
            return False
    for c, plan in p_car.items():
        actual = _pct(por_c.get(c, 0), total)
        if abs(actual - plan * 100) > delta_pp + 1e-4:
            return False
    return True


def _margen_filas(
    celdas: list[tuple[str, str]],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    total: int,
    n_vars: int,
    x_cols: slice,
) -> tuple[list[np.ndarray], list[float], list[float]]:
    tol = delta_pp / 100.0
    rows: list[np.ndarray] = []
    lb_rows: list[float] = []
    ub_rows: list[float] = []

    eq = np.zeros(n_vars)
    for i in range(len(celdas)):
        eq[x_cols.start + i] = 1.0
    rows.append(eq)
    lb_rows.append(float(total))
    ub_rows.append(float(total))

    for f in p_src:
        row = np.zeros(n_vars)
        for i, key in enumerate(celdas):
            if key[0] == f:
                row[x_cols.start + i] = 1.0
        rows.append(row)
        lb_rows.append((p_src[f] - tol) * total)
        ub_rows.append((p_src[f] + tol) * total)

    for c in p_car:
        row = np.zeros(n_vars)
        for i, key in enumerate(celdas):
            if key[1] == c:
                row[x_cols.start + i] = 1.0
        rows.append(row)
        lb_rows.append((p_car[c] - tol) * total)
        ub_rows.append((p_car[c] + tol) * total)

    return rows, lb_rows, ub_rows


def _vector_a_conteos(x: np.ndarray, celdas: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    return {celdas[i]: int(x[i]) for i in range(len(celdas))}


def _milp_factible(
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    total: int,
) -> bool:
    if total == 0:
        return True
    celdas = sorted(av_fc.keys())
    m = len(celdas)
    caps = np.array([int(av_fc[k]) for k in celdas], dtype=float)
    if total > int(caps.sum()):
        return False

    rows, lb_rows, ub_rows = _margen_filas(celdas, p_src, p_car, delta_pp, total, m, slice(0, m))
    A = np.vstack(rows)
    res = milp(
        c=-np.ones(m),
        integrality=np.ones(m, dtype=int),
        bounds=Bounds(np.zeros(m), caps),
        constraints=LinearConstraint(A, np.array(lb_rows), np.array(ub_rows)),
    )
    if not res.success or res.x is None:
        return False
    x = np.round(res.x).astype(int)
    x = np.clip(x, 0, caps.astype(int))
    if int(x.sum()) != total:
        return False
    counts = _vector_a_conteos(x, celdas)
    por_f: dict[str, int] = defaultdict(int)
    por_c: dict[str, int] = defaultdict(int)
    for (s, c), n in counts.items():
        por_f[s] += n
        por_c[c] += n
    return dentro_tolerancia(por_f, por_c, total, p_src, p_car, delta_pp)


def _milp_asignar(
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    total: int,
    p_fc: dict[tuple[str, str], float] | None,
) -> dict[tuple[str, str], int] | None:
    celdas = sorted(av_fc.keys())
    m = len(celdas)
    caps = np.array([int(av_fc[k]) for k in celdas], dtype=int)
    if total == 0:
        return {k: 0 for k in celdas}

    targets = np.array(
        [
            (p_fc.get(k, p_src[k[0]] * p_car[k[1]]) if p_fc else p_src[k[0]] * p_car[k[1]]) * total
            for k in celdas
        ],
        dtype=float,
    )

    n_slack = 2 * m
    n_vars = m + n_slack
    x_slice = slice(0, m)

    rows, lb_rows, ub_rows = _margen_filas(celdas, p_src, p_car, delta_pp, total, n_vars, x_slice)
    for i in range(m):
        row = np.zeros(n_vars)
        row[i] = 1.0
        row[m + i] = -1.0
        row[m + m + i] = 1.0
        rows.append(row)
        lb_rows.append(float(targets[i]))
        ub_rows.append(float(targets[i]))

    A = np.vstack(rows)
    c_obj = np.zeros(n_vars)
    c_obj[m:] = 1.0
    integrality = np.ones(n_vars, dtype=int)
    integrality[m:] = 0

    res = milp(
        c=c_obj,
        integrality=integrality,
        bounds=Bounds(
            np.concatenate([np.zeros(m), np.zeros(n_slack)]),
            np.concatenate([caps.astype(float), np.full(n_slack, np.inf)]),
        ),
        constraints=LinearConstraint(A, np.array(lb_rows), np.array(ub_rows)),
    )
    if not res.success or res.x is None:
        return _milp_asignar_simple(av_fc, p_src, p_car, delta_pp, total)

    x = np.floor(res.x[:m] + 1e-6).astype(int)
    x = np.clip(x, 0, caps)
    x = _reparar_suma_entera(x, caps, celdas, p_src, p_car, delta_pp, total, p_fc)
    if x is None:
        return _milp_asignar_simple(av_fc, p_src, p_car, delta_pp, total)
    return _vector_a_conteos(x, celdas)


def _milp_asignar_simple(
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    total: int,
) -> dict[tuple[str, str], int] | None:
    celdas = sorted(av_fc.keys())
    m = len(celdas)
    caps = np.array([int(av_fc[k]) for k in celdas], dtype=float)
    rows, lb_rows, ub_rows = _margen_filas(celdas, p_src, p_car, delta_pp, total, m, slice(0, m))
    A = np.vstack(rows)
    res = milp(
        c=-np.ones(m),
        integrality=np.ones(m, dtype=int),
        bounds=Bounds(np.zeros(m), caps),
        constraints=LinearConstraint(A, np.array(lb_rows), np.array(ub_rows)),
    )
    if not res.success or res.x is None:
        return None
    x = np.round(res.x).astype(int)
    x = np.clip(x, 0, caps.astype(int))
    if int(x.sum()) != total:
        x = _reparar_suma_entera(x, caps.astype(int), celdas, p_src, p_car, delta_pp, total, None)
        if x is None:
            return None
    counts = _vector_a_conteos(x, celdas)
    por_f: dict[str, int] = defaultdict(int)
    por_c: dict[str, int] = defaultdict(int)
    for (s, c), n in counts.items():
        por_f[s] += n
        por_c[c] += n
    if not dentro_tolerancia(por_f, por_c, total, p_src, p_car, delta_pp):
        return None
    return counts


def _reparar_suma_entera(
    x: np.ndarray,
    caps: np.ndarray,
    celdas: list[tuple[str, str]],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    objetivo: int,
    p_fc: dict[tuple[str, str], float] | None,
) -> np.ndarray | None:
    x = x.copy()
    diff = objetivo - int(x.sum())
    targets = None
    if p_fc:
        targets = {celdas[i]: p_fc.get(celdas[i], 0) * objetivo for i in range(len(celdas))}

    def viable(vec: np.ndarray) -> bool:
        counts = _vector_a_conteos(vec, celdas)
        por_f: dict[str, int] = defaultdict(int)
        por_c: dict[str, int] = defaultdict(int)
        for (s, c), n in counts.items():
            por_f[s] += n
            por_c[c] += n
        return dentro_tolerancia(por_f, por_c, objetivo, p_src, p_car, delta_pp)

    guard = 0
    while diff != 0 and guard < 100000:
        guard += 1
        if diff < 0:
            candidatos = [i for i in range(len(celdas)) if x[i] > 0]
            if not candidatos:
                return None
            if targets:
                i = max(candidatos, key=lambda j: (x[j] - targets.get(celdas[j], 0), x[j]))
            else:
                i = max(candidatos, key=lambda j: x[j])
            x[i] -= 1
            diff += 1
        else:
            candidatos = [i for i in range(len(celdas)) if x[i] < caps[i]]
            if not candidatos:
                return None
            if targets:
                i = max(candidatos, key=lambda j: (targets.get(celdas[j], 0) - x[j], -j))
            else:
                i = max(candidatos, key=lambda j: (caps[j] - x[j]))
            x[i] += 1
            diff -= 1
    if int(x.sum()) != objetivo or not viable(x):
        return None
    return x


def resolver_conteos_celdas(
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    p_fc: dict[tuple[str, str], float] | None = None,
) -> dict[tuple[str, str], int]:
    max_cap = sum(av_fc.values())
    if max_cap == 0:
        return {}

    lo, hi = 0, max_cap
    mejor_t = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if _milp_factible(av_fc, p_src, p_car, delta_pp, mid):
            mejor_t = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if mejor_t == 0:
        return {k: 0 for k in av_fc}

    sol = _milp_asignar(av_fc, p_src, p_car, delta_pp, mejor_t, p_fc)
    if sol is not None:
        return sol

    sol = _milp_asignar_simple(av_fc, p_src, p_car, delta_pp, mejor_t)
    if sol is not None:
        return sol

    return _mejor_esfuerzo_desviacion(av_fc, p_src, p_car, p_fc)


def _mejor_esfuerzo_desviacion(
    av_fc: dict[tuple[str, str], int],
    p_src: dict[str, float],
    p_car: dict[str, float],
    p_fc: dict[tuple[str, str], float] | None,
) -> dict[tuple[str, str], int]:
    max_cap = sum(av_fc.values())
    mejor: tuple[float, int, dict[tuple[str, str], int]] | None = None
    for t in range(max_cap, 0, -1):
        sol = _milp_asignar_simple(av_fc, p_src, p_car, 100.0, t)
        if sol is None:
            continue
        por_f: dict[str, int] = defaultdict(int)
        por_c: dict[str, int] = defaultdict(int)
        for (s, c), n in sol.items():
            por_f[s] += n
            por_c[c] += n
        dev = 0.0
        for f, plan in p_src.items():
            dev = max(dev, abs(_pct(por_f.get(f, 0), t) - plan * 100))
        for c, plan in p_car.items():
            dev = max(dev, abs(_pct(por_c.get(c, 0), t) - plan * 100))
        cand = (dev, -t, sol)
        if mejor is None or cand < mejor:
            mejor = cand
    return mejor[2] if mejor else {k: 0 for k in av_fc}


def seleccionar_por_omision(
    scored: list[OfertaScored],
    p_src: dict[str, float],
    p_car: dict[str, float],
    delta_pp: float,
    p_fc: dict[tuple[str, str], float] | None = None,
) -> set[str]:
    if not scored:
        return set()

    por_celda: dict[tuple[str, str], list[OfertaScored]] = defaultdict(list)
    for s in scored:
        por_celda[(s.fuente_key, s.carrera)].append(s)
    for items in por_celda.values():
        items.sort(key=lambda x: x.score_sort)

    av_fc = {k: len(v) for k, v in por_celda.items()}
    objetivos = resolver_conteos_celdas(av_fc, p_src, p_car, delta_pp, p_fc)

    keep: set[str] = set()
    for key, items in por_celda.items():
        n = objetivos.get(key, 0)
        for s in items[:n]:
            keep.add(s.oferta.id_oferta)
    return keep


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
    p_fc: dict[tuple[str, str], float] | None = None,
) -> int:
    return sum(resolver_conteos_celdas(av_fc, p_src, p_car, delta_pp, p_fc).values())


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

    p_src, p_car, p_fc = _pesos_plan(params, cfg)
    scored = _score_ofertas(activas)
    keep = seleccionar_por_omision(scored, p_src, p_car, delta_pp, p_fc)

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