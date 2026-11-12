"""Clasificación por carrera y relevancia (RF-06): reglas primero.

Resultado por oferta:
- `relevante`  -> se guarda con sus carreras (máximo 5, la principal primero).
- `no_relevante` -> se descarta (no se guarda en `ofertas`).
- `dudosa`     -> se envía al LLM (OpenRouter, modelos gratuitos). Si el LLM no
  está disponible se aplica la regla de respaldo.

Puntaje por carrera = 3 × (palabras fuertes en el título)
                    + 2 × (carrera mencionada explícitamente en la descripción)
                    + min(palabras débiles en la descripción, 3)
                    + 1 si el término de búsqueda pertenece a esa carrera.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from observatorio.texto import plegar

MAX_CARRERAS = 5

# Palabras de título que indican jerarquía pero no área: no salvan a un título
# excluido ("Enfermera jefe", "Coordinador de desarrollo de software").
GENERICAS_TITULO = {"jefe", "coordinador", "coordinadora", "director", "directora", "gerente", "gerencia", "manager",
                    "ejecutivo", "management", "lider", "líder", "proyectos", "calidad", "operaciones", "procesos"}

# Menciones explícitas de la carrera en la descripción (señal fuerte)
EXPLICITAS = {
    "Contaduría Pública": [r"contadur[ií]a", r"contador(?:a)? p[uú]blic[oa]", r"tarjeta profesional (?:de|como) contador"],
    "Economía": [r"econom[ií]a\b", r"economista", r"ciencias econ[oó]micas"],
    "Administración de Empresas": [r"administraci[oó]n de empresas", r"administrador(?:a)? de empresas", r"ciencias administrativas",
                                   r"administraci[oó]n empresarial", r"business administration"],
}


@dataclass
class Clasificacion:
    estado: str  # relevante | no_relevante | dudosa
    carreras: list[str] = field(default_factory=list)
    puntajes: dict[str, float] = field(default_factory=dict)
    motivo: str = ""
    clasificado_por: str = "reglas"

    @property
    def carrera_texto(self) -> str:
        return "; ".join(self.carreras)


def _contiene(texto_plegado: str, palabra: str) -> bool:
    w = plegar(palabra)
    if w.endswith(" "):  # palabra con espacio final exige palabra completa
        return re.search(r"(?<![a-z0-9])" + re.escape(w.strip()) + r"(?![a-z0-9])", texto_plegado) is not None
    return re.search(r"(?<![a-z0-9])" + re.escape(w), texto_plegado) is not None


def titulo_excluido_operativo(cargo: str, patrones: list[str]) -> bool:
    """Cargos operativos de bajo nivel que no deben contarse aunque coincidan con reglas amplias (p. ej. «administrativ»)."""
    t = " " + plegar(cargo) + " "
    return any(_contiene(t, p) for p in patrones)


class ClasificadorReglas:
    def __init__(
        self,
        reglas: dict,
        exclusion_titulo: list[str],
        carreras: list[str] | None = None,
        exclusion_operativa: list[str] | None = None,
    ):
        self.reglas = reglas
        self.exclusion = exclusion_titulo
        self.exclusion_operativa = exclusion_operativa or []
        self.carreras = carreras or list(reglas.keys())
        self.explicitas = {c: [re.compile(p) for p in EXPLICITAS.get(c, [])] for c in self.carreras}

    def puntajes(self, cargo: str, descripcion: str, carrera_termino: str | None) -> tuple[dict, dict]:
        t = " " + plegar(cargo) + " "
        d = plegar(descripcion or "")[:6000]
        fuertes: dict[str, int] = {}
        especificas: dict[str, int] = {}
        puntos: dict[str, float] = {}
        for c in self.carreras:
            r = self.reglas.get(c, {})
            hits = [w for w in r.get("titulo", []) if _contiene(t, w)]
            n_tit = len(hits)
            especificas[c] = sum(1 for w in hits if plegar(w.strip()) not in {plegar(g) for g in GENERICAS_TITULO})
            n_exp = sum(1 for p in self.explicitas.get(c, []) if p.search(d))
            n_desc = sum(1 for w in r.get("descripcion", []) if _contiene(d, w))
            fuertes[c] = n_tit
            puntos[c] = 3 * n_tit + 2 * n_exp + min(n_desc, 3) + (1 if carrera_termino == c else 0)
        self._especificas = especificas
        return fuertes, puntos

    def clasificar(self, cargo: str, descripcion: str = "", carrera_termino: str | None = None) -> Clasificacion:
        if titulo_excluido_operativo(cargo, self.exclusion_operativa):
            return Clasificacion("no_relevante", [], {}, "cargo operativo de bajo nivel (fuera del alcance del observatorio)")
        fuertes, puntos = self.puntajes(cargo, descripcion, carrera_termino)
        t = " " + plegar(cargo) + " "
        excluido = any(_contiene(t, w) for w in self.exclusion)
        hay_fuerte = any(v > 0 for v in fuertes.values())
        hay_especifica = any(v > 0 for v in self._especificas.values())
        orden = sorted((c for c in self.carreras if puntos[c] > 0), key=lambda c: -puntos[c])

        if excluido and not hay_especifica:
            return Clasificacion("no_relevante", [], puntos, "título fuera de la FCE")
        if hay_fuerte:
            principal = orden[0]
            otras = [c for c in orden[1:] if fuertes[c] > 0 or puntos[c] >= 3]
            return Clasificacion("relevante", ([principal] + otras)[:MAX_CARRERAS], puntos, "título")
        if not orden:
            return Clasificacion("no_relevante", [], puntos, "sin señales de carrera")
        return Clasificacion("dudosa", orden[:MAX_CARRERAS], puntos, "solo descripción o término")

    @staticmethod
    def respaldo(c: Clasificacion) -> Clasificacion:
        """Regla de respaldo para dudosas cuando no hay LLM: puntaje ≥ 3."""
        aceptadas = [k for k in c.carreras if c.puntajes.get(k, 0) >= 3]
        if aceptadas:
            return Clasificacion("relevante", aceptadas[:MAX_CARRERAS], c.puntajes, "respaldo por reglas", "reglas_respaldo")
        return Clasificacion("no_relevante", [], c.puntajes, "respaldo por reglas: evidencia insuficiente", "reglas_respaldo")

