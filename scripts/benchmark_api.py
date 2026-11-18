#!/usr/bin/env python3
"""Mide latencias de consultas API (misma lógica que rutas) contra DATABASE_URL."""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from observatorio import analisis
from observatorio.config import ajustes, normalizar_url_bd
from observatorio.consultas import buscar_ofertas, valores_filtros


def _ms(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000


def main() -> None:
    url = normalizar_url_bd(os.getenv("DATABASE_URL", "") or ajustes().database_url)
    if not url or url.startswith("sqlite"):
        raise SystemExit("DATABASE_URL Postgres requerida")
    Session = sessionmaker(bind=create_engine(url))
    with Session() as s:
        cortes = analisis.cortes_disponibles(s)
        if not cortes:
            print(json.dumps({"error": "sin cortes"}))
            return
        ult = cortes[-1]
        sem, cor = ult["semestre"], ult["corte"]
        pen = cortes[-2] if len(cortes) > 1 else ult
        resultados = {
            "cortes_disponibles_ms": round(_ms(lambda: analisis.cortes_disponibles(s)), 1),
            "valores_filtros_ms": round(_ms(lambda: valores_filtros(s)), 1),
            "resumen_corte_ms": round(_ms(lambda: analisis.resumen_corte(s, sem, cor)), 1),
            "ranking_software_ms": round(
                _ms(lambda: (analisis.ranking(s, sem, cor, None), analisis.ranking_por_grupo(s, sem, cor, None))),
                1,
            ),
            "ranking_comparar_ms": round(
                _ms(lambda: analisis.comparar(s, pen["semestre"], pen["corte"], sem, cor, None)),
                1,
            ),
            "ofertas_listado_ms": round(_ms(lambda: buscar_ofertas(s, 1, 25, semestre=sem, corte=cor)), 1),
            "semestre": sem,
            "corte": cor,
        }
    print(json.dumps(resultados, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()