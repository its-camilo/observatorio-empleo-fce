"""Eliminación de duplicados (RF-08).

Dos ofertas son la misma si coinciden empresa + cargo + ciudad normalizados y
sus fechas de publicación están a menos de N días (7 por defecto). Si alguna
no tiene fecha, se consideran la misma. Se conserva la que tenga la
descripción más larga. También son duplicadas dos ofertas con el mismo
identificador de la fuente.

Si la empresa es genérica ("Importante empresa del sector"), la clave incluye
el inicio de la descripción para no fusionar ofertas distintas.
"""
from __future__ import annotations

from datetime import date

from observatorio.texto import clave_cargo, clave_ciudad_dedup, clave_empresa, es_empresa_generica, hash_texto


def clave_dedup(empresa: str, cargo: str, ciudad: str, descripcion: str = "") -> str:
    base = f"{clave_empresa(empresa)}|{clave_cargo(cargo)}|{clave_ciudad_dedup(ciudad)}"
    if es_empresa_generica(empresa):
        base += "|" + hash_texto((descripcion or "")[:300].lower())[:12]
    return base


def _cerca(a: date | None, b: date | None, dias: int) -> bool:
    if a is None or b is None:
        return True
    return abs((a - b).days) < dias


def _largo(o: dict) -> int:
    return len(o.get("descripcion") or "")


def deduplicar(ofertas: list[dict], dias: int = 7) -> tuple[list[dict], int]:
    """Deduplica una lista de ofertas (dicts con clave_dedup, fecha_publicacion, descripcion, id_oferta).

    Devuelve (únicas, duplicados_eliminados). Conserva la de descripción más
    larga y le suma los términos de búsqueda de las otras.
    """
    por_id: dict[str, dict] = {}
    duplicados = 0
    for o in ofertas:
        previo = por_id.get(o["id_oferta"])
        if previo is None:
            por_id[o["id_oferta"]] = o
            continue
        duplicados += 1
        por_id[o["id_oferta"]] = _fusionar(previo, o)

    grupos: dict[str, list[dict]] = {}
    for o in por_id.values():
        grupos.setdefault(o["clave_dedup"], []).append(o)

    unicas: list[dict] = []
    for lista in grupos.values():
        lista.sort(key=lambda x: (x.get("fecha_publicacion") or date.min))
        clusters: list[dict] = []
        for o in lista:
            destino = next((c for c in clusters if _cerca(c.get("fecha_publicacion"), o.get("fecha_publicacion"), dias)), None)
            if destino is None:
                clusters.append(o)
            else:
                duplicados += 1
                clusters[clusters.index(destino)] = _fusionar(destino, o)
        unicas.extend(clusters)
    return unicas, duplicados


def _fusionar(a: dict, b: dict) -> dict:
    """Gana la de descripción más larga; se conservan los términos de ambas."""
    ganador, perdedor = (a, b) if _largo(a) >= _largo(b) else (b, a)
    ganador = dict(ganador)
    terminos = [t for t in dict.fromkeys(
        (ganador.get("termino_busqueda") or "").split("; ") + (perdedor.get("termino_busqueda") or "").split("; ")) if t]
    ganador["termino_busqueda"] = "; ".join(terminos)[:250]
    if not ganador.get("fecha_publicacion"):
        ganador["fecha_publicacion"] = perdedor.get("fecha_publicacion")
    if not ganador.get("sector"):
        ganador["sector"] = perdedor.get("sector")
    return ganador


def buscar_en_historial(oferta: dict, existentes: list, dias: int = 7):
    """Devuelve la oferta guardada (modelo `Oferta`) que es duplicado de `oferta`, o None."""
    for e in existentes:
        if e.clave_dedup == oferta["clave_dedup"] and _cerca(e.fecha_publicacion, oferta.get("fecha_publicacion"), dias):
            return e
    return None
