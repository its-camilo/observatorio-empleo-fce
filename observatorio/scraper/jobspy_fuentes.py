"""Indeed Colombia y Google Jobs mediante JobSpy (RF-03).

Se descartan correos y salarios: nunca se leen las columnas `emails`,
`min_amount`, `max_amount`, `interval`, `currency`.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, Iterator

from observatorio.config import ajustes
from observatorio.scraper.base import Consulta, OfertaCrudaDatos

log = logging.getLogger("observatorio.jobspy")


def _valor(r, col):
    v = r.get(col)
    if v is None:
        return ""
    try:
        import pandas as pd

        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return v


class _JobSpyBase:
    sitio = ""
    nombre = ""
    prefijo = ""

    def __init__(self, retraso=(2.0, 4.0), proxies: list[str] | None = None):
        self.retraso = retraso
        self.proxies = proxies if proxies is not None else ajustes().proxies

    def _kwargs(self, c: Consulta) -> dict:
        return {}

    def extraer(self, c: Consulta, ya_existe: Callable[[str], bool]) -> Iterator[OfertaCrudaDatos]:
        from jobspy import scrape_jobs

        time.sleep(random.uniform(*self.retraso))
        df = scrape_jobs(site_name=self.sitio, search_term=c.termino, results_wanted=c.max_resultados,
                         hours_old=24 * c.ventana_dias, proxies=self.proxies or None, verbose=0,
                         description_format="markdown", **self._kwargs(c))
        stats = c.opciones.setdefault("stats", {"omitidas": 0, "sin_detalle": 0})
        for _, r in df.iterrows():
            idf = str(_valor(r, "id")).split("-", 1)[-1]
            if not idf:
                continue
            if ya_existe(idf):
                stats["omitidas"] += 1
                continue
            remoto = _valor(r, "is_remote")
            yield OfertaCrudaDatos(
                fuente=self.nombre, id_fuente=idf, url=str(_valor(r, "job_url")),
                cargo=str(_valor(r, "title")), empresa=str(_valor(r, "company")), ubicacion=str(_valor(r, "location")),
                fecha_publicacion=str(_valor(r, "date_posted")), descripcion=str(_valor(r, "description")),
                sector=str(_valor(r, "company_industry")), nivel_fuente=str(_valor(r, "job_level")),
                tipo_empleo=str(_valor(r, "job_type")), remoto=bool(remoto) if remoto != "" else None,
            )


class Indeed(_JobSpyBase):
    sitio = "indeed"
    nombre = "Indeed"

    def _kwargs(self, c: Consulta) -> dict:
        return {"location": c.ubicacion, "country_indeed": "Colombia", "is_remote": bool(c.remoto)}


class GoogleJobs(_JobSpyBase):
    sitio = "google"
    nombre = "Google Jobs"

    def _kwargs(self, c: Consulta) -> dict:
        lugar = c.ubicacion or "Colombia"
        texto = f"{c.termino} empleos en {lugar} últimos {c.ventana_dias} días"
        if c.remoto:
            texto = f"{c.termino} empleos remotos Colombia"
        return {"google_search_term": texto, "location": lugar}
