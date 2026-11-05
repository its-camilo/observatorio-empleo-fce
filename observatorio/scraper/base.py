"""Estructura común de una oferta cruda y de una consulta (partición)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable


@dataclass
class Consulta:
    fuente: str
    termino: str
    ubicacion: str  # como se escribe en la fuente
    nombre_ubicacion: str = ""
    carrera: str | None = None
    remoto: bool = False
    max_resultados: int = 100
    ventana_dias: int = 30
    opciones: dict = field(default_factory=dict)


@dataclass
class OfertaCrudaDatos:
    """Lo que entrega cada fuente, antes de limpiar. Sin correos ni salarios."""

    fuente: str  # LinkedIn, Indeed, Google Jobs, Computrabajo
    id_fuente: str
    url: str
    cargo: str
    empresa: str = ""
    ubicacion: str = ""
    fecha_publicacion: str = ""  # ISO o texto relativo
    descripcion: str = ""
    sector: str = ""
    nivel_fuente: str = ""
    tipo_empleo: str = ""
    remoto: bool | None = None

    def a_dict(self) -> dict:
        return asdict(self)


# Firma de un extractor: recibe una consulta y un callback "ya_existe(id_fuente)"
# para no pedir detalles de ofertas que ya tenemos; devuelve ofertas crudas.
Extractor = Callable[[Consulta, Callable[[str], bool]], Iterable[OfertaCrudaDatos]]
