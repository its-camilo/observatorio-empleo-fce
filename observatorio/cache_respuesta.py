"""Caché en memoria con TTL para respuestas de API (proceso serverless)."""
from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_lock = Lock()
_almacen: dict[str, tuple[float, Any]] = {}


def obtener_o_calcular(clave: str, ttl_segundos: float, calcular: Callable[[], T]) -> T:
    ahora = time.monotonic()
    with _lock:
        hit = _almacen.get(clave)
        if hit is not None and ahora - hit[0] < ttl_segundos:
            return hit[1]
    valor = calcular()
    with _lock:
        _almacen[clave] = (ahora, valor)
    return valor


def invalidar_prefijo(prefijo: str) -> None:
    with _lock:
        for k in list(_almacen):
            if k.startswith(prefijo):
                del _almacen[k]


def invalidar_caches_analitica() -> None:
    """Tras consolidar un corte nuevo o cambiar ofertas visibles en reportes."""
    for prefijo in (
        "cortes_disponibles",
        "resumen:",
        "analisis:",
        "dashboard:",
        "filtros:",
        "total_historico",
        "corridas:list",
    ):
        invalidar_prefijo(prefijo)
