"""LinkedIn (RF-02): solo información pública, sin iniciar sesión.

1. Búsqueda: JobSpy (sitio "linkedin"), que usa el endpoint público de
   invitados. Si JobSpy falla, se usa nuestro propio lector del mismo
   endpoint (`jobs-guest/jobs/api/seeMoreJobPostings/search`).
2. Detalle: para cada oferta nueva se pide la página pública
   `jobs-guest/jobs/api/jobPosting/<id>` con pausas y reintentos
   (descripción, nivel, tipo de empleo y sector).

Nunca se usan cuentas personales ni institucionales. Ver la sección de
riesgos (términos de uso) en docs/documentacion-tecnica.md.
"""
from __future__ import annotations

import html as html_mod
import logging
import re
from typing import Callable, Iterator
from urllib.parse import quote

from bs4 import BeautifulSoup

from observatorio.scraper.base import Consulta, OfertaCrudaDatos
from observatorio.scraper.http import ClienteHttp, FuenteBloqueada

log = logging.getLogger("observatorio.linkedin")

URL_BUSQUEDA = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
URL_DETALLE = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"

_CRITERIOS = {
    "seniority level": "nivel", "nivel de antigüedad": "nivel", "nivel de antiguedad": "nivel",
    "employment type": "tipo", "tipo de empleo": "tipo",
    "industries": "sector", "sectores": "sector",
    "job function": "funcion", "función laboral": "funcion", "funcion laboral": "funcion",
}


def parsear_detalle(pagina: str) -> dict:
    """Extrae descripción y criterios de la página pública de una oferta."""
    s = BeautifulSoup(pagina, "lxml")
    datos: dict = {"descripcion": "", "nivel": "", "tipo": "", "sector": "", "funcion": ""}
    caja = s.select_one("div.show-more-less-html__markup") or s.select_one("div.description__text")
    if caja:
        for br in caja.find_all(["br"]):
            br.replace_with("\n")
        for li in caja.find_all("li"):
            li.insert_before("\n• ")
        for p in caja.find_all(["p", "div", "ul", "ol", "h1", "h2", "h3", "strong"]):
            p.insert_after("\n")
        datos["descripcion"] = re.sub(r"\n\s*\n+", "\n\n", caja.get_text("")).strip()
    for li in s.select("li.description__job-criteria-item"):
        h = li.select_one("h3")
        v = li.select_one("span")
        if not h or not v:
            continue
        clave = _CRITERIOS.get(h.get_text(strip=True).lower())
        if clave:
            datos[clave] = v.get_text(" ", strip=True)
    for sel, clave in ((".topcard__title", "cargo"), (".topcard__org-name-link", "empresa"),
                       (".topcard__flavor--bullet", "ubicacion"), (".posted-time-ago__text", "publicado")):
        e = s.select_one(sel)
        if e:
            datos[clave] = e.get_text(" ", strip=True)
    return datos


def parsear_tarjetas(pagina: str) -> list[dict]:
    """Tarjetas del endpoint de búsqueda (respaldo cuando JobSpy falla)."""
    s = BeautifulSoup(pagina, "lxml")
    tarjetas = []
    for card in s.select("li"):
        div = card.select_one("[data-entity-urn]")
        if not div:
            continue
        m = re.search(r"jobPosting:(\d+)", div.get("data-entity-urn", ""))
        if not m:
            continue
        def txt(sel):
            e = card.select_one(sel)
            return html_mod.unescape(e.get_text(" ", strip=True)) if e else ""
        t = card.select_one("time")
        tarjetas.append({
            "id": m.group(1), "cargo": txt(".base-search-card__title"), "empresa": txt(".base-search-card__subtitle"),
            "ubicacion": txt(".job-search-card__location"), "fecha": t.get("datetime", "") if t else "",
        })
    return tarjetas


class LinkedIn:
    nombre = "LinkedIn"

    def __init__(self, retraso=(2.5, 5.0), proxies: list[str] | None = None):
        self.http = ClienteHttp("linkedin", retraso=retraso, proxies=proxies, espera_base=30.0)

    # -------------------------------------------------------------- búsqueda
    def _buscar_jobspy(self, c: Consulta) -> list[dict]:
        from jobspy import scrape_jobs  # import tardío: dependencia pesada

        df = scrape_jobs(
            site_name="linkedin", search_term=c.termino, location=c.ubicacion, results_wanted=c.max_resultados,
            hours_old=24 * c.ventana_dias, is_remote=bool(c.remoto), linkedin_fetch_description=False,
            proxies=self.http.proxies or None, verbose=0, description_format="markdown",
        )
        filas = []
        for _, r in df.iterrows():
            jid = str(r.get("id") or "").replace("li-", "")
            if not jid:
                continue
            filas.append({"id": jid, "cargo": str(r.get("title") or ""), "empresa": str(r.get("company") or ""),
                          "ubicacion": str(r.get("location") or ""), "fecha": r.get("date_posted"),
                          "remoto": bool(r.get("is_remote")) if r.get("is_remote") is not None else None})
        return filas

    def _buscar_propio(self, c: Consulta) -> list[dict]:
        filas: dict[str, dict] = {}
        segundos = 86400 * c.ventana_dias
        for inicio in range(0, c.max_resultados, 10):
            url = (f"{URL_BUSQUEDA}?keywords={quote(c.termino)}&location={quote(c.ubicacion)}"
                   f"&f_TPR=r{segundos}&start={inicio}" + ("&f_WT=2" if c.remoto else ""))
            r = self.http.get(url)
            if r is None or not r.text.strip():
                break
            tarjetas = parsear_tarjetas(r.text)
            if not tarjetas:
                break
            for t in tarjetas:
                filas.setdefault(t["id"], t)
        return list(filas.values())

    def buscar(self, c: Consulta) -> list[dict]:
        try:
            filas = self._buscar_jobspy(c)
            if filas:
                return filas
            log.info("[LinkedIn] JobSpy no trajo resultados para '%s' en %s; se usa el lector propio", c.termino, c.ubicacion)
        except Exception as e:  # JobSpy falla o LinkedIn lo bloquea
            log.info("[LinkedIn] JobSpy falló (%s); se usa el lector propio", type(e).__name__)
        return self._buscar_propio(c)

    # -------------------------------------------------------------- detalle
    def detalle(self, id_li: str) -> dict | None:
        r = self.http.get(URL_DETALLE.format(id=id_li))
        if r is None:
            return None
        return parsear_detalle(r.text)

    def extraer(self, c: Consulta, ya_existe: Callable[[str], bool]) -> Iterator[OfertaCrudaDatos]:
        stats = c.opciones.setdefault("stats", {"omitidas": 0, "sin_detalle": 0})
        for f in self.buscar(c):
            if ya_existe(f["id"]):
                stats["omitidas"] += 1
                continue
            try:
                d = self.detalle(f["id"]) or {}
            except FuenteBloqueada:
                raise
            if not d.get("descripcion"):
                stats["sin_detalle"] += 1
            yield OfertaCrudaDatos(
                fuente=self.nombre, id_fuente=f["id"], url=f"https://www.linkedin.com/jobs/view/{f['id']}/",
                cargo=f.get("cargo") or d.get("cargo", ""), empresa=f.get("empresa") or d.get("empresa", ""),
                ubicacion=f.get("ubicacion") or d.get("ubicacion", ""),
                fecha_publicacion=str(f.get("fecha") or d.get("publicado") or ""),
                descripcion=d.get("descripcion", ""), sector=d.get("sector", ""), nivel_fuente=d.get("nivel", ""),
                tipo_empleo=d.get("tipo", ""), remoto=f.get("remoto") if f.get("remoto") else (True if c.remoto else None),
            )
