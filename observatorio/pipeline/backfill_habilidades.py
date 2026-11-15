"""Vuelve a detectar habilidades blandas e idiomas en ofertas ya guardadas (RF-18)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Oferta
from observatorio.filtro_ofertas import oferta_incluida_en_resultados
from observatorio.pipeline.detector_habilidades_idiomas import DetectorHabilidadesIdiomas
from observatorio.pipeline.procesar import Procesador


def backfill_habilidades_idiomas(
    s: Session,
    semestre: str | None = None,
    corte: str | None = None,
    limite: int | None = None,
) -> dict:
    detector = DetectorHabilidadesIdiomas.desde_bd(s)
    q = select(Oferta).where(oferta_incluida_en_resultados()).order_by(Oferta.id_oferta)
    if semestre:
        q = q.where(Oferta.semestre == semestre)
    if corte:
        q = q.where(Oferta.corte == corte)
    if limite:
        q = q.limit(limite)
    n = 0
    # Reutiliza la lógica de relaciones sin corrida completa
    class _SoloHabilidades:
        def __init__(self, session: Session, det):
            self.s = session
            self.detector_gc = det

        _aplicar_habilidades_idiomas = Procesador._aplicar_habilidades_idiomas

    aux = _SoloHabilidades(s, detector)
    for o in s.scalars(q):
        aux._aplicar_habilidades_idiomas(o)
        n += 1
        if n % 200 == 0:
            s.flush()
    s.flush()
    return {"ofertas_actualizadas": n, "semestre": semestre, "corte": corte}