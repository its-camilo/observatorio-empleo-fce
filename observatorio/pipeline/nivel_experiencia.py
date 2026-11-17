"""Filtro por nivel de experiencia (RF-01) y parámetros de búsqueda en LinkedIn."""
from __future__ import annotations

import copy
from typing import Any

NIVELES_EXPERIENCIA = [
    "Practicante",
    "Sin experiencia / Junior",
    "Intermedio",
    "Senior",
    "Directivo",
    "No especificado",
]

MOTIVO_NIVEL_EXPERIENCIA = "nivel_experiencia_no_permitido"

# Códigos f_E del buscador invitado de LinkedIn (experiencia)
_LINKEDIN_NIVEL_A_FE: dict[str, tuple[str, ...]] = {
    "Practicante": ("1",),
    "Sin experiencia / Junior": ("2",),
    "Intermedio": ("3",),
    "Senior": ("4",),
    "Directivo": ("5", "6"),
}


def config_niveles_defecto() -> dict[str, Any]:
    return {"modo": "todos", "niveles": list(NIVELES_EXPERIENCIA)}


def sugerencia_niveles_algunos() -> list[str]:
    return ["Practicante", "Sin experiencia / Junior"]


def normalizar_config_niveles(raw: Any) -> dict[str, Any]:
    """Forma canónica: modo todos|algunos + lista de niveles permitidos."""
    if isinstance(raw, dict) and raw.get("modo") in ("todos", "algunos"):
        modo = str(raw["modo"])
        niveles = [x for x in (raw.get("niveles") or []) if x in NIVELES_EXPERIENCIA]
        if modo == "todos":
            return {"modo": "todos", "niveles": list(NIVELES_EXPERIENCIA)}
        return {"modo": "algunos", "niveles": niveles}
    # Compatibilidad: lista plana antigua
    if isinstance(raw, list):
        niveles = [x for x in raw if x in NIVELES_EXPERIENCIA]
        if not niveles or len(niveles) >= len(NIVELES_EXPERIENCIA):
            return {"modo": "todos", "niveles": list(NIVELES_EXPERIENCIA)}
        return {"modo": "algunos", "niveles": niveles}
    return copy.deepcopy(config_niveles_defecto())


def niveles_efectivos(config: Any) -> set[str] | None:
    """None = sin filtro (modo todos). Set vacío = ningún nivel permitido (modo algunos sin selección)."""
    cfg = normalizar_config_niveles(config)
    if cfg["modo"] == "todos":
        return None
    return set(cfg["niveles"])


def filtro_activo(config: Any) -> bool:
    return niveles_efectivos(config) is not None


def nivel_permitido(nivel: str | None, permitidos: set[str] | None) -> bool:
    if permitidos is None:
        return True
    if not permitidos:
        return False
    n = (nivel or "No especificado").strip()
    if n not in NIVELES_EXPERIENCIA:
        n = "No especificado"
    return n in permitidos


def linkedin_query_f_e(permitidos: set[str] | None) -> str | None:
    """Fragmento de query string &f_E=… para LinkedIn, o None si no aplica filtro."""
    if not permitidos:
        return None
    codigos: list[str] = []
    for nivel in permitidos:
        if nivel == "No especificado":
            continue
        for c in _LINKEDIN_NIVEL_A_FE.get(nivel, ()):
            if c not in codigos:
                codigos.append(c)
    if not codigos:
        return None
    return "&".join(f"f_E={c}" for c in codigos)