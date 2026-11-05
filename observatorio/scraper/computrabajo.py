"""Computrabajo Colombia (co.computrabajo.com), listados públicos (RF-03).

Listado: https://co.computrabajo.com/trabajo-de-<termino>[-en-<lugar>]?p=<n>
Detalle: enlace de cada tarjeta (/ofertas-de-trabajo/oferta-de-trabajo-de-...-<ID>)

Pausas entre consultas y sin iniciar sesión. Se elimina la línea
"Palabras clave:" que Computrabajo añade (no la escribió la empresa) y el
salario.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from observatorio.scraper.base import Consulta, OfertaCrudaDatos
from observatorio.scraper.http import ClienteHttp
from observatorio.texto import sin_tildes

log = logging.getLogger("observatorio.computrabajo")

BASE = "https://co.computrabajo.com"


def slug(texto: str) -> str:
    t = sin_tildes(texto).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-")


def url_listado(termino: str, lugar: str = "", pagina: int = 1) -> str:
    url = f"{BASE}/trabajo-de-{slug(termino)}"
    if lugar:
        url += f"-en-{lugar}"
    if pagina > 1:
        url += f"?p={pagina}"
    return url


def parsear_listado(pagina: str) -> list[dict]:
    s = BeautifulSoup(pagina, "lxml")
    salida = []
    for art in s.select("article.box_offer"):
        a = art.select_one("h2 a.js-o-link") or art.select_one("h2 a")
        if not a:
            continue
        oid = art.get("data-id") or art.get("id") or ""
        empresa = ubicacion = fecha = ""
        for p in art.select("p"):
            txt = p.get_text(" ", strip=True)
            clases = " ".join(p.get("class") or [])
            if re.match(r"^(hace|ayer|hoy)\b", txt.lower()) or "fc_aux" in clases:
                fecha = fecha or txt
            elif "dFlex" in clases and not empresa:
                # párrafo de empresa: enlace con el nombre, a veces precedido de la calificación (4,5 ★)
                enlace = p.select_one("a")
                empresa = enlace.get_text(" ", strip=True) if enlace else re.sub(r"^\d+[.,]\d\s*", "", txt)
            elif p.select_one("span.mr10") and not ubicacion:
                ubicacion = p.select_one("span.mr10").get_text(" ", strip=True)
        salida.append({"id": oid, "cargo": a.get_text(" ", strip=True), "url": urljoin(BASE, a.get("href", "").split("#")[0]),
                       "empresa": empresa, "ubicacion": ubicacion, "fecha": fecha})
    return salida


def parsear_detalle(pagina: str) -> dict:
    s = BeautifulSoup(pagina, "lxml")
    caja = s.select_one('div[div-link="oferta"]') or s.select_one("div.box_detail")
    descripcion = ""
    if caja:
        partes = [p.get_text("\n", strip=True) for p in caja.select("p.mbB")]
        descripcion = "\n".join(partes) if partes else caja.get_text("\n", strip=True)
    # Quitar "Palabras clave" (añadidas por el portal) y salarios
    descripcion = re.sub(r"(?im)^\s*palabras clave:.*$", "", descripcion)
    descripcion = re.sub(r"(?i)\$\s?[\d.,]+(?:\s*\(?\w+\)?)?", "", descripcion)
    descripcion = re.sub(r"(?im)^\s*salario.*$", "", descripcion).strip()
    requisitos = " ".join(li.get_text(" ", strip=True) for li in s.select("ul.disc li"))
    fecha = ""
    for p in s.select("p.fc_aux, span.fc_aux"):
        t = p.get_text(" ", strip=True)
        if re.match(r"^(hace|ayer|hoy|publicado)", t.lower()):
            fecha = t
            break
    tipo = ""
    for tag in s.select("span.tag"):
        t = tag.get_text(" ", strip=True)
        if re.search(r"remoto|presencial|h[ií]brido", t, re.I):
            tipo = t
    return {"descripcion": (descripcion + ("\n" + requisitos if requisitos else "")).strip(), "fecha": fecha, "modalidad": tipo}


class Computrabajo:
    nombre = "Computrabajo"

    def __init__(self, retraso=(2.0, 4.0), proxies: list[str] | None = None, max_paginas: int = 3):
        self.http = ClienteHttp("computrabajo", retraso=retraso, proxies=proxies, espera_base=20.0)
        self.max_paginas = max_paginas

    def extraer(self, c: Consulta, ya_existe: Callable[[str], bool]) -> Iterator[OfertaCrudaDatos]:
        stats = c.opciones.setdefault("stats", {"omitidas": 0, "sin_detalle": 0})
        vistos: set[str] = set()
        entregadas = 0
        lugar = c.ubicacion
        for pag in range(1, self.max_paginas + 1):
            r = self.http.get(url_listado(c.termino, lugar, pag))
            if r is None:
                break
            tarjetas = parsear_listado(r.text)
            if not tarjetas and pag == 1 and lugar:
                # Computrabajo a veces recorta el slug con ciudad ("administrador-de-empres-en-..."):
                # se intenta la búsqueda nacional y la ciudad se normaliza después.
                lugar = ""
                r = self.http.get(url_listado(c.termino, lugar, pag))
                tarjetas = parsear_listado(r.text) if r is not None else []
            nuevas = [t for t in tarjetas if t["id"] and t["id"] not in vistos]
            if not nuevas:
                break
            for t in nuevas:
                vistos.add(t["id"])
                if entregadas >= c.max_resultados:
                    return
                if ya_existe(t["id"]):
                    stats["omitidas"] += 1
                    continue
                det = {}
                rd = self.http.get(t["url"])
                if rd is not None:
                    det = parsear_detalle(rd.text)
                if not det.get("descripcion"):
                    stats["sin_detalle"] += 1
                entregadas += 1
                yield OfertaCrudaDatos(
                    fuente=self.nombre, id_fuente=t["id"], url=t["url"], cargo=t["cargo"], empresa=t["empresa"],
                    ubicacion=t["ubicacion"], fecha_publicacion=t["fecha"] or det.get("fecha", ""),
                    descripcion=det.get("descripcion", ""), tipo_empleo=det.get("modalidad", ""),
                    remoto=True if re.search(r"remoto", det.get("modalidad", ""), re.I) else None,
                )
