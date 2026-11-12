"""Línea de comandos del Observatorio.

Uso local (corrida completa en un computador, p. ej. si la IP del servidor está bloqueada):
    python -m observatorio.run --semestre 2026-II --corte inicio

Prueba pequeña (1 término por carrera, 1 ciudad, ~20 ofertas por consulta, sin mini corrida):
    python -m observatorio.run --semestre 2026-II --corte inicio --prueba

Pasos sueltos (los usa GitHub Actions):
    python -m observatorio.run preparar   --semestre 2026-II --corte inicio --run-id ID
    python -m observatorio.run extraer    --run-id ID --fuente linkedin --fragmento 0 --fragmentos 4
    python -m observatorio.run cursos     --run-id ID
    python -m observatorio.run consolidar --run-id ID
    python -m observatorio.run reporte    --run-id ID
    python -m observatorio.run exportar   --semestre 2026-II --corte inicio --salida observatorio.xlsx
    python -m observatorio.run migrar     (crea/actualiza tablas con Alembic) | semilla
    python -m observatorio.run purga-operativa | purga-reglas [--aplicar]  (purga por reglas operativas y valor formativo)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

ACCIONES = (
    "completa", "preparar", "extraer", "extraer-secuencial", "cursos", "consolidar", "reporte", "exportar",
    "migrar", "semilla", "purga-operativa", "purga-reglas",
)

# Comandos de mantenimiento / export que no requieren id de ejecución de corrida.
ACCIONES_SIN_RUN_ID = frozenset({"exportar", "purga-operativa", "purga-reglas"})


def configurar_logs() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
    for ruidoso in ("urllib3", "httpx", "JobSpy", "jobspy"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def migrar() -> None:
    """Aplica las migraciones de Alembic (o crea las tablas en SQLite)."""
    from observatorio.config import ajustes

    url = ajustes().database_url
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini = os.path.join(raiz, "alembic.ini")
    if os.path.exists(ini):
        from alembic import command
        from alembic.config import Config

        cfg = Config(ini)
        cfg.set_main_option("script_location", os.path.join(raiz, "alembic"))
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(cfg, "head")
    else:  # instalación sin carpeta alembic
        from observatorio.db.sesion import crear_tablas

        crear_tablas(url)


def imprimir_reporte(e) -> None:
    """Reporte de ejecución en lenguaje sencillo (RF-15)."""
    print("\n================ REPORTE DE EJECUCIÓN ================")
    print(f"Ejecución: {e.id_ejecucion}  ({e.semestre} · corte {e.corte})  estado: {e.estado}")
    print(f"Fuentes: {e.fuentes}")
    print(f"Ofertas encontradas: {e.ofertas_encontradas}  ·  guardadas (relevantes y nuevas): {e.ofertas_guardadas}")
    print(f"Duplicados eliminados: {e.duplicados_eliminados}  ·  no relevantes descartadas: {e.no_relevantes}")
    print(f"Total del corte: {e.total_corte} (meta {e.meta_ofertas})  ·  mini corrida: {'sí' if e.mini_corrida else 'no'}")
    print("Por fuente:", json.dumps(e.conteo_por_fuente or {}, ensure_ascii=False))
    print("Por carrera:", json.dumps(e.conteo_por_carrera or {}, ensure_ascii=False))
    if e.uso_llm:
        print("Clasificación con IA:", json.dumps(e.uso_llm, ensure_ascii=False))
    m, sg = divmod(e.duracion_segundos or 0, 60)
    print(f"Duración: {m // 60} h {m % 60} min {sg} s")
    if e.errores_detalle:
        print("Avisos y errores:")
        for x in e.errores_detalle:
            print("  -", x)
    print("======================================================\n")


def main(argv: list[str] | None = None) -> int:
    configurar_logs()
    p = argparse.ArgumentParser(prog="python -m observatorio.run", description="Observatorio de Empleo FCE")
    p.add_argument("accion", nargs="?", default="completa", choices=ACCIONES)
    p.add_argument("--semestre")
    p.add_argument("--corte", choices=["inicio", "mitad", "final", "Inicio", "Mitad", "Final"])
    p.add_argument("--run-id", dest="run_id")
    p.add_argument("--fuente", help="linkedin | indeed | google | computrabajo")
    p.add_argument("--fuentes", help="Lista separada por comas para limitar las fuentes")
    p.add_argument("--fragmento", type=int, default=0)
    p.add_argument("--fragmentos", type=int, default=1)
    p.add_argument("--max-minutos", type=float)
    p.add_argument("--modo", choices=["completa", "prueba"], default="completa")
    p.add_argument("--prueba", action="store_true", help="Corrida pequeña de prueba")
    p.add_argument("--terminos", type=int, help="Máximo de términos (prueba)")
    p.add_argument("--ubicaciones", type=int, help="Máximo de ciudades (prueba)")
    p.add_argument("--max", type=int, dest="max_por_particion", help="Máximo de ofertas por término y ciudad")
    p.add_argument("--sin-llm", action="store_true")
    p.add_argument("--sin-cursos", action="store_true")
    p.add_argument("--ejecutado-por")
    p.add_argument("--salida", default="observatorio.xlsx")
    p.add_argument("--github-output", help="Archivo donde escribir la matriz (GitHub Actions)")
    p.add_argument("--aplicar", action="store_true", help="Con purga-operativa/purga-reglas: aplica cambios (sin esto solo vista previa)")
    a = p.parse_args(argv)

    if a.accion == "migrar":
        migrar()
        print("Base de datos actualizada.")
        return 0

    from observatorio import orquestador as orq
    from observatorio.config import ajustes
    from observatorio.db.modelos import Ejecucion
    from observatorio.db.sesion import crear_tablas, fabrica_sesiones

    if ajustes().database_url.startswith("sqlite"):
        crear_tablas()  # modo local sin Postgres
        logging.info("Usando base local SQLite (%s). Configure DATABASE_URL para Postgres.", ajustes().database_url)

    if a.prueba:
        a.modo = "prueba"
        a.terminos = a.terminos or 3
        a.ubicaciones = a.ubicaciones or 1
        a.max_por_particion = a.max_por_particion or 20
    fuentes = [x.strip() for x in a.fuentes.split(",")] if a.fuentes else None

    with fabrica_sesiones()() as s:
        if a.accion == "semilla":
            from observatorio.db.semilla import sembrar_todo

            print(sembrar_todo(s))
            s.commit()
            return 0
        if a.accion in ("completa", "preparar") and not (a.semestre and a.corte):
            p.error("Indique --semestre (p. ej. 2026-II) y --corte (inicio, mitad o final)")
        if a.accion == "completa":
            e = orq.correr_completa(s, a.semestre, a.corte, a.run_id, a.ejecutado_por, a.modo, fuentes, a.terminos, a.ubicaciones,
                                    a.max_por_particion, usar_llm=not a.sin_llm, cursos=not a.sin_cursos, ejecutor="local")
            imprimir_reporte(e)
            return 0 if e.estado in ("completada", "incompleta") else 1
        if a.accion == "preparar":
            e = orq.preparar(s, a.semestre, a.corte, a.run_id, a.ejecutado_por, a.modo, fuentes, a.terminos, a.ubicaciones,
                             a.max_por_particion, ejecutor="github" if os.getenv("GITHUB_ACTIONS") else "local")
            s.commit()
            m = orq.matriz(s, e.id_ejecucion)
            print(json.dumps({"id_ejecucion": e.id_ejecucion, "matriz": m}, ensure_ascii=False))
            if a.github_output:
                with open(a.github_output, "a", encoding="utf-8") as f:
                    f.write(f"run_id={e.id_ejecucion}\n")
                    f.write(f"matriz={json.dumps({'include': m})}\n")
            return 0
        if not a.run_id and a.accion not in ACCIONES_SIN_RUN_ID:
            p.error("Indique --run-id")
        if a.accion == "extraer-secuencial":
            resumenes = orq.extraer_secuencial(s, a.run_id, a.max_minutos)
            print(json.dumps(resumenes, ensure_ascii=False))
            return 0
        if a.accion == "extraer":
            if not a.fuente:
                p.error("Indique --fuente")
            r = orq.extraer(s, a.run_id, a.fuente, a.fragmento, a.fragmentos, a.max_minutos)
            print(json.dumps(r, ensure_ascii=False))
            return 0
        if a.accion == "cursos":
            e = s.get(Ejecucion, a.run_id)
            lim = (e.parametros or {}).get("max_por_particion") if e else None
            print(json.dumps(orq.extraer_cursos_corrida(s, a.run_id, max_por_termino=lim), ensure_ascii=False))
            return 0
        if a.accion == "consolidar":
            e = orq.consolidar(s, a.run_id, usar_llm=not a.sin_llm)
            imprimir_reporte(e)
            return 0
        if a.accion == "reporte":
            e = s.get(Ejecucion, a.run_id)
            if e is None:
                p.error("No existe esa ejecución")
            imprimir_reporte(e)
            return 0
        if a.accion == "exportar":
            from observatorio.exportar import a_excel

            sem = orq.normalizar_semestre(a.semestre) if a.semestre else None
            cor = orq.normalizar_corte(a.corte) if a.corte else None
            with open(a.salida, "wb") as f:
                f.write(a_excel(s, sem, cor))
            print(f"Archivo guardado: {a.salida}")
            return 0
        if a.accion in ("purga-operativa", "purga-reglas"):
            from sqlalchemy import func, select

            from observatorio.db.modelos import TerminoBusqueda
            from observatorio.mantenimiento import (
                TERMINOS_BUSQUEDA_RETIRADOS,
                desactivar_terminos_retirados,
                purgar_por_reglas,
            )

            n_terms_activos = s.scalar(
                select(func.count())
                .select_from(TerminoBusqueda)
                .where(TerminoBusqueda.termino.in_(TERMINOS_BUSQUEDA_RETIRADOS), TerminoBusqueda.activo.is_(True))
            ) or 0
            res = purgar_por_reglas(s, aplicar=a.aplicar)
            n_desactivados = desactivar_terminos_retirados(s) if a.aplicar else 0
            print(
                json.dumps(
                    {
                        "modo": "aplicar" if a.aplicar else "vista_previa",
                        "accion": a.accion,
                        "terminos_retirados_activos": n_terms_activos,
                        "terminos_desactivados": n_desactivados,
                        **res,
                    },
                    ensure_ascii=False,
                )
            )
            if a.aplicar:
                s.commit()
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
