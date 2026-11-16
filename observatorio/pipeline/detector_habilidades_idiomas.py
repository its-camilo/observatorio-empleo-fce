"""Detección de habilidades blandas e idiomas desde catálogo editable (RF-18)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.db.modelos import CatalogoHabilidad, CatalogoIdioma
from observatorio.pipeline.habilidades import _NIVEL, _NIVEL_LEGIBLE
from observatorio.texto import plegar

_NIVEL_RX = re.compile(rf"\b{_NIVEL}\b", re.I)


@dataclass(frozen=True)
class IdiomaDetectado:
    idioma: str
    nivel: str | None
    texto: str


@dataclass(frozen=True)
class HabilidadDetectada:
    habilidad: str
    texto: str


def _frases_por_nombre(items: list[tuple[str, list[str]]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for nombre, frases in items:
        for f in frases:
            out.append((nombre, plegar(f)))
    return out


class DetectorHabilidadesIdiomas:
    def __init__(self, habilidades: list[tuple[str, list[str]]], idiomas: list[tuple[str, list[str]]]):
        self._hab = _frases_por_nombre(habilidades)
        self._idi = idiomas

    @classmethod
    def desde_bd(cls, s: Session) -> "DetectorHabilidadesIdiomas":
        hab: list[tuple[str, list[str]]] = []
        for c in s.scalars(select(CatalogoHabilidad).where(CatalogoHabilidad.activo.is_(True))):
            frases = [x.texto for x in c.sinonimos] or [c.nombre]
            hab.append((c.nombre, frases))
        idi: list[tuple[str, list[str]]] = []
        for c in s.scalars(select(CatalogoIdioma).where(CatalogoIdioma.activo.is_(True))):
            frases = [x.texto for x in c.sinonimos] or [c.nombre]
            idi.append((c.nombre, frases))
        if not hab or not idi:
            from observatorio.pipeline.habilidades import HABILIDADES_BLANDAS, IDIOMAS

            if not hab:
                hab = [(k, v) for k, v in HABILIDADES_BLANDAS.items()]
            if not idi:
                idi = [(k, [p]) for k, p in IDIOMAS.items()]
        return cls(habilidades=hab, idiomas=idi)

    def detectar_blandas(self, texto: str) -> list[HabilidadDetectada]:
        t = plegar(texto or "")
        halladas: dict[str, HabilidadDetectada] = {}
        for nombre, frase in self._hab:
            if re.search(rf"\b{re.escape(frase)}\b", t):
                halladas.setdefault(nombre, HabilidadDetectada(habilidad=nombre, texto=frase))
        return list(halladas.values())

    def detectar_idiomas(self, texto: str) -> list[IdiomaDetectado]:
        t = plegar(texto or "")
        resultado: dict[str, IdiomaDetectado] = {}
        for idioma, frases in self._idi:
            for frase in frases:
                rx = frase if "|" in frase else re.escape(frase)
                for m in re.finditer(rf"\b(?:{rx})\b", t):
                    n = _NIVEL_RX.search(t[m.end(): m.end() + 35]) or _NIVEL_RX.search(
                        t[max(0, m.start() - 30): m.start()]
                    )
                    nivel = ""
                    if n:
                        v = n.group(1).strip()
                        nivel = (
                            v.upper()
                            if re.match(r"^[abc][12]\+?$", v, re.I)
                            else _NIVEL_LEGIBLE.get(re.sub(r"\s+", " ", v), v)
                        )
                    if "bilingue" in m.group(0) or "bilingual" in m.group(0):
                        nivel = nivel or "bilingüe"
                    previo = resultado.get(idioma)
                    if previo is None or (not previo.nivel and nivel):
                        resultado[idioma] = IdiomaDetectado(idioma=idioma, nivel=nivel or None, texto=m.group(0))
        return list(resultado.values())

    def texto_idiomas(self, items: list[IdiomaDetectado]) -> str:
        return "; ".join(f"{x.idioma} {x.nivel}".strip() for x in items)

    def texto_blandas(self, items: list[HabilidadDetectada]) -> str:
        return "; ".join(x.habilidad for x in items)