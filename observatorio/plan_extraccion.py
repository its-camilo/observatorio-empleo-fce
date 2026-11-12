"""Presupuesto de extracción por corrida: un objetivo global repartido entre fuentes."""
from __future__ import annotations

import math

# LinkedIn primero y con algo más de cupo que el resto.
ORDEN_FUENTES = ("linkedin", "indeed", "computrabajo", "google")
PESOS_FUENTE = {"linkedin": 0.38, "indeed": 0.27, "computrabajo": 0.25, "google": 0.10}


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


def ordenar_fuentes(activas: list[str]) -> list[str]:
    vistos = set()
    ordenadas: list[str] = []
    for f in ORDEN_FUENTES:
        if f in activas:
            ordenadas.append(f)
            vistos.add(f)
    for f in activas:
        if f not in vistos:
            ordenadas.append(f)
    return ordenadas


def presupuesto_por_fuente(objetivo: int, fuentes: list[str]) -> dict[str, int]:
    """Reparte el objetivo entre fuentes activas según PESOS_FUENTE."""
    if objetivo <= 0 or not fuentes:
        return {}
    ordenadas = ordenar_fuentes(fuentes)
    total_peso = sum(PESOS_FUENTE.get(f, 0.1) for f in ordenadas)
    reparto: dict[str, int] = {}
    restante = objetivo
    for i, f in enumerate(ordenadas):
        if i == len(ordenadas) - 1:
            reparto[f] = max(0, restante)
        else:
            cupo = max(1, int(round(objetivo * PESOS_FUENTE.get(f, 0.1) / total_peso)))
            cupo = min(cupo, restante)
            reparto[f] = cupo
            restante -= cupo
    return reparto


def max_particiones_fuente(presupuesto: int, max_por_particion: int) -> int:
    """Cuántas consultas (término × ciudad) crear como máximo para una fuente."""
    max_por_particion = max(1, max_por_particion)
    if presupuesto <= 0:
        return 0
    return max(1, math.ceil(presupuesto / max_por_particion))
