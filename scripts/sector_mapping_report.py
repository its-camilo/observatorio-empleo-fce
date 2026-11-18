#!/usr/bin/env python3
"""Estadísticas de mapeo sector (producción o DATABASE_URL). Solo lectura en SQL."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import create_engine, text

from observatorio.config import ajustes, normalizar_url_bd
from observatorio.pipeline.sectores_taxonomia import SECTORES_CANONICOS, resumen_mapeo, sector_canonico


def cargar_distinct_desde_db() -> list[str]:
    url = normalizar_url_bd(os.getenv("DATABASE_URL", "") or ajustes().database_url)
    if not url or url.startswith("sqlite"):
        raise RuntimeError("Se requiere Postgres (DATABASE_URL)")
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT sector FROM ofertas WHERE sector IS NOT NULL AND TRIM(sector) != '' GROUP BY sector"
            )
        ).scalars()
        return [str(r) for r in rows]


def main() -> None:
    valores = cargar_distinct_desde_db()
    antes = len(valores)
    canonicos = {sector_canonico(v) for v in valores}
    despues = len(canonicos)
    mapeo = resumen_mapeo(valores)
    cnt = {k: len(vs) for k, vs in mapeo["por_canonico"].items()}
    print(
        json.dumps(
            {
                "sectores_raw_distintos": antes,
                "sectores_canonicos_distintos": despues,
                "etiquetas_canonicas_definidas": len(SECTORES_CANONICOS),
                "conteo_raw_por_canonico": cnt,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()