"""Cierre de corridas interrumpidas y reconciliación con GitHub Actions."""
from __future__ import annotations

import logging
import re
from datetime import timedelta

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.config import ajustes
from observatorio.db.modelos import Ejecucion, Particion, ahora

log = logging.getLogger(__name__)

API = "https://api.github.com"
_CONCLUSIONES_ERROR = frozenset({"failure", "cancelled", "timed_out", "action_required", "stale"})
_RUN_URL = re.compile(r"/actions/runs/(\d+)(?:\?|$|/)")

# Corridas completas en Actions pueden superar 6 h; margen para reconciliar sin token.
HORAS_MAX_EN_CURSO = 14.0
HORAS_MAX_HUERFANA = 36.0


def _cabeceras_github(permitir_sin_token: bool = True) -> dict | None:
    a = ajustes()
    base = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if a.github_token:
        return {**base, "Authorization": f"Bearer {a.github_token}"}
    if not permitir_sin_token or not a.github_repo:
        return None
    return base


def _run_id_desde_url(url: str | None) -> int | None:
    if not url:
        return None
    m = _RUN_URL.search(url)
    return int(m.group(1)) if m else None


def _consultar_run_por_id(repo: str, run_id: int, headers: dict) -> dict | None:
    try:
        r = requests.get(f"{API}/repos/{repo}/actions/runs/{run_id}", headers=headers, timeout=8)
        if r.status_code != 200:
            return None
        run = r.json()
        return {
            "estado": run.get("status"),
            "conclusion": run.get("conclusion"),
            "url": run.get("html_url"),
            "iniciado": run.get("run_started_at"),
        }
    except requests.RequestException:
        return None


def estado_github(id_ejecucion: str, github_run_url: str | None = None) -> dict | None:
    """Estado del workflow en GitHub (con token si existe; si no, consulta pública por URL de run)."""
    a = ajustes()
    if not a.github_repo:
        return None
    headers = _cabeceras_github(permitir_sin_token=True)
    if headers is None:
        return None

    run_num = _run_id_desde_url(github_run_url)
    if run_num is not None:
        gh = _consultar_run_por_id(a.github_repo, run_num, headers)
        if gh:
            return gh

    if not a.github_token:
        return None
    try:
        r = requests.get(
            f"{API}/repos/{a.github_repo}/actions/workflows/{a.github_workflow}/runs",
            headers=headers,
            params={"per_page": 30, "event": "workflow_dispatch"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        for run in r.json().get("workflow_runs", []):
            titulo = run.get("display_title") or run.get("name") or ""
            if id_ejecucion in titulo:
                return {
                    "estado": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "url": run.get("html_url"),
                    "iniciado": run.get("run_started_at"),
                }
    except requests.RequestException:
        return None
    return None


def _hubo_trabajo(s: Session, ejec: Ejecucion) -> bool:
    parts = list(s.scalars(select(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion)))
    if not parts:
        return ejec.ofertas_encontradas > 0 or ejec.fase not in (None, "en_cola", "preparada")
    return any(p.estado in ("hecha", "error") for p in parts)


def _estado_cierre_por_trabajo(s: Session, ejec: Ejecucion, conclusion: str | None) -> str:
    if conclusion in _CONCLUSIONES_ERROR and _hubo_trabajo(s, ejec):
        return "incompleta"
    if conclusion in ("cancelled", "timed_out") and _hubo_trabajo(s, ejec):
        return "incompleta"
    parts = list(s.scalars(select(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion)))
    if parts and any(p.estado == "hecha" for p in parts):
        pend = sum(1 for p in parts if p.estado == "pendiente")
        err = sum(1 for p in parts if p.estado == "error")
        if pend or err:
            return "incompleta"
    return "fallida"


def cerrar_ejecucion_error(
    s: Session,
    ejec: Ejecucion,
    mensaje: str,
    *,
    conclusion_github: str | None = None,
    estado: str | None = None,
) -> bool:
    """Marca la ejecución como terminada con error. Devuelve True si hubo cambio."""
    if ejec.estado not in ("en_cola", "en_curso"):
        return False
    fin = ahora()
    ejec.fase = "terminada"
    ejec.fin = fin
    if not ejec.inicio:
        ejec.inicio = ejec.creado_en or fin
    ejec.duracion_segundos = max(0, int((fin - ejec.inicio).total_seconds()))
    detalle = list(ejec.errores_detalle or [])
    linea = mensaje
    if conclusion_github and conclusion_github not in mensaje:
        linea = f"{mensaje} (GitHub: {conclusion_github})"
    if linea not in detalle:
        detalle.append(linea)
    ejec.errores_detalle = detalle
    ejec.errores = "\n".join(detalle)
    ejec.estado = estado or _estado_cierre_por_trabajo(s, ejec, conclusion_github)
    if conclusion_github == "stale":
        ejec.estado = "incompleta" if _hubo_trabajo(s, ejec) else "fallida"
    return True


def _demasiado_antigua(ejec: Ejecucion, horas: float) -> bool:
    ref = ejec.inicio or ejec.creado_en
    if ref is None:
        return False
    return ahora() - ref > timedelta(hours=horas)


def reconciliar_ejecucion(
    s: Session,
    ejec: Ejecucion,
    *,
    consultar_github: bool = True,
    persistir: bool = True,
    horas_max_en_curso: float = HORAS_MAX_EN_CURSO,
    horas_max_huerfana: float = HORAS_MAX_HUERFANA,
) -> bool:
    """Si la corrida quedó colgada, ciérrala en BD. Devuelve True si cambió el estado."""
    if ejec.estado not in ("en_cola", "en_curso"):
        return False

    mensaje: str | None = None
    conclusion: str | None = None

    if consultar_github and ejec.ejecutor == "github":
        gh = estado_github(ejec.id_ejecucion, ejec.github_run_url)
        if gh:
            if gh.get("url") and not ejec.github_run_url:
                ejec.github_run_url = gh["url"]
            if gh.get("estado") == "completed":
                conc = gh.get("conclusion")
                if conc in _CONCLUSIONES_ERROR or (conc and conc != "success"):
                    conclusion = conc or "failure"
                    mensaje = (
                        "El workflow de GitHub Actions terminó sin éxito. "
                        "Revise el enlace de GitHub Actions para el detalle de los jobs."
                    )

    if mensaje is None and _demasiado_antigua(ejec, horas_max_huerfana):
        conclusion = "stale"
        mensaje = (
            f"La corrida superó {int(horas_max_huerfana)} h sin cierre en la base de datos "
            "(reconciliación automática)."
        )
    elif mensaje is None and ejec.estado == "en_curso" and _demasiado_antigua(ejec, horas_max_en_curso):
        conclusion = "stale"
        mensaje = (
            f"La corrida lleva más de {int(horas_max_en_curso)} h en curso sin finalizar "
            "(reconciliación automática)."
        )

    if mensaje is None:
        return False

    changed = cerrar_ejecucion_error(s, ejec, mensaje, conclusion_github=conclusion)
    if changed and persistir:
        s.flush()
    return changed


def reconciliar_corridas_activas(s: Session, *, consultar_github: bool = True) -> list[str]:
    """Reconcilia todas las ejecuciones en cola o en curso."""
    ids: list[str] = []
    for ejec in s.scalars(select(Ejecucion).where(Ejecucion.estado.in_(("en_cola", "en_curso")))):
        if reconciliar_ejecucion(s, ejec, consultar_github=consultar_github, persistir=True):
            ids.append(ejec.id_ejecucion)
    return ids


def cerrar_corridas_colgadas(
    s: Session,
    *,
    ids: list[str] | None = None,
    consultar_github: bool = True,
    horas_max_en_curso: float = HORAS_MAX_EN_CURSO,
    horas_max_huerfana: float = HORAS_MAX_HUERFANA,
    forzar_ids: bool = False,
) -> dict:
    """Cierra corridas huérfanas (mantenimiento). `forzar_ids` cierra los ids aunque no pasen el umbral de horas."""
    q = select(Ejecucion).where(Ejecucion.estado.in_(("en_cola", "en_curso")))
    if ids:
        q = q.where(Ejecucion.id_ejecucion.in_(ids))
    cerradas: list[str] = []
    for ejec in s.scalars(q):
        if forzar_ids and ids and ejec.id_ejecucion in ids:
            if cerrar_ejecucion_error(
                s,
                ejec,
                "Cierre manual de mantenimiento: corrida quedó en curso/cola.",
                conclusion_github="failure",
            ):
                cerradas.append(ejec.id_ejecucion)
            continue
        if reconciliar_ejecucion(
            s,
            ejec,
            consultar_github=consultar_github,
            persistir=True,
            horas_max_en_curso=horas_max_en_curso,
            horas_max_huerfana=horas_max_huerfana,
        ):
            cerradas.append(ejec.id_ejecucion)
    s.commit()
    return {"cerradas": cerradas, "cantidad": len(cerradas)}
