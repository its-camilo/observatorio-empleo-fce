"""Filtros compartidos: ofertas visibles en reportes (no excluidas por ajuste de proporción)."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.sql import ColumnElement

from observatorio.db.modelos import Oferta


def oferta_incluida_en_resultados() -> ColumnElement[bool]:
    """True si la oferta cuenta para exportes, dashboard y totales de corrida."""
    return or_(Oferta.excluida_resultado_corrida.is_(False), Oferta.excluida_resultado_corrida.is_(None))


def oferta_incluida_en_corrida(id_ejecucion: str) -> ColumnElement[bool]:
    from sqlalchemy import and_

    return and_(Oferta.id_ejecucion == id_ejecucion, oferta_incluida_en_resultados())