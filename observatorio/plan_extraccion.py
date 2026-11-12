"""Presupuesto de extracción por corrida: objetivo global repartido entre fuentes y carreras."""
from __future__ import annotations

import math

from observatorio.distribucion import (
    DISTRIBUCION_FUENTES_DEFECTO,
    FUENTES_EXTRACCION,
    distribucion_carreras_igualitaria,
    repartir_enteros,
)

ORDEN_FUENTES = FUENTES_EXTRACCION


def objetivo_ofertas_corrida(cfg: dict, parametros_ejec: dict | None = None) -> int:
    """Número objetivo de ofertas crudas a recolectar (0 = sin tope explícito → meta histórica 10 000)."""
    if parametros_ejec and "objetivo_ofertas_corrida" in parametros_ejec:
        return max(0, int(parametros_ejec["objetivo_ofertas_corrida"] or 0))
    if cfg.get("objetivo_ofertas_corrida") is not None:
        return max(0, int(cfg["objetivo_ofertas_corrida"]))
    lim = int(cfg.get("limite_extraccion_corrida") or 0)
    if lim > 0:
        return lim
    return max(0, int(cfg.get("meta_ofertas", 10000)))


def porcentajes_fuentes(cfg: dict) -> dict[str, float]:
    raw = cfg.get("distribucion_fuentes") or DISTRIBUCION_FUENTES_DEFECTO
    return {f: float(raw.get(f, 0) or 0) for f in FUENTES_EXTRACCION}


def porcentajes_carreras(cfg: dict) -> dict[str, float]:
    carreras = list(cfg.get("carreras") or [])
    raw = cfg.get("distribucion_carreras")
    if not raw:
        return distribucion_carreras_igualitaria(carreras)
    return {c: float(raw.get(c, 0) or 0) for c in carreras}


def fuentes_para_corrida(cfg: dict, fuentes_solicitadas: list[str] | None = None) -> list[str]:
    """Fuentes activas en configuración, con % > 0 y sin Google Jobs."""
    cfg_fuentes = cfg.get("fuentes") or {}
    pct = porcentajes_fuentes(cfg)
    activas = [
        f
        for f in ORDEN_FUENTES
        if cfg_fuentes.get(f, {}).get("activa", True) and pct.get(f, 0) > 0
    ]
    if fuentes_solicitadas:
        permitidas = {x.strip().lower() for x in fuentes_solicitadas if x.strip()}
        activas = [f for f in activas if f in permitidas]
    return ordenar_fuentes(activas)


def ordenar_fuentes(activas: list[str]) -> list[str]:
    vistos = set()
    ordenadas: list[str] = []
    for f in ORDEN_FUENTES:
        if f in activas:
            ordenadas.append(f)
            vistos.add(f)
    for f in activas:
        if f not in vistos and f != "google":
            ordenadas.append(f)
    return ordenadas


def presupuesto_por_fuente(objetivo: int, fuentes: list[str], cfg: dict) -> dict[str, int]:
    """Reparte el objetivo entre fuentes según config.distribucion_fuentes."""
    if objetivo <= 0 or not fuentes:
        return {}
    pct = {f: porcentajes_fuentes(cfg).get(f, 0) for f in fuentes}
    pct = {f: p for f, p in pct.items() if p > 0}
    if not pct:
        return {}
    return repartir_enteros(objetivo, pct)


def presupuesto_por_carrera(objetivo: int, cfg: dict) -> dict[str, int]:
    carreras = list(cfg.get("carreras") or [])
    if objetivo <= 0 or not carreras:
        return {}
    pct = porcentajes_carreras(cfg)
    pct = {c: pct.get(c, 0) for c in carreras if pct.get(c, 0) > 0}
    if not pct:
        return {}
    return repartir_enteros(objetivo, pct)


def max_particiones_fuente(presupuesto: int, max_por_particion: int) -> int:
    """Cuántas consultas (término × ciudad) crear como máximo para una fuente."""
    max_por_particion = max(1, max_por_particion)
    if presupuesto <= 0:
        return 0
    return max(1, math.ceil(presupuesto / max_por_particion))


def presupuesto_fuente_carrera(presupuesto_fuentes: dict[str, int], cfg: dict) -> dict[str, dict[str, int]]:
    """Cupo de cada fuente repartido entre carreras (así ninguna carrera se queda sin consultas en ninguna fuente)."""
    salida: dict[str, dict[str, int]] = {}
    for f, cupo in (presupuesto_fuentes or {}).items():
        if int(cupo or 0) > 0:
            reparto = presupuesto_por_carrera(int(cupo), cfg)
            if reparto:
                salida[f] = reparto
    return salida
