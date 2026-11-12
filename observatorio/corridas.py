"""Lanzar corridas en GitHub Actions y consultar su progreso (lo usan la API y el MCP)."""
from __future__ import annotations

import uuid
from datetime import timedelta

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.config import ajustes
from observatorio.db.modelos import Ejecucion, OfertaCruda, Particion, ahora
from observatorio.normas_corrida import NOMBRES_FUENTE, normalizar_corte, normalizar_semestre

API = "https://api.github.com"


class ErrorCorrida(Exception):
    """Error con mensaje en lenguaje sencillo para el usuario."""


def _cabeceras() -> dict:
    a = ajustes()
    if not a.github_token or not a.github_repo:
        raise ErrorCorrida("Falta configurar GITHUB_TOKEN y GITHUB_REPO en el servidor para lanzar corridas en GitHub Actions. "
                           "Mientras tanto se puede correr desde un computador con: python -m observatorio.run --semestre ... --corte ...")
    return {"Authorization": f"Bearer {a.github_token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def lanzar(s: Session, semestre: str, corte: str, solicitado_por: str, modo: str = "completa") -> Ejecucion:
    """Registra la ejecución (en cola) y dispara el workflow con workflow_dispatch."""
    semestre, corte = normalizar_semestre(semestre), normalizar_corte(corte)
    if modo not in ("completa", "prueba"):
        raise ErrorCorrida("El modo debe ser 'completa' o 'prueba'.")
    activa = s.scalars(select(Ejecucion).where(Ejecucion.estado.in_(["en_cola", "en_curso"]),
                                              Ejecucion.creado_en > ahora() - timedelta(hours=8))).first()
    if activa is not None:
        raise ErrorCorrida(f"Ya hay una corrida en marcha ({activa.id_ejecucion}). Espere a que termine antes de lanzar otra.")
    cab = _cabeceras()
    a = ajustes()
    id_ej = f"{semestre}-{corte.lower()}-{uuid.uuid4().hex[:6]}"
    ejec = Ejecucion(id_ejecucion=id_ej, semestre=semestre, corte=corte, ejecutado_por=solicitado_por, estado="en_cola",
                     modo=modo, ejecutor="github", fase="en_cola")
    s.add(ejec)
    s.flush()
    try:
        r = requests.post(f"{API}/repos/{a.github_repo}/actions/workflows/{a.github_workflow}/dispatches", headers=cab, timeout=20,
                          json={"ref": a.github_ref, "inputs": {"semestre": semestre, "corte": corte.lower(), "run_id": id_ej,
                                                                "modo": modo, "ejecutado_por": solicitado_por}})
    except requests.RequestException as e:
        ejec.estado, ejec.errores = "fallida", f"No hubo conexión con GitHub: {e}"
        s.commit()
        raise ErrorCorrida(ejec.errores) from e
    if r.status_code not in (200, 204):
        ejec.estado = "fallida"
        ejec.errores = f"GitHub rechazó el lanzamiento (HTTP {r.status_code}): {r.text[:300]}. Revise GITHUB_TOKEN (permiso Actions: write) y GITHUB_WORKFLOW."
        s.commit()
        raise ErrorCorrida(ejec.errores)
    s.commit()
    return ejec


def estado_github(id_ejecucion: str) -> dict | None:
    """Busca la ejecución de Actions cuyo título incluye el id (run-name del workflow)."""
    a = ajustes()
    if not a.github_token or not a.github_repo:
        return None
    try:
        r = requests.get(f"{API}/repos/{a.github_repo}/actions/workflows/{a.github_workflow}/runs", headers=_cabeceras(),
                         params={"per_page": 30, "event": "workflow_dispatch"}, timeout=15)
        if r.status_code != 200:
            return None
        for run in r.json().get("workflow_runs", []):
            if id_ejecucion in (run.get("display_title") or run.get("name") or ""):
                return {"estado": run.get("status"), "conclusion": run.get("conclusion"), "url": run.get("html_url"),
                        "iniciado": run.get("run_started_at")}
    except requests.RequestException:
        return None
    return None


def progreso(s: Session, ejec: Ejecucion, consultar_github: bool = False) -> dict:
    """Progreso a partir de las particiones (igual para GitHub Actions y para la CLI local)."""
    filas = s.execute(select(Particion.fuente, Particion.estado, func.count(), func.sum(Particion.ofertas))
                      .where(Particion.id_ejecucion == ejec.id_ejecucion).group_by(Particion.fuente, Particion.estado)).all()
    por_fuente: dict[str, dict] = {}
    tot = {"total": 0, "hechas": 0, "error": 0, "pendientes": 0}
    for fuente, estado, n, ofertas in filas:
        d = por_fuente.setdefault(NOMBRES_FUENTE.get(fuente, fuente), {"total": 0, "hechas": 0, "error": 0, "pendientes": 0, "ofertas": 0})
        d["total"] += n
        d["ofertas"] += int(ofertas or 0)
        clave = {"hecha": "hechas", "error": "error"}.get(estado, "pendientes")
        d[clave] += n
        tot["total"] += n
        tot[clave] += n
    crudas = s.scalar(select(func.count()).select_from(OfertaCruda).where(OfertaCruda.id_ejecucion == ejec.id_ejecucion)) or 0
    procesadas = s.scalar(select(func.count()).select_from(OfertaCruda).where(
        OfertaCruda.id_ejecucion == ejec.id_ejecucion, OfertaCruda.procesada.is_(True))) or 0
    if ejec.estado in ("completada", "incompleta", "fallida"):
        pct = 100
    elif tot["total"]:
        pct = int(85 * (tot["hechas"] + tot["error"]) / tot["total"] + (10 * procesadas / crudas if crudas else 0))
    else:
        pct = 0
    salida = {"id_ejecucion": ejec.id_ejecucion, "estado": ejec.estado, "fase": ejec.fase, "porcentaje": min(pct, 100),
              "consultas": tot, "por_fuente": por_fuente, "ofertas_crudas": crudas, "procesadas": procesadas,
              "github_run_url": ejec.github_run_url}
    if consultar_github and ejec.ejecutor == "github" and ejec.estado in ("en_cola", "en_curso"):
        gh = estado_github(ejec.id_ejecucion)
        if gh:
            salida["github"] = gh
            salida["github_run_url"] = salida["github_run_url"] or gh.get("url")
            if gh.get("estado") == "completed" and gh.get("conclusion") not in ("success", None) and ejec.estado == "en_cola":
                salida["aviso"] = "El workflow de GitHub terminó con error antes de empezar. Revise el enlace de GitHub Actions."
    return salida


def ejecucion_dict(e: Ejecucion) -> dict:
    campos = ["id_ejecucion", "fecha", "semestre", "corte", "ejecutado_por", "fuentes", "ofertas_encontradas", "duplicados_eliminados",
              "errores", "estado", "modo", "ejecutor", "ofertas_relevantes", "ofertas_guardadas", "no_relevantes", "total_corte",
              "meta_ofertas", "mini_corrida", "conteo_por_fuente", "conteo_por_carrera", "errores_detalle", "terminos_usados",
              "uso_llm", "duracion_segundos", "inicio", "fin", "fase", "github_run_url", "creado_en"]
    d = {c: getattr(e, c) for c in campos}
    for c in ("fecha", "inicio", "fin", "creado_en"):
        d[c] = d[c].isoformat() if d[c] else None
    params = e.parametros or {}
    d["presupuesto_fuentes"] = params.get("presupuesto_fuentes")
    d["presupuesto_carreras"] = params.get("presupuesto_carreras")
    d["logro_extraccion"] = params.get("logro_extraccion")
    return d
