"""Detección de softwares por catálogo + sinónimos (RF-05).

Reglas:
- Coincidencia por palabra completa (no dentro de otra palabra): "java" no
  coincide dentro de "javascript", "sql" no coincide dentro de "mysql".
- Sin distinguir mayúsculas ni tildes, salvo sinónimos marcados como
  `sensible_mayusculas` (p. ej. "R", "SAS", "Word", "Alegra").
- Los sinónimos con `requiere_contexto` solo cuentan si cerca (±120
  caracteres) aparece alguna palabra de contexto del catálogo.
- `patron_exclusion` (regex) anula una coincidencia si la ventana alrededor
  la cumple (p. ej. "S.A.S", "R&D", "excel in").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from observatorio.texto import plegar

VENTANA_CONTEXTO = 120
_BORDE_IZQ = r"(?<![A-Za-z0-9_ñÑ])"
_BORDE_DER = r"(?![A-Za-z0-9_ñÑ])"


@dataclass
class SinonimoDef:
    texto: str
    sensible_mayusculas: bool = False
    requiere_contexto: bool = False
    patron_exclusion: str | None = None


@dataclass
class SoftwareDef:
    software: str
    grupo: str
    sinonimos: list[SinonimoDef]
    contexto: list[str] = field(default_factory=list)
    activo: bool = True


@dataclass(frozen=True)
class Deteccion:
    software: str
    grupo: str
    texto_encontrado: str


def _patron(texto: str, sensible: bool) -> re.Pattern:
    base = texto if sensible else plegar(texto)
    partes = [re.escape(p) for p in base.split()]
    cuerpo = r"[\s\-_]*".join(partes) if len(partes) > 1 else partes[0]
    # Para "power bi" también aceptar "powerbi" / "power-bi"
    return re.compile(_BORDE_IZQ + cuerpo + _BORDE_DER)


@dataclass
class _Compilado:
    software: SoftwareDef
    sin: SinonimoDef
    regex: re.Pattern
    exclusion: re.Pattern | None


class DetectorSoftware:
    def __init__(self, catalogo: list[SoftwareDef]):
        self.catalogo = [c for c in catalogo if c.activo]
        self._compilados: list[_Compilado] = []
        for sw in self.catalogo:
            # sinónimos más largos primero: el texto encontrado será el más específico
            for sin in sorted(sw.sinonimos, key=lambda x: -len(x.texto)):
                if not sin.texto.strip():
                    continue
                excl = None
                if sin.patron_exclusion:
                    try:
                        excl = re.compile(sin.patron_exclusion)
                    except re.error:
                        excl = None
                self._compilados.append(_Compilado(sw, sin, _patron(sin.texto.strip(), sin.sensible_mayusculas), excl))
        self._contexto = {sw.software: [plegar(w.strip()) for w in sw.contexto if w.strip()] for sw in self.catalogo}

    # ------------------------------------------------------------------
    @classmethod
    def desde_bd(cls, s) -> "DetectorSoftware":
        from observatorio.db.modelos import Catalogo

        defs = []
        for c in s.query(Catalogo).all():
            defs.append(SoftwareDef(
                software=c.software, grupo=c.grupo, activo=c.activo,
                contexto=[w for w in (c.contexto or "").split(",")],
                sinonimos=[SinonimoDef(x.texto, x.sensible_mayusculas, x.requiere_contexto, x.patron_exclusion)
                           for x in c.sinonimos] or [SinonimoDef(c.software)],
            ))
        return cls(defs)

    # ------------------------------------------------------------------
    def _hay_contexto(self, software: str, plegado: str, ini: int, fin: int) -> bool:
        palabras = self._contexto.get(software) or []
        if not palabras:
            return False
        ventana = plegado[max(0, ini - VENTANA_CONTEXTO): fin + VENTANA_CONTEXTO]
        # Quitar la propia coincidencia para que "R" no sea contexto de sí misma
        ventana = ventana.replace(plegado[ini:fin], " ", 1)
        for w in palabras:
            # Borde izquierdo siempre ("econometr" coincide con "econometría");
            # palabras cortas exigen también borde derecho ("sas" no está en "casas").
            patron = _BORDE_IZQ + re.escape(w) + (_BORDE_DER if len(w) <= 4 else "")
            if re.search(patron, ventana):
                return True
        return False

    def detectar(self, titulo: str, descripcion: str = "", empresa: str = "") -> list[Deteccion]:
        original = f"{titulo or ''}\n{descripcion or ''}"
        # El nombre de la empresa no cuenta como software pedido (p. ej. "Siigo S.A.S.")
        if empresa and len(empresa.strip()) > 3:
            original = re.sub(re.escape(empresa.strip()), lambda m: " " * len(m.group(0)), original, flags=re.I)
        plegado = plegar(original)
        encontrados: dict[str, Deteccion] = {}
        for comp in self._compilados:
            sw = comp.software
            if sw.software in encontrados:
                continue
            objetivo = original if comp.sin.sensible_mayusculas else plegado
            for m in comp.regex.finditer(objetivo):
                ini, fin = m.span()
                if comp.exclusion is not None:
                    ventana = original[max(0, ini - 12): fin + 12]
                    if comp.exclusion.search(ventana):
                        continue
                if comp.sin.requiere_contexto and not self._hay_contexto(sw.software, plegado, ini, fin):
                    continue
                encontrados[sw.software] = Deteccion(sw.software, sw.grupo, original[ini:fin].strip())
                break
        return sorted(encontrados.values(), key=lambda d: d.software.lower())

    def coincide_algun_sinonimo(self, termino: str) -> bool:
        """True si el término ya está cubierto por el catálogo (para RF-17)."""
        t = plegar(termino)
        for comp in self._compilados:
            if comp.regex.search(t if not comp.sin.sensible_mayusculas else termino):
                return True
        return False
