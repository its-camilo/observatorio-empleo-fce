"""Sector industrial: normalización, inferencia por empresa y backfill (§9.1)."""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Oferta
from observatorio.filtro_ofertas import oferta_incluida_en_resultados
from observatorio.texto import clave_empresa, es_empresa_generica, limpiar_espacios, plegar

log = logging.getLogger(__name__)

# Variantes en inglés → taxonomía española usada en LinkedIn
_SECTOR_EN_ES: dict[str, str] = {
    "consulting and business services": "Servicios de consultoría y asesoramiento",
    "consulting": "Servicios de consultoría y asesoramiento",
    "financial services": "Servicios financieros",
    "it services and it consulting": "Servicios y consultoría en TI",
    "technology, information and internet": "Tecnología, información e internet",
    "technology information and internet": "Tecnología, información e internet",
    "software development": "Desarrollo de software",
    "retail": "Comercio minorista",
    "manufacturing": "Fabricación",
    "hospital and health care": "Hospitales y atención sanitaria",
    "education management": "Gestión educativa",
    "banking": "Banca",
    "insurance": "Seguros",
    "accounting": "Contabilidad",
    "consumer goods": "Bienes de consumo",
    "staffing and recruiting": "Selección de personal y reclutamiento",
    "outsourcing and offshoring consulting": "Externalización y consultoría de offshoring",
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
    mapa = construir_mapa_sector_por_empresa(s)
    base = select(Oferta).where(oferta_incluida_en_resultados())
    base = base.where((Oferta.sector.is_(None)) | (Oferta.sector == ""))
    if semestre:
        base = base.where(Oferta.semestre == semestre)
    if corte:
        base = base.where(Oferta.corte == corte)
    n = 0
    ultimo_id: str | None = None
    while True:
        q = base.order_by(Oferta.id_oferta)
        if ultimo_id is not None:
            q = q.where(Oferta.id_oferta > ultimo_id)
        tam = lote if not limite else min(lote, max(0, limite - n))
        if tam <= 0:
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
            n += 1
            if aplicar:
                o.sector = sec
                lote_escritos += 1
        ultimo_id = filas[-1].id_oferta
        if aplicar and lote_escritos:
            s.commit()
            log.info("Backfill sector: %d ofertas actualizadas en este lote", lote_escritos)
        if len(filas) < tam:
            break
    sin_despues = _contar_sin_sector(s, semestre, corte) if aplicar else max(0, sin_antes - n)
    return {
        "aplicar": aplicar,
        "ofertas_actualizadas": n,
        "sin_sector_antes": sin_antes,
        "sin_sector_despues": sin_despues,
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