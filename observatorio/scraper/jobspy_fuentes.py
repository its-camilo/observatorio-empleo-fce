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
_JOBSPY_GOOGLE = logging.getLogger("jobspy.google")


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


def _dataframe_vacio(df) -> bool:
    if df is None:
        return True
    try:
        return len(df) == 0
    except TypeError:
        return True


class _JobSpyBase:
    sitio = ""
    nombre = ""
    prefijo = ""

    def __init__(self, retraso=(2.0, 4.0), proxies: list[str] | None = None):
        self.retraso = retraso
        self.proxies = proxies if proxies is not None else ajustes().proxies

    def _kwargs(self, c: Consulta) -> dict:
        return {}

    def _scrape(self, c: Consulta, hours_old: int | None) -> "object":
        from jobspy import scrape_jobs

        return scrape_jobs(
            site_name=self.sitio,
            search_term=c.termino,
            results_wanted=c.max_resultados,
            hours_old=hours_old,
            proxies=self.proxies or None,
            verbose=0,
            description_format="markdown",
            **self._kwargs(c),
        )

    def extraer(self, c: Consulta, ya_existe: Callable[[str], bool]) -> Iterator[OfertaCrudaDatos]:
        time.sleep(random.uniform(*self.retraso))
        nivel_log = _JOBSPY_GOOGLE.level
        if self.sitio == "google":
            _JOBSPY_GOOGLE.setLevel(logging.CRITICAL)
        try:
            horas = 24 * c.ventana_dias
            df = self._scrape(c, horas)
            if _dataframe_vacio(df) and self.sitio == "google":
                df = self._scrape(c, None)
        finally:
            if self.sitio == "google":
                _JOBSPY_GOOGLE.setLevel(nivel_log)
        if _dataframe_vacio(df):
            c.opciones.setdefault("stats", {})["sin_resultados"] = True
            return
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
        """Deja que JobSpy arme la consulta (término + ubicación); no usar google_search_term en español."""
        lugar = (c.nombre_ubicacion or c.ubicacion or "Colombia").strip()
        if "|" in lugar:
            lugar = lugar.split("|", 1)[0]
        if c.remoto:
            return {"location": "Colombia", "is_remote": True}
        if "," not in lugar:
            lugar = f"{lugar}, Colombia"
        return {"location": lugar}
