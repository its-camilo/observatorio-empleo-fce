"""Catálogo OpenRouter: modelos gratuitos disponibles para clasificación por corrida."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from observatorio.config import MODELOS_OPENROUTER_POR_DEFECTO

log = logging.getLogger("observatorio.llm")

MODELOS_URL = "https://openrouter.ai/api/v1/models"
_CACHE_TTL_SEG = 3600

# Módulo: catálogo reciente; por corrida: lista ya resuelta (consolidar).
_cache_catalogo: dict[str, Any] = {"ts": 0.0, "gratis": set()}
_cache_por_corrida: dict[str, list[str]] = {}


def _precio_cero(val: object) -> bool:
    if val is None:
        return False
    try:
        return float(val) == 0.0
    except (TypeError, ValueError):
        return str(val).strip() in {"0", "0.0"}


def es_modelo_gratis(model: dict) -> bool:
    mid = model.get("id") or ""
    if mid.endswith(":free"):
        return True
    pricing = model.get("pricing") or {}
    return _precio_cero(pricing.get("prompt")) and _precio_cero(pricing.get("completion"))


def soporta_clasificacion_json(model: dict) -> bool:
    arch = model.get("architecture") or {}
    modality = str(arch.get("modality") or "")
    if "->text" in modality and "+audio" in modality.split("->")[-1]:
        return False
    params = model.get("supported_parameters") or []
    return "response_format" in params or "structured_outputs" in params


def _catalogo_gratis(api_key: str | None) -> set[str]:
    now = time.time()
    if _cache_catalogo.get("gratis") and now - float(_cache_catalogo.get("ts") or 0) < _CACHE_TTL_SEG:
        return set(_cache_catalogo["gratis"])

    headers = {
        "HTTP-Referer": "https://github.com/its-camilo/observatorio-empleo-fce",
        "X-Title": "Observatorio de Empleo FCE",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = requests.get(MODELOS_URL, headers=headers, timeout=45)
        r.raise_for_status()
        gratis = {
            m["id"]
            for m in r.json().get("data", [])
            if m.get("id") and es_modelo_gratis(m) and soporta_clasificacion_json(m)
        }
        _cache_catalogo.update({"ts": now, "gratis": gratis})
        log.info("OpenRouter: %d modelos gratuitos con JSON en catálogo", len(gratis))
        return set(gratis)
    except requests.RequestException as e:
        log.warning("No se pudo consultar %s: %s", MODELOS_URL, e)
        previo = _cache_catalogo.get("gratis")
        return set(previo) if previo else set()


def resolver_modelos(
    *,
    preferidos: list[str],
    api_key: str | None,
    id_corrida: str | None = None,
) -> list[str]:
    """Orden: preferidos que sigan gratis → resto del catálogo. Cache por id de ejecución."""
    if id_corrida and id_corrida in _cache_por_corrida:
        return list(_cache_por_corrida[id_corrida])

    disponibles = _catalogo_gratis(api_key)
    preferencia = [m for m in preferidos if m] or list(MODELOS_OPENROUTER_POR_DEFECTO)
    elegidos: list[str] = []
    vistos: set[str] = set()

    for mid in preferencia:
        if mid in disponibles and mid not in vistos:
            elegidos.append(mid)
            vistos.add(mid)

    extras = sorted(m for m in disponibles if m not in vistos)
    if "openrouter/free" in extras:
        extras.remove("openrouter/free")
        extras.insert(0, "openrouter/free")
    elegidos.extend(extras)

    if not elegidos and preferencia:
        log.warning(
            "Ningún modelo preferido está en el catálogo gratuito; se omiten llamadas LLM (solo reglas)."
        )

    if id_corrida:
        _cache_por_corrida[id_corrida] = list(elegidos)

    return elegidos


def limpiar_cache_corrida(id_corrida: str) -> None:
    _cache_por_corrida.pop(id_corrida, None)
