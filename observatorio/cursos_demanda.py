"""Demanda de habilidades en ofertas y recomendación de cursos (RF-19, plan docencia FCE)."""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.analisis import corte_anterior
from observatorio.db.modelos import Curso, Oferta, OfertaSoftware
from observatorio.filtro_ofertas import oferta_incluida_en_resultados

CONSULTA_BUSQUEDA: dict[str, str] = {
    "excel": "Excel avanzado",
    "microsoft excel": "Excel avanzado",
    "power bi": "Power BI",
    "tableau": "Tableau",
    "python": "Python análisis de datos",
    "sql": "SQL base de datos",
    "sap": "SAP FICO",
    "sap fico": "SAP FICO",
    "sap hana": "SAP",
    "niif": "NIIF contabilidad",
    "ifrs": "NIIF IFRS",
    "chatgpt": "ChatGPT productividad",
    "inteligencia artificial": "inteligencia artificial",
    "machine learning": "machine learning",
    "access": "Microsoft Access base de datos",
    "r": "R estadística",
    "spss": "SPSS estadística",
    "stata": "Stata econometría",
    "quickbooks": "QuickBooks contabilidad",
    "siigo": "contabilidad Colombia Siigo",
    "dynamics": "Microsoft Dynamics ERP",
    "oracle": "Oracle ERP finanzas",
    "looker": "Looker BI",
    "qlik": "Qlik Sense",
}


@dataclass
class DemandaHabilidad:
    habilidad: str
    consulta: str
    ofertas: int
    pct: float
    por_carrera: dict[str, dict[str, float]]


def _coincide_frontera(texto: str, fragmento: str) -> bool:
    if not fragmento:
        return False
    return re.search(rf"(?<!\w){re.escape(fragmento)}(?!\w)", texto, re.IGNORECASE) is not None


def consulta_para(habilidad: str) -> str:
    clave = (habilidad or "").strip().lower()
    if not clave:
        return ""
    if clave in CONSULTA_BUSQUEDA:
        return CONSULTA_BUSQUEDA[clave]
    for k, v in CONSULTA_BUSQUEDA.items():
        if len(k) < 3:
            continue
        if _coincide_frontera(clave, k) or _coincide_frontera(k, clave):
            return v
    return habilidad.strip()


def _ofertas_por_carrera(s: Session, semestre: str, corte: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for car, n in s.execute(
        select(Oferta.carrera_principal, func.count())
        .where(Oferta.semestre == semestre, Oferta.corte == corte, oferta_incluida_en_resultados())
        .group_by(Oferta.carrera_principal)
    ):
        if car:
            out[car] = int(n)
    return out


def contar_demanda_software(s: Session, semestre: str, corte: str) -> tuple[int, dict[str, int], dict[str, dict[str, int]]]:
    total_ofertas = int(
        s.scalar(
            select(func.count())
            .select_from(Oferta)
            .where(Oferta.semestre == semestre, Oferta.corte == corte, oferta_incluida_en_resultados())
        )
        or 0
    )
    por_sw: dict[str, set[str]] = defaultdict(set)
    por_sw_car: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    q = (
        select(OfertaSoftware.software, OfertaSoftware.id_oferta, Oferta.carrera_principal)
        .join(Oferta, OfertaSoftware.id_oferta == Oferta.id_oferta)
        .where(
            Oferta.semestre == semestre,
            Oferta.corte == corte,
            oferta_incluida_en_resultados(),
        )
    )
    for software, id_of, carrera in s.execute(q):
        if not software:
            continue
        por_sw[software].add(id_of)
        car = (carrera or "Todas").split("; ")[0]
        por_sw_car[software][car].add(id_of)

    conteos = {sw: len(ids) for sw, ids in por_sw.items()}
    por_carrera = {sw: {c: len(ids) for c, ids in cars.items()} for sw, cars in por_sw_car.items()}
    return total_ofertas, conteos, por_carrera


def _por_carrera_pct(
    cars: dict[str, int],
    totales_car: dict[str, int],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for car, cn in cars.items():
        n_car = totales_car.get(car, 0)
        out[car] = {"n": float(cn), "pct": round(100.0 * cn / n_car, 2) if n_car else 0.0}
    return out


def terminos_para_busqueda_cursos(s: Session, semestre: str, corte: str, cfg: dict) -> list[DemandaHabilidad]:
    """Top N habilidades para buscar cursos en plataformas (tras consolidar)."""
    cc = cfg.get("cursos") or {}
    top_n = int(cc.get("max_terminos_demanda", 25))
    min_ofertas = int(cc.get("min_ofertas_habilidad", 2))
    min_terminos = int(cc.get("min_terminos", 5))
    respaldo = list(cc.get("terminos_respaldo") or [])[:20]
    total, conteos_sw, por_carrera = contar_demanda_software(s, semestre, corte)
    totales_car = _ofertas_por_carrera(s, semestre, corte)

    ordenados = sorted(conteos_sw.items(), key=lambda x: (-x[1], x[0].lower()))
    elegidos: list[DemandaHabilidad] = []
    for habilidad, n in ordenados:
        if n < min_ofertas and total >= min_ofertas * 2:
            continue
        pct = round(100.0 * n / total, 2) if total else 0.0
        elegidos.append(
            DemandaHabilidad(
                habilidad=habilidad,
                consulta=consulta_para(habilidad),
                ofertas=n,
                pct=pct,
                por_carrera=_por_carrera_pct(por_carrera.get(habilidad, {}), totales_car),
            )
        )
        if len(elegidos) >= top_n:
            break

    if len(elegidos) < min_terminos:
        ya = {d.habilidad.lower() for d in elegidos}
        for t in respaldo:
            if t.lower() in ya:
                continue
            elegidos.append(DemandaHabilidad(t, consulta_para(t), 0, 0.0, {}))
            ya.add(t.lower())
            if len(elegidos) >= min_terminos:
                break
    return elegidos


def demanda_temas(
    s: Session,
    semestre: str,
    corte: str,
    cfg: dict,
    limite: int = 80,
    carrera: str | None = None,
) -> list[dict[str, Any]]:
    """Temas (skills) rankeados por demanda en ofertas guardadas del corte."""
    total, conteos, por_carrera = contar_demanda_software(s, semestre, corte)
    totales_car = _ofertas_por_carrera(s, semestre, corte)

    prev = corte_anterior(s, semestre, corte)
    prev_pct: dict[str, float] = {}
    if prev:
        p_sem, p_cor = prev
        total_p, conteos_p, _ = contar_demanda_software(s, p_sem, p_cor)
        for k, n in conteos_p.items():
            prev_pct[k] = round(100.0 * n / total_p, 2) if total_p else 0.0

    items: list[dict[str, Any]] = []
    for habilidad, n in sorted(conteos.items(), key=lambda x: (-x[1], x[0].lower()))[:limite]:
        pct = round(100.0 * n / total, 2) if total else 0.0
        por_car = _por_carrera_pct(por_carrera.get(habilidad, {}), totales_car)
        if carrera and por_car:
            if carrera not in por_car and n == 0:
                continue
        p_ant = prev_pct.get(habilidad)
        items.append(
            {
                "tema": habilidad,
                "grupo": "software",
                "ofertas": n,
                "pct_ofertas": pct,
                "por_carrera": por_car,
                "pct_corte_anterior": p_ant,
                "variacion_pp": round(pct - p_ant, 2) if p_ant is not None else None,
                "semestre": semestre,
                "corte": corte,
                "total_ofertas_corte": total,
            }
        )
    if carrera:
        items = [x for x in items if x["por_carrera"].get(carrera, {}).get("n", 0) > 0 or x["ofertas"] >= 2]
        items.sort(key=lambda x: (-x["por_carrera"].get(carrera, {}).get("pct", 0), -x["ofertas"]))
    return items


def _a_entero_no_negativo(val: Any) -> int:
    if val is None:
        return 0
    if isinstance(val, str):
        s = val.strip().lower()
        if not s or s in ("nan", "inf", "+inf", "-inf", "none", "null"):
            return 0
    try:
        f = float(val)
        if not math.isfinite(f):
            return 0
        n = int(f)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, n)


def _a_float_no_negativo(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, str):
        s = val.strip().lower()
        if not s or s in ("nan", "inf", "+inf", "-inf", "none", "null"):
            return 0.0
    try:
        f = float(val)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not math.isfinite(f):
        return 0.0
    return max(0.0, f)


def _senal_plataforma(c: dict) -> float:
    plat = (c.get("plataforma") or "").lower()
    pos_raw = c.get("posicion")
    pos = max(1, _a_entero_no_negativo(pos_raw) or (20 if pos_raw is None else 1))
    pos_score = 1.0 / pos
    if plat == "edx":
        ins = _a_entero_no_negativo(c.get("inscritos_recientes"))
        return pos_score * math.log1p(ins)
    cal = _a_float_no_negativo(c.get("calificacion"))
    num = _a_entero_no_negativo(c.get("num_calificaciones"))
    if cal > 0 and num > 0:
        return pos_score * cal * math.log1p(num)
    return pos_score


def normalizar_senales_plataforma(cursos: list[dict]) -> None:
    por_plat: dict[str, list[float]] = defaultdict(list)
    for c in cursos:
        por_plat[(c.get("plataforma") or "").lower()].append(_senal_plataforma(c))
    max_plat = {p: max(v) if v else 1.0 for p, v in por_plat.items()}
    for c in cursos:
        plat = (c.get("plataforma") or "").lower()
        c["_senal_plat"] = _senal_plataforma(c) / max(max_plat.get(plat, 1.0), 1e-9)


def calcular_puntaje_recomendacion(demanda_pct: float, senal_plat_norm: float, peso_demanda: float = 0.65) -> float:
    d_norm = min(100.0, max(0.0, demanda_pct)) / 100.0
    return round(peso_demanda * d_norm + (1.0 - peso_demanda) * min(1.0, max(0.0, senal_plat_norm)), 4)


def indice_demanda(terminos: list[DemandaHabilidad]) -> dict[str, DemandaHabilidad]:
    out: dict[str, DemandaHabilidad] = {}
    for d in terminos:
        out[d.habilidad.lower()] = d
        out[d.consulta.lower()] = d
    return out


def serializar_demanda_carreras(por_carrera: dict) -> str | None:
    if not por_carrera:
        return None
    return json.dumps(por_carrera, ensure_ascii=False)


def cursos_referencia_tema(
    s: Session,
    semestre: str,
    corte: str,
    habilidad: str,
    limite: int = 3,
) -> list[dict]:
    clave = habilidad.strip().lower()
    q = (
        select(Curso)
        .where(Curso.semestre == semestre, Curso.corte == corte)
        .where(
            (func.lower(Curso.habilidad_demanda) == clave)
            | (func.lower(Curso.termino).like(f"%{clave[:40]}%"))
        )
        .order_by(Curso.puntaje_recomendacion.desc().nullslast(), Curso.posicion, Curso.id)
        .limit(limite)
    )
    return [
        {
            "titulo": c.titulo,
            "url": c.url,
            "plataforma": c.plataforma,
            "puntaje_recomendacion": c.puntaje_recomendacion,
            "organizacion": c.organizacion,
        }
        for c in s.scalars(q)
    ]


def temas_recomendados_dictado(
    s: Session,
    semestre: str,
    corte: str,
    cfg: dict,
    carrera: str | None = None,
    limite: int = 50,
    incluir_cursos: bool = True,
) -> list[dict[str, Any]]:
    temas = demanda_temas(s, semestre, corte, cfg, limite=limite, carrera=carrera)
    if incluir_cursos:
        for t in temas:
            t["cursos_referencia"] = cursos_referencia_tema(s, semestre, corte, t["tema"])
    return temas


def coincidencia_habilidad(habilidad: str, termino_busqueda: str, idx: dict[str, DemandaHabilidad]) -> DemandaHabilidad | None:
    t = termino_busqueda.lower().strip()
    h = habilidad.lower().strip()
    if t in idx:
        return idx[t]
    if h in idx:
        return idx[h]
    for k, d in idx.items():
        if k in t or t in k or k in h or h in k:
            return d
    return None