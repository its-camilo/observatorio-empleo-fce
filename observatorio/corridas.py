"""Lanzar corridas en GitHub Actions y consultar su progreso (lo usan la API y el MCP)."""
from __future__ import annotations

import uuid
from datetime import timedelta

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.config import ajustes
from observatorio.corridas_cierre import (
    cerrar_corridas_colgadas,
    cerrar_ejecucion_error,
    estado_github,
    reconciliar_corridas_activas,
    reconciliar_ejecucion,
)
from observatorio.db.modelos import Ejecucion, OfertaCruda, Particion, ahora
from observatorio.normas_corrida import NOMBRES_FUENTE, normalizar_corte, normalizar_semestre

API = "https://api.github.com"

__all__ = [
    "ErrorCorrida",
    "acciones_corrida",
    "cerrar_corridas_colgadas",
    "cerrar_ejecucion_error",
    "contar_consultas_pendientes",
    "ejecucion_dict",
    "estado_github",
    "lanzar",
    "progreso",
    "reanudar_corrida",
    "reconciliar_corridas_activas",
    "reconciliar_ejecucion",
    "reintentar_consolidacion_corrida",
]


class ErrorCorrida(Exception):
    """Error con mensaje en lenguaje sencillo para el usuario."""


def _cabeceras() -> dict:
    a = ajustes()
    if not a.github_token or not a.github_repo:
        raise ErrorCorrida("Falta configurar GITHUB_TOKEN y GITHUB_REPO en el servidor para lanzar corridas en GitHub Actions. "
                           "Mientras tanto se puede correr desde un computador con: python -m observatorio.run --semestre ... --corte ...")
    return {"Authorization": f"Bearer {a.github_token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _corrida_activa(s: Session, excluir_id: str | None = None) -> Ejecucion | None:
    q = select(Ejecucion).where(
        Ejecucion.estado.in_(["en_cola", "en_curso"]),
        Ejecucion.creado_en > ahora() - timedelta(hours=8),
    )
    if excluir_id:
        q = q.where(Ejecucion.id_ejecucion != excluir_id)
    return s.scalars(q).first()


def contar_consultas_pendientes(s: Session, id_ejecucion: str) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(Particion)
            .where(Particion.id_ejecucion == id_ejecucion, Particion.estado == "pendiente")
        )
        or 0
    )


def _contar_crudas(s: Session, id_ejecucion: str) -> int:
    return int(
        s.scalar(select(func.count()).select_from(OfertaCruda).where(OfertaCruda.id_ejecucion == id_ejecucion))
        or 0
    )


def _disparar_workflow_github(inputs: dict) -> None:
    a = ajustes()
    cab = _cabeceras()
    try:
        r = requests.post(
            f"{API}/repos/{a.github_repo}/actions/workflows/{a.github_workflow}/dispatches",
            headers=cab,
            timeout=20,
            json={"ref": a.github_ref, "inputs": inputs},
        )
    except requests.RequestException as e:
        raise ErrorCorrida(f"No hubo conexión con GitHub: {e}") from e
    if r.status_code not in (200, 204):
        raise ErrorCorrida(
            f"GitHub rechazó el lanzamiento (HTTP {r.status_code}): {r.text[:300]}. "
            "Revise GITHUB_TOKEN (permiso Actions: write) y GITHUB_WORKFLOW."
        )


def _marcar_corrida_en_cola(ejec: Ejecucion, solicitado_por: str) -> None:
    ejec.estado = "en_cola"
    ejec.fase = "en_cola"
    ejec.ejecutado_por = solicitado_por


def _validar_relanzable(s: Session, ejec: Ejecucion) -> None:
    if ejec.estado in ("en_cola", "en_curso"):
        raise ErrorCorrida(
            f"La corrida {ejec.id_ejecucion} ya está en marcha (estado: {ejec.estado}). "
            "Espere a que termine antes de intentar de nuevo."
        )
    activa = _corrida_activa(s)
    if activa is not None:
        raise ErrorCorrida(
            f"Ya hay una corrida en marcha ({activa.id_ejecucion}). "
            "Espere a que termine antes de relanzar esta ejecución."
        )


def acciones_corrida(s: Session, ejec: Ejecucion) -> dict:
    """Indicadores para la UI: reanudar extracción vs reintentar solo consolidación."""
    pend = contar_consultas_pendientes(s, ejec.id_ejecucion)
    en_marcha = ejec.estado in ("en_cola", "en_curso")
    otra = _corrida_activa(s, excluir_id=ejec.id_ejecucion) if not en_marcha else None
    bloqueado = otra is not None
    crudas = _contar_crudas(s, ejec.id_ejecucion)
    puede_reintentar = (
        not en_marcha
        and not bloqueado
        and pend == 0
        and crudas > 0
        and ejec.estado in ("fallida", "incompleta")
    )
    puede_reanudar = (
        not en_marcha
        and not bloqueado
        and (
            pend > 0
            or (ejec.estado in ("incompleta", "fallida") and not puede_reintentar)
        )
    )
    return {
        "consultas_pendientes": pend,
        "en_marcha": en_marcha,
        "bloqueado_por_otra": bloqueado,
        "id_corrida_activa": otra.id_ejecucion if otra else None,
        "puede_reanudar": puede_reanudar,
        "puede_reintentar_consolidacion": puede_reintentar,
    }


def reanudar_corrida(s: Session, id_ejecucion: str, solicitado_por: str) -> Ejecucion:
    """Relanza corrida.yml con el mismo run_id (fase completa: retoma particiones pendientes)."""
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ErrorCorrida(f"No existe la ejecución {id_ejecucion}.")
    acc = acciones_corrida(s, ejec)
    if not acc["puede_reanudar"]:
        if acc["en_marcha"]:
            raise ErrorCorrida(f"La corrida {id_ejecucion} ya está en marcha.")
        if acc["bloqueado_por_otra"]:
            raise ErrorCorrida(f"Ya hay una corrida en marcha ({acc['id_corrida_activa']}).")
        raise ErrorCorrida(
            "Esta corrida no se puede reanudar: no hay consultas pendientes "
            "y el estado actual no lo permite."
        )
    _validar_relanzable(s, ejec)
    reconciliar_corridas_activas(s, consultar_github=True)
    s.commit()
    _marcar_corrida_en_cola(ejec, solicitado_por)
    s.flush()
    inputs = {
        "semestre": ejec.semestre,
        "corte": (ejec.corte or "").lower(),
        "run_id": id_ejecucion,
        "modo": ejec.modo or "completa",
        "ejecutado_por": solicitado_por,
        "fase": "completa",
    }
    try:
        _disparar_workflow_github(inputs)
    except ErrorCorrida:
        ejec.estado, ejec.errores = "fallida", "No se pudo reanudar en GitHub Actions."
        s.commit()
        raise
    s.commit()
    return ejec


def reintentar_consolidacion_corrida(s: Session, id_ejecucion: str, solicitado_por: str) -> Ejecucion:
    """Relanza corrida.yml con fase solo_consolidar (mismo run_id, presupuestos congelados)."""
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ErrorCorrida(f"No existe la ejecución {id_ejecucion}.")
    acc = acciones_corrida(s, ejec)
    if not acc["puede_reintentar_consolidacion"]:
        if acc["en_marcha"]:
            raise ErrorCorrida(f"La corrida {id_ejecucion} ya está en marcha.")
        if acc["bloqueado_por_otra"]:
            raise ErrorCorrida(f"Ya hay una corrida en marcha ({acc['id_corrida_activa']}).")
        if acc["consultas_pendientes"] > 0:
            raise ErrorCorrida(
                f"Aún hay {acc['consultas_pendientes']} consultas pendientes; "
                "use «Reanudar corrida» para continuar la extracción."
            )
        raise ErrorCorrida(
            "No se puede reintentar la consolidación: la extracción no terminó o el estado no lo permite."
        )
    _validar_relanzable(s, ejec)
    reconciliar_corridas_activas(s, consultar_github=True)
    s.commit()
    _marcar_corrida_en_cola(ejec, solicitado_por)
    s.flush()
    inputs = {
        "semestre": ejec.semestre,
        "corte": (ejec.corte or "").lower(),
        "run_id": id_ejecucion,
        "modo": ejec.modo or "completa",
        "ejecutado_por": solicitado_por,
        "fase": "solo_consolidar",
    }
    try:
        _disparar_workflow_github(inputs)
    except ErrorCorrida:
        ejec.estado, ejec.errores = "fallida", "No se pudo reintentar la consolidación en GitHub Actions."
        s.commit()
        raise
    s.commit()
    return ejec


def lanzar(s: Session, semestre: str, corte: str, solicitado_por: str, modo: str = "completa") -> Ejecucion:
    """Registra la ejecución (en cola) y dispara el workflow con workflow_dispatch."""
    semestre, corte = normalizar_semestre(semestre), normalizar_corte(corte)
    if modo not in ("completa", "prueba"):
        raise ErrorCorrida("El modo debe ser 'completa' o 'prueba'.")
    reconciliar_corridas_activas(s, consultar_github=True)
    s.commit()
    activa = s.scalars(select(Ejecucion).where(Ejecucion.estado.in_(["en_cola", "en_curso"]),
                                              Ejecucion.creado_en > ahora() - timedelta(hours=8))).first()
    if activa is not None:
        raise ErrorCorrida(f"Ya hay una corrida en marcha ({activa.id_ejecucion}). Espere a que termine antes de lanzar otra.")
    id_ej = f"{semestre}-{corte.lower()}-{uuid.uuid4().hex[:6]}"
    ejec = Ejecucion(id_ejecucion=id_ej, semestre=semestre, corte=corte, ejecutado_por=solicitado_por, estado="en_cola",
                     modo=modo, ejecutor="github", fase="en_cola")
    s.add(ejec)
    s.flush()
    inputs = {
        "semestre": semestre,
        "corte": corte.lower(),
        "run_id": id_ej,
        "modo": modo,
        "ejecutado_por": solicitado_por,
        "fase": "completa",
    }
    try:
        _disparar_workflow_github(inputs)
    except ErrorCorrida as e:
        ejec.estado, ejec.errores = "fallida", str(e)
        s.commit()
        raise
    s.commit()
    return ejec


def progreso(s: Session, ejec: Ejecucion, consultar_github: bool = False) -> dict:
    """Progreso a partir de las particiones (igual para GitHub Actions y para la CLI local)."""
    if consultar_github and ejec.estado in ("en_cola", "en_curso"):
        if reconciliar_ejecucion(s, ejec, consultar_github=True, persistir=True):
            s.commit()
    filas = s.execute(select(Particion.fuente, Particion.estado, func.count(), func.sum(Particion.ofertas))
                      .where(Particion.id_ejecucion == ejec.id_ejecucion).group_by(Particion.fuente, Particion.estado)).all()
    por_fuente: dict[str, dict] = {}
    tot = {"total": 0, "hechas": 0, "error": 0, "pendientes": 0}
    for fuente, estado, n, ofertas in filas:
        d = por_fuente.setdefault(NOMBRES_FUENTE.get(fuente, fuente), {"total": 0, "hechas": 0, "error": 0, "pendientes": 0, "ofertas": 0})
        d["total"] += n
        d["ofertas"] += int(ofertas or 0)
        clave = {"hecha": "hechas", "omitida": "hechas", "error": "error"}.get(estado, "pendientes")
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
        gh = estado_github(ejec.id_ejecucion, ejec.github_run_url)
        if gh:
            salida["github"] = gh
            salida["github_run_url"] = salida["github_run_url"] or gh.get("url")
            if gh.get("estado") == "completed" and gh.get("conclusion") not in ("success", None):
                salida["aviso"] = "El workflow de GitHub ya terminó con errores; si el estado no se actualiza, recargue en unos segundos."
    elif ejec.estado in ("fallida", "incompleta") and ejec.fase == "terminada":
        pend = contar_consultas_pendientes(s, ejec.id_ejecucion)
        if pend:
            salida["aviso"] = (
                f"Quedaron {pend} consultas pendientes. Puede usar «Reanudar corrida» en esta pantalla "
                "con el mismo id (continúa sin duplicar particiones hechas)."
            )
        else:
            salida["aviso"] = (
                "La corrida terminó con errores. Puede «Reintentar consolidación» si la extracción ya terminó, "
                "o pedir ayuda a Desarrollo."
            )
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
