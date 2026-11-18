"""Sector industrial: normalización, inferencia por empresa y backfill (§9.1)."""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Oferta
from observatorio.filtro_ofertas import oferta_incluida_en_resultados
from observatorio.pipeline.sectores_taxonomia import sector_canonico, resumen_mapeo
from observatorio.texto import clave_empresa, es_empresa_generica, limpiar_espacios, plegar

log = logging.getLogger(__name__)

# Variantes en inglés → taxonomía española usada en LinkedIn
_SECTOR_EN_ES: dict[str, str] = {
    "consulting and business services": "Consultoría y servicios a empresas",
    "consulting": "Consultoría y servicios a empresas",
    "financial services": "Servicios financieros",
    "it services and it consulting": "Servicios y consultoría de TI",
    "technology, information and internet": "Tecnología, información e internet",
    "technology information and internet": "Tecnología, información e internet",
    "software development": "Desarrollo de software",
    "retail": "Comercio al por menor",
    "manufacturing": "Industria manufacturera",
    "hospital and health care": "Hospitales y atención sanitaria",
    "education management": "Gestión educativa y formación profesional",
    "banking": "Banca",
    "insurance": "Seguros",
    "accounting": "Contabilidad",
    "consumer goods": "Bienes de consumo",
    "staffing and recruiting": "Servicios de recursos humanos y selección de personal",
    "outsourcing and offshoring consulting": "Consultoría de externalización y deslocalización",
}

_RE_SECTOR_CT = re.compile(r"(?i)^\s*sector\s*:\s*(.+)$")


def _clave_sector_lookup(valor: str) -> str:
    return plegar(valor).strip()


def normalizar_sector(valor: str | None) -> str | None:
    """Normaliza sector de la fuente; traduce inglés conocido a español."""
    if not valor:
        return None
    t = limpiar_espacios(valor)
    if not t:
        return None
    clave = _clave_sector_lookup(t)
    trad = _SECTOR_EN_ES.get(clave)
    if trad:
        return trad[:255]
    if clave == t.lower():
        trad = _SECTOR_EN_ES.get(clave)
        if trad:
            return trad[:255]
    canon = sector_canonico(t)
    if canon:
        return canon[:255]
    return t[:255]


def extraer_sector_texto(texto: str) -> str | None:
    """Computrabajo y textos con línea «Sector: …»."""
    for linea in (texto or "").splitlines():
        m = _RE_SECTOR_CT.match(linea.strip())
        if m:
            return normalizar_sector(m.group(1))
    return None


def sector_desde_fuente(sector_crudo: str | None, descripcion: str | None = None) -> str | None:
    """Sector explícito de metadatos o, si falta, línea Sector en descripción."""
    sec = normalizar_sector(sector_crudo)
    if sec:
        return sec
    if descripcion:
        return extraer_sector_texto(descripcion)
    return None


def construir_mapa_sector_por_empresa(
    s: Session,
    *,
    min_ofertas: int = 2,
    solo_incluidas: bool = True,
) -> dict[str, str]:
    """Empresa normalizada → sector más frecuente (mínimo min_ofertas con sector conocido)."""
    q = select(Oferta.sector, Oferta.empresa).where(Oferta.sector.isnot(None), Oferta.sector != "")
    if solo_incluidas:
        q = q.where(oferta_incluida_en_resultados())
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for sector, empresa in s.execute(q):
        sec = normalizar_sector(sector)
        if not sec or es_empresa_generica(empresa):
            continue
        k = clave_empresa(empresa)
        if k:
            buckets[k][sec] += 1
    out: dict[str, str] = {}
    for k, ctr in buckets.items():
        mejor, n = ctr.most_common(1)[0]
        if n >= min_ofertas:
            out[k] = mejor
    return out


def inferir_sector_empresa(empresa: str | None, mapa: dict[str, str]) -> str | None:
    if es_empresa_generica(empresa):
        return None
    k = clave_empresa(empresa)
    if not k:
        return None
    return mapa.get(k)


def backfill_sectores(
    s: Session,
    semestre: str | None = None,
    corte: str | None = None,
    limite: int | None = None,
    lote: int = 300,
    *,
    aplicar: bool = True,
) -> dict:
    sin_antes = _contar_sin_sector(s, semestre, corte)
    distinct_antes = _contar_sectores_distintos(s, semestre, corte)
    valores_distintos = _listar_sectores_distintos(s, semestre, corte)
    mapa = construir_mapa_sector_por_empresa(s)

    inferidos = 0
    renorm = 0
    escrito = 0

    def _filtrar(q):
        if semestre:
            q = q.where(Oferta.semestre == semestre)
        if corte:
            q = q.where(Oferta.corte == corte)
        return q

    # 1) Completar sectores vacíos
    base_vacio = select(Oferta).where(oferta_incluida_en_resultados())
    base_vacio = base_vacio.where((Oferta.sector.is_(None)) | (Oferta.sector == ""))
    base_vacio = _filtrar(base_vacio)
    ultimo_id: str | None = None
    while True:
        q = base_vacio.order_by(Oferta.id_oferta)
        if ultimo_id is not None:
            q = q.where(Oferta.id_oferta > ultimo_id)
        tam = lote if limite is None else min(lote, max(0, (limite or 0) - inferidos - renorm))
        if limite is not None and tam <= 0:
            break
        filas = list(s.scalars(q.limit(tam)))
        if not filas:
            break
        lote_escritos = 0
        for o in filas:
            sec = sector_desde_fuente(o.sector)
            if not sec:
                sec = inferir_sector_empresa(o.empresa, mapa)
            if not sec:
                continue
            inferidos += 1
            if aplicar:
                o.sector = sec
                lote_escritos += 1
                escrito += 1
        ultimo_id = filas[-1].id_oferta
        if aplicar and lote_escritos:
            s.commit()
            log.info("Backfill sector (inferencia): %d ofertas en lote", lote_escritos)
        if len(filas) < tam:
            break

    # 2) Renormalizar sectores existentes a taxonomía canónica
    base_sec = select(Oferta).where(oferta_incluida_en_resultados())
    base_sec = base_sec.where(Oferta.sector.isnot(None), Oferta.sector != "")
    base_sec = _filtrar(base_sec)
    ultimo_id = None
    while True:
        q = base_sec.order_by(Oferta.id_oferta)
        if ultimo_id is not None:
            q = q.where(Oferta.id_oferta > ultimo_id)
        tam = lote if limite is None else min(lote, max(0, (limite or 0) - inferidos - renorm))
        if limite is not None and tam <= 0:
            break
        filas = list(s.scalars(q.limit(tam)))
        if not filas:
            break
        lote_escritos = 0
        for o in filas:
            canon = normalizar_sector(o.sector)
            if not canon or canon == o.sector:
                continue
            renorm += 1
            if aplicar:
                o.sector = canon
                lote_escritos += 1
                escrito += 1
        ultimo_id = filas[-1].id_oferta
        if aplicar and lote_escritos:
            s.commit()
            log.info("Backfill sector (renormalización): %d ofertas en lote", lote_escritos)
        if len(filas) < tam:
            break

    sin_despues = _contar_sin_sector(s, semestre, corte) if aplicar else max(0, sin_antes - inferidos)
    distinct_despues = _contar_sectores_distintos(s, semestre, corte) if aplicar else len(
        {sector_canonico(v) for v in valores_distintos if v}
    )
    mapeo = resumen_mapeo(valores_distintos)
    cnt_por_canon = {k: len(vs) for k, vs in mapeo["por_canonico"].items()}

    return {
        "aplicar": aplicar,
        "ofertas_inferidas": inferidos,
        "ofertas_renormalizadas": renorm,
        "ofertas_actualizadas": inferidos + renorm,
        "ofertas_escritas": escrito if aplicar else 0,
        "sin_sector_antes": sin_antes,
        "sin_sector_despues": sin_despues,
        "sectores_distintos_antes": distinct_antes,
        "sectores_distintos_despues": distinct_despues,
        "conteo_raw_por_canonico": cnt_por_canon,
        "empresas_en_mapa": len(mapa),
        "semestre": semestre,
        "corte": corte,
    }


def _contar_sin_sector(s: Session, semestre: str | None, corte: str | None) -> int:
    q = select(func.count()).select_from(Oferta).where(oferta_incluida_en_resultados())
    q = q.where((Oferta.sector.is_(None)) | (Oferta.sector == ""))
    if semestre:
        q = q.where(Oferta.semestre == semestre)
    if corte:
        q = q.where(Oferta.corte == corte)
    return int(s.scalar(q) or 0)


def _contar_sectores_distintos(s: Session, semestre: str | None, corte: str | None) -> int:
    q = (
        select(func.count(func.distinct(Oferta.sector)))
        .select_from(Oferta)
        .where(oferta_incluida_en_resultados(), Oferta.sector.isnot(None), Oferta.sector != "")
    )
    if semestre:
        q = q.where(Oferta.semestre == semestre)
    if corte:
        q = q.where(Oferta.corte == corte)
    return int(s.scalar(q) or 0)


def _listar_sectores_distintos(s: Session, semestre: str | None, corte: str | None) -> list[str]:
    q = select(Oferta.sector).where(oferta_incluida_en_resultados(), Oferta.sector.isnot(None), Oferta.sector != "")
    if semestre:
        q = q.where(Oferta.semestre == semestre)
    if corte:
        q = q.where(Oferta.corte == corte)
    q = q.distinct()
    return [str(x) for x in s.scalars(q) if x]