"""Cursos en tendencia (RF-19): Coursera, edX y Platzi, en tabla aparte.

- Coursera: endpoint GraphQL público que usa su buscador (sin sesión).
- edX: índice público de búsqueda (Algolia) que usa edx.org. La llave de
  búsqueda es pública (está en la página); se puede fijar con las variables
  EDX_ALGOLIA_APP_ID / EDX_ALGOLIA_KEY o se descubre leyendo la página.
- Platzi: página pública de búsqueda (HTML).

La "tendencia" se mide con lo que entrega cada plataforma: posición en el
buscador, calificaciones y, en edX, inscripciones recientes.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Iterator
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from observatorio.scraper.http import ClienteHttp

log = logging.getLogger("observatorio.cursos")


def _num(texto: str) -> int | None:
    t = (texto or "").strip().lower().replace(",", ".")
    m = re.match(r"([\d.]+)\s*(k|m)?", t)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return int(v * (1000 if m.group(2) == "k" else 1_000_000 if m.group(2) == "m" else 1))


class Coursera:
    nombre = "Coursera"
    URL = "https://www.coursera.org/graphql-gateway?opname=Search"
    CONSULTA = ("query Search($requests: [Search_Request!]!) { SearchResult { search(requests: $requests) { elements { "
                "... on Search_ProductHit { name url partners productDifficultyLevel avgProductRating numProductRatings productType } } } } }")

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp("coursera", retraso=(1.5, 3.0))

    def buscar(self, termino: str, n: int = 15) -> Iterator[dict]:
        cuerpo = [{"operationName": "Search", "query": self.CONSULTA, "variables": {"requests": [
            {"entityType": "PRODUCTS", "limit": n, "facetFilters": [], "cursor": "0", "query": termino}]}}]
        r = self.http.post(self.URL, json=cuerpo, headers={"content-type": "application/json"})
        if r is None:
            return
        elementos = r.json()[0]["data"]["SearchResult"]["search"][0]["elements"]
        for i, e in enumerate(elementos, 1):
            yield {"plataforma": self.nombre, "termino": termino, "titulo": e.get("name", ""),
                   "url": urljoin("https://www.coursera.org", e.get("url", "")), "organizacion": ", ".join(e.get("partners") or []),
                   "nivel": (e.get("productDifficultyLevel") or "").capitalize(), "tipo": e.get("productType", ""),
                   "calificacion": round(float(e["avgProductRating"]), 2) if e.get("avgProductRating") else None,
                   "num_calificaciones": e.get("numProductRatings"), "inscritos_recientes": None, "posicion": i}


class Edx:
    nombre = "edX"

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp("edx", retraso=(1.5, 3.0))
        self.app_id = os.getenv("EDX_ALGOLIA_APP_ID", "")
        self.llave = os.getenv("EDX_ALGOLIA_KEY", "")

    def _descubrir_llave(self) -> None:
        """Lee la llave pública de búsqueda desde los scripts de edx.org."""
        r = self.http.get("https://www.edx.org/search?q=excel")
        if r is None:
            raise ValueError("no se pudo abrir edx.org")
        scripts = list(dict.fromkeys(re.findall(r'/_next/static/chunks/[^"\']+\.js', r.text)))
        for src in scripts[:80]:
            js = self.http.get("https://www.edx.org" + src, pausar=False)
            if js is None:
                continue
            m = re.search(r'"([A-Z0-9]{10})",\w+="([a-f0-9]{32})"', js.text)
            if m:
                self.app_id, self.llave = m.group(1), m.group(2)
                return
        raise ValueError("no se encontró la llave pública de búsqueda de edX")

    def buscar(self, termino: str, n: int = 15) -> Iterator[dict]:
        if not (self.app_id and self.llave):
            self._descubrir_llave()
        url = f"https://{self.app_id.lower()}-dsn.algolia.net/1/indexes/*/queries"
        cuerpo = {"requests": [{"indexName": "product", "params": f"query={quote(termino)}&hitsPerPage={n}"}]}
        r = self.http.post(url, json=cuerpo, headers={"x-algolia-application-id": self.app_id, "x-algolia-api-key": self.llave,
                                                      "content-type": "application/json"})
        if r is None:
            return
        for i, h in enumerate(r.json()["results"][0]["hits"], 1):
            yield {"plataforma": self.nombre, "termino": termino, "titulo": h.get("title", ""),
                   "url": h.get("marketing_url") or "", "organizacion": ", ".join(h.get("partner") or []),
                   "nivel": ", ".join(h.get("level") or []), "tipo": h.get("product", ""), "calificacion": None,
                   "num_calificaciones": None, "inscritos_recientes": int(h["recent_enrollment_count"]) if h.get("recent_enrollment_count") else None,
                   "posicion": i}


class Platzi:
    nombre = "Platzi"

    def __init__(self, http: ClienteHttp | None = None):
        self.http = http or ClienteHttp("platzi", retraso=(1.5, 3.0))

    def buscar(self, termino: str, n: int = 15) -> Iterator[dict]:
        r = self.http.get(f"https://platzi.com/buscar/?search={quote(termino)}")
        if r is None:
            return
        s = BeautifulSoup(r.text, "lxml")
        vistos = set()
        i = 0
        for a in s.select('a[href^="/cursos/"]'):
            href = a.get("href", "")
            if not re.fullmatch(r"/cursos/[a-z0-9\-]+/", href) or href in vistos:
                continue
            h = a.find(["h2", "h3"])
            if h is None:
                continue
            vistos.add(href)
            i += 1
            estrellas = a.select_one('[class*="Rank__Stars"]')
            votos = a.select_one('[class*="Rank__Ratings"]')
            yield {"plataforma": self.nombre, "termino": termino, "titulo": h.get_text(" ", strip=True)[:300],
                   "url": "https://platzi.com" + href, "organizacion": "Platzi", "nivel": None, "tipo": "Curso",
                   "calificacion": float(estrellas.get_text(strip=True)) if estrellas else None,
                   "num_calificaciones": _num(votos.get_text("", strip=True).strip("() ")) if votos else None,
                   "inscritos_recientes": None, "posicion": i}
            if i >= n:
                break


PLATAFORMAS = {"coursera": Coursera, "edx": Edx, "platzi": Platzi}


def extraer_cursos(plataformas: list[str], terminos: list[str], max_por_termino: int = 15) -> tuple[list[dict], list[str]]:
    """Devuelve (cursos, errores en lenguaje sencillo). Cada plataforma es independiente."""
    from observatorio.scraper.http import explicar_error

    cursos: list[dict] = []
    errores: list[str] = []
    for nombre in plataformas:
        clase = PLATAFORMAS.get(nombre.lower())
        if clase is None:
            continue
        fuente = clase()
        for t in terminos:
            try:
                cursos.extend(list(fuente.buscar(t, max_por_termino)))
            except Exception as e:  # noqa: BLE001 - una plataforma no tumba a las demás
                errores.append(explicar_error(nombre, e) + f" (término '{t}')")
                log.warning("Cursos %s '%s': %s", nombre, t, e)
                if len([x for x in errores if x.startswith(clase.nombre) or nombre in x.lower()]) >= 3:
                    break
    return cursos, errores


if __name__ == "__main__":  # prueba rápida manual
    c, e = extraer_cursos(["coursera", "edx", "platzi"], ["excel"], 3)
    print(json.dumps(c, ensure_ascii=False, indent=1)[:3000], e)
