"""Agregados precalculados por corte (dashboard, filtros, rankings, comparación)."""
from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from observatorio import analisis
from observatorio.consultas import valores_filtros
from observatorio.db.modelos import AgregadoAnalisis, ConteoOfertasCorte, Oferta, ahora
from observatorio.filtro_ofertas import oferta_incluida_en_resultados
from sqlalchemy import func

log = logging.getLogger(__name__)

CARRERAS_RANKING = ["", "Administración de Empresas", "Contaduría Pública", "Economía"]


def guardar(s: Session, clave: str, payload: Any) -> None:
    fila = s.get(AgregadoAnalisis, clave)
    if fila is None:
        fila = AgregadoAnalisis(clave=clave, payload=payload, actualizado_en=ahora())
        s.add(fila)
    else:
        fila.payload = payload
        fila.actualizado_en = ahora()


def leer(s: Session, clave: str) -> Any | None:
    fila = s.get(AgregadoAnalisis, clave)
    return fila.payload if fila is not None else None


def obtener_o_calcular(
    s: Session,
    clave: str,
    calcular: Callable[[], Any],
    *,
    forzar: bool = False,
) -> Any:
    if not forzar:
        hit = leer(s, clave)
        if hit is not None:
            return hit
    valor = calcular()
    guardar(s, clave, valor)
    s.flush()
    return valor


def _refrescar_conteos_corte(s: Session, semestre: str, corte: str) -> None:
    s.execute(
        delete(ConteoOfertasCorte).where(
            ConteoOfertasCorte.semestre == semestre,
            ConteoOfertasCorte.corte == corte,
        )
    )
    totales = analisis._ofertas_por_carrera(s, semestre, corte)
    for carrera, total in totales.items():
        s.add(
            ConteoOfertasCorte(
                semestre=semestre,
                corte=corte,
                carrera=carrera,
                total=total,
            )
        )


def conteo_ofertas_precalculado(
    s: Session,
    semestre: str | None,
    corte: str | None,
    carrera: str | None,
) -> int | None:
    """Devuelve total si coincide con un conteo almacenado; si no, None."""
    if not semestre or not corte:
        return None
    clave_carrera = carrera or "Todas"
    fila = s.get(ConteoOfertasCorte, (semestre, corte, clave_carrera))
    if fila is None and carrera:
        return None
    if fila is None:
        fila = s.get(ConteoOfertasCorte, (semestre, corte, "Todas"))
    return fila.total if fila else None


def refrescar_agregados_globales(s: Session) -> None:
    guardar(s, "cortes_disponibles", analisis.cortes_disponibles(s))
    guardar(s, "filtros:ofertas", valores_filtros(s))
    total = s.scalar(select(func.count()).select_from(Oferta).where(oferta_incluida_en_resultados())) or 0
    guardar(s, "total_historico_ofertas", total)


def refrescar_agregados_corte(s: Session, semestre: str, corte: str) -> dict[str, int]:
    """Recalcula y persiste agregados para un corte. Devuelve resumen de claves escritas."""
    escritas = 0
    _refrescar_conteos_corte(s, semestre, corte)

    clave_resumen = f"resumen:{semestre}:{corte}"
    guardar(s, clave_resumen, analisis.resumen_corte(s, semestre, corte, para_dashboard=True))
    escritas += 1

    for carrera in CARRERAS_RANKING:
        car = carrera or None
        clave_rank = f"analisis:ranking:{semestre}:{corte}:{carrera}"
        guardar(
            s,
            clave_rank,
            {
                "ranking": analisis.ranking(s, semestre, corte, car),
                "grupos": analisis.ranking_por_grupo(s, semestre, corte, car),
            },
        )
        escritas += 1
        guardar(
            s,
            f"analisis:ranking-hab:{semestre}:{corte}:{carrera}",
            {"ranking": analisis.ranking_habilidades(s, semestre, corte, car)},
        )
        guardar(
            s,
            f"analisis:ranking-idi:{semestre}:{corte}:{carrera}",
            {"ranking": analisis.ranking_idiomas(s, semestre, corte, car)},
        )
        guardar(
            s,
            f"analisis:ranking-tipo:{semestre}:{corte}:{carrera}",
            {"ranking": analisis.ranking_tipo_oferta(s, semestre, corte, car)},
        )
        guardar(
            s,
            f"analisis:ranking-sector:{semestre}:{corte}:{carrera}",
            {"ranking": analisis.ranking_sector(s, semestre, corte, car)},
        )
        escritas += 4

    prev = analisis.corte_anterior(s, semestre, corte)
    if prev:
        sa, ca = prev
        for carrera in CARRERAS_RANKING:
            car = carrera or None
            clave_cmp = f"analisis:comparar:{sa}:{ca}:{semestre}:{corte}:{carrera}"
            guardar(s, clave_cmp, analisis.comparar(s, sa, ca, semestre, corte, car))
            escritas += 1

    refrescar_agregados_globales(s)
    escritas += 3
    log.info("Agregados actualizados para %s %s (%s claves aprox.)", semestre, corte, escritas)
    return {"semestre": semestre, "corte": corte, "claves_aprox": escritas}


def backfill_agregados_existentes(s: Session) -> list[dict]:
    cortes = analisis.cortes_disponibles(s)
    resumen: list[dict] = []
    for item in cortes:
        resumen.append(refrescar_agregados_corte(s, item["semestre"], item["corte"]))
    return resumen