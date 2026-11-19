"""Cabeceras HTTP de caché para respuestas autenticadas."""
from __future__ import annotations

from sqlalchemy.orm import Session

from observatorio import analisis
from observatorio.normas_corrida import normalizar_corte

_HEADERS_PRIVADO = {"Cache-Control": "private, max-age=60"}
_HEADERS_CERRADO = {
    "Cache-Control": "private, max-age=600, stale-while-revalidate=3600",
}


def corte_considerado_cerrado(s: Session, semestre: str, corte: str) -> bool:
    """Cortes distintos al más reciente con ofertas (o marcados Final y no últimos)."""
    cortes = analisis.cortes_disponibles(s)
    if not cortes:
        return False
    ultimo = cortes[-1]
    if ultimo["semestre"] == semestre and ultimo["corte"] == normalizar_corte(corte):
        return False
    return True


def cabeceras_analisis(s: Session, semestre: str, corte: str) -> dict[str, str]:
    if corte_considerado_cerrado(s, semestre, corte):
        return dict(_HEADERS_CERRADO)
    return dict(_HEADERS_PRIVADO)