"""Reparto de cupos por fuente y carrera (porcentajes que suman 100)."""
from __future__ import annotations

from typing import Iterable

FUENTES_EXTRACCION = ("linkedin", "indeed", "computrabajo")

DISTRIBUCION_FUENTES_DEFECTO = {"linkedin": 42, "indeed": 30, "computrabajo": 28}

TOLERANCIA_SUMA = 0.05


def distribucion_carreras_igualitaria(carreras: Iterable[str]) -> dict[str, float]:
    lista = list(carreras)
    if not lista:
        return {}
    base = round(100 / len(lista), 2)
    out = {c: base for c in lista}
    # Ajuste fino para sumar 100
    diff = round(100 - sum(out.values()), 2)
    if diff and lista:
        out[lista[0]] = round(out[lista[0]] + diff, 2)
    return out


def normalizar_porcentajes(valores: dict[str, float | int]) -> dict[str, float]:
    limpios = {k: max(0.0, float(v or 0)) for k, v in valores.items()}
    total = sum(limpios.values())
    if total <= 0:
        raise ValueError("La suma de porcentajes debe ser mayor que cero para normalizar.")
    return {k: round(v * 100 / total, 2) for k, v in limpios.items()}


def validar_distribucion(valores: dict[str, float | int], *, claves: list[str] | None = None) -> dict[str, float]:
    """Devuelve porcentajes validados (no negativos, suma ≈ 100)."""
    if not isinstance(valores, dict) or not valores:
        raise ValueError("Indique un objeto con porcentajes por clave.")
    if claves:
        for c in claves:
            if c not in valores:
                raise ValueError(f"Falta el porcentaje de «{c}».")
    limpios = {k: max(0.0, float(v or 0)) for k, v in valores.items()}
    if any(float(v or 0) < 0 for v in valores.values()):
        raise ValueError("No se permiten porcentajes negativos.")
    total = sum(limpios.values())
    if total <= 0:
        raise ValueError("Al menos una clave debe tener porcentaje mayor que cero.")
    if abs(total - 100) > TOLERANCIA_SUMA:
        raise ValueError(f"Los porcentajes deben sumar 100 (suma actual: {total:.2f}).")
    return {k: round(v, 2) for k, v in limpios.items()}


def repartir_enteros(total: int, porcentajes: dict[str, float]) -> dict[str, int]:
    """Reparte `total` en enteros según porcentajes; la suma coincide exactamente con `total`."""
    if total <= 0:
        return {k: 0 for k in porcentajes}
    activos = [(k, p) for k, p in porcentajes.items() if p > 0]
    if not activos:
        return {k: 0 for k in porcentajes}
    peso_total = sum(p for _, p in activos)
    partes: list[tuple[str, int, float]] = []
    asignado = 0
    for k, p in activos:
        exacto = total * p / peso_total
        entero = int(exacto)
        partes.append((k, entero, exacto - entero))
        asignado += entero
    resto = total - asignado
    partes.sort(key=lambda x: -x[2])
    salida = {k: e for k, e, _ in partes}
    for i in range(resto):
        salida[partes[i % len(partes)][0]] += 1
    for k in porcentajes:
        salida.setdefault(k, 0)
    return salida
