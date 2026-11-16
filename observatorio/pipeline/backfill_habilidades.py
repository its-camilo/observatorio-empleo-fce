"""Vuelve a detectar habilidades blandas e idiomas en ofertas ya guardadas (RF-18)."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from observatorio.db.modelos import Oferta
from observatorio.filtro_ofertas import oferta_incluida_en_resultados
from observatorio.pipeline.detector_habilidades_idiomas import DetectorHabilidadesIdiomas
from observatorio.pipeline.procesar import Procesador

logger = logging.getLogger(__name__)


def backfill_habilidades_idiomas(
    s: Session,
    semestre: str | None = None,
    corte: str | None = None,
    limite: int | None = None,
) -> dict:
    detector = DetectorHabilidadesIdiomas.desde_bd(s)
    base = select(Oferta).where(oferta_incluida_en_resultados())
    if semestre:
        base = base.where(Oferta.semestre == semestre)
    if corte:
        base = base.where(Oferta.corte == corte)

    # Reutiliza la lógica de relaciones sin corrida completa
    class _SoloHabilidades:
        def __init__(self, session: Session, det):
            self.s = session
            self.detector_gc = det

        _aplicar_habilidades_idiomas = Procesador._aplicar_habilidades_idiomas

    aux = _SoloHabilidades(s, detector)
    n = 0
    ultimo_id = None
    lote = 300
    while True:
        q = (
            base.options(
                selectinload(Oferta.habilidades),
                selectinload(Oferta.idiomas_detectados),
            )
            .order_by(Oferta.id_oferta)
        )
        if ultimo_id is not None:
            q = q.where(Oferta.id_oferta > ultimo_id)
        tam = lote if not limite else min(lote, limite - n)
        if tam <= 0:
            break
        ofertas = list(s.scalars(q.limit(tam)))
        if not ofertas:
            break
        for o in ofertas:
            aux._aplicar_habilidades_idiomas(o)
        n += len(ofertas)
        ultimo_id = ofertas[-1].id_oferta
        s.commit()
        logger.info("Backfill RF-18: %d ofertas procesadas", n)
    return {"ofertas_actualizadas": n, "semestre": semestre, "corte": corte}