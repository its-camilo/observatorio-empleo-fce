"""Normalización de semestre/corte y nombres de fuente (sin dependencias de scraping)."""
from __future__ import annotations

import re

NOMBRES_FUENTE = {"linkedin": "LinkedIn", "indeed": "Indeed", "computrabajo": "Computrabajo", "google": "Google Jobs"}
CORTES = {"inicio": "Inicio", "mitad": "Mitad", "final": "Final"}


def normalizar_corte(corte: str) -> str:
    c = (corte or "").strip().lower()
    if c not in CORTES:
        raise ValueError("El corte debe ser inicio, mitad o final")
    return CORTES[c]


def normalizar_semestre(semestre: str) -> str:
    s = (semestre or "").strip().upper().replace(" ", "")
    m = re.fullmatch(r"(\d{4})-?(I{1,2}|1|2)", s)
    if not m:
        raise ValueError("El semestre debe tener la forma 2026-I o 2026-II")
    return f"{m.group(1)}-{'I' if m.group(2) in ('I', '1') else 'II'}"
