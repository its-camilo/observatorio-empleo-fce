"""Capitales departamentales de Colombia (33: 32 departamentos + Bogotá D.C.).

Solo estas ciudades deben conservarse cuando `solo_capitales_departamento` está activo.
"""
from __future__ import annotations

import re

from observatorio.texto import CIUDADES, limpiar_espacios, normalizar_ciudad, normalizar_clave, plegar

# Nombres canónicos guardados en `ofertas.ciudad` (con tildes como en el observatorio).
CAPITALES_DEPARTAMENTALES: tuple[str, ...] = (
    "Bogotá",
    "Medellín",
    "Cali",
    "Barranquilla",
    "Cartagena",
    "Bucaramanga",
    "Cúcuta",
    "Pereira",
    "Manizales",
    "Armenia",
    "Ibagué",
    "Neiva",
    "Villavicencio",
    "Santa Marta",
    "Montería",
    "Valledupar",
    "Pasto",
    "Popayán",
    "Tunja",
    "Riohacha",
    "Sincelejo",
    "Quibdó",
    "Florencia",
    "Yopal",
    "Arauca",
    "Mocoa",
    "San José del Guaviare",
    "Inírida",
    "Puerto Carreño",
    "Mitú",
    "Leticia",
    "San Andrés",
)

_CAPITAL_SET = frozenset(CAPITALES_DEPARTAMENTALES)

# Municipios conocidos en el normalizador que NO son capital (metrópolis).
_MUNICIPIOS_NO_CAPITAL = frozenset(
    {
        "Envigado",
        "Itagüí",
        "Sabaneta",
        "Bello",
        "Rionegro",
        "Chía",
        "Soacha",
        "Mosquera",
        "Funza",
        "Cota",
        "Tocancipá",
        "Zipaquirá",
        "Facatativá",
        "Madrid (Cundinamarca)",
        "Yumbo",
        "Palmira",
        "Floridablanca",
        "Soledad",
        "Malambo",
        "Girardot",
        "Sogamoso",
        "Duitama",
    }
)

# Solo nombre de departamento (sin capital explícita) — no se asume capital.
_SOLO_DEPARTAMENTO = frozenset(
    {
        "Cundinamarca",
        "Antioquia",
        "Valle del Cauca",
        "Atlántico",
        "Santander",
        "Bolívar",
        "Colombia",
    }
)

_ALIAS_EXTRA: dict[str, str] = {
    "bogota d c": "Bogotá",
    "distrito capital": "Bogotá",
    "capital district": "Bogotá",
    "santafe de bogota": "Bogotá",
    "santa fe de bogota": "Bogotá",
    "cartagena de indias": "Cartagena",
    "santiago de cali": "Cali",
    "san jose del guaviare": "San José del Guaviare",
    "puerto carreno": "Puerto Carreño",
    "san andres": "San Andrés",
    "san andres y providencia": "San Andrés",
    "inirida": "Inírida",
    "mitu": "Mitú",
    "popayan": "Popayán",
    "monteria": "Montería",
    "cucuta": "Cúcuta",
    "ibague": "Ibagué",
    "neiva": "Neiva",
    "tunja": "Tunja",
    "riohacha": "Riohacha",
    "quibdo": "Quibdó",
    "florencia": "Florencia",
    "yopal": "Yopal",
    "arauca": "Arauca",
    "mocoa": "Mocoa",
    "leticia": "Leticia",
    "villavicencio": "Villavicencio",
    "santa marta": "Santa Marta",
    "valledupar": "Valledupar",
    "sincelejo": "Sincelejo",
    "pasto": "Pasto",
    "manizales": "Manizales",
    "armenia": "Armenia",
    "pereira": "Pereira",
    "barranquilla": "Barranquilla",
    "bucaramanga": "Bucaramanga",
    "medellin": "Medellín",
    "bogota": "Bogotá",
}


def _resolver_clave(clave: str) -> str | None:
    k = normalizar_clave(clave)
    if not k:
        return None
    if k in _ALIAS_EXTRA:
        return _ALIAS_EXTRA[k]
    if k in CIUDADES:
        canon = CIUDADES[k]
        if canon in _CAPITAL_SET:
            return canon
        if canon == "Bogotá":
            return "Bogotá"
        return None
    for alias, canon in _ALIAS_EXTRA.items():
        if alias in k or re.search(rf"\b{re.escape(alias)}\b", k):
            return canon
    for alias, canon in CIUDADES.items():
        if canon in _CAPITAL_SET and re.search(rf"\b{re.escape(alias)}\b", k):
            return canon
    return None


def capital_desde_texto(ubicacion: str | None) -> str | None:
    """Si el texto de ubicación corresponde a una capital departamental, devuelve el nombre canónico."""
    if not limpiar_espacios(ubicacion or ""):
        return None
    t = normalizar_clave((ubicacion or "").replace(".", ""))
    if re.search(r"\b(remoto|remote|teletrabajo|hibrid)\b", t):
        return "Remoto"
    directo = _resolver_clave(t)
    if directo:
        return directo
    norm = normalizar_ciudad(ubicacion)
    if norm in _CAPITAL_SET:
        return norm
    if norm == "Bogotá":
        return "Bogotá"
    if norm == "Remoto":
        return "Remoto"
    return _resolver_clave(plegar(ubicacion or ""))


def es_capital_departamental(ciudad: str | None, ubicacion_original: str | None = None) -> bool:
    """True si la oferta está asociada a una capital departamental (o remoto nacional desde búsqueda por capital).

    Reglas:
    - Ciudad canónica en las 33 capitales → sí.
    - Localidades de Bogotá normalizadas a «Bogotá» → sí.
    - «Remoto» → sí (oferta sin sede municipal, recolectada en consultas por capital).
    - Municipio conocido no capital (Envigado, Chía, …) → no.
    - Solo «Colombia», vacío o nombre de departamento sin capital → no (ubicación insuficiente).
    """
    c = limpiar_espacios(ciudad or "")
    if c in _CAPITAL_SET:
        return True
    if c == "Remoto":
        return True
    if c in _MUNICIPIOS_NO_CAPITAL:
        return False
    if c in _SOLO_DEPARTAMENTO:
        return False
    if c and c not in _CAPITAL_SET and c != "Remoto":
        return False
    if ubicacion_original:
        cap = capital_desde_texto(ubicacion_original)
        if cap in _CAPITAL_SET or cap == "Remoto":
            return True
        norm = normalizar_ciudad(ubicacion_original)
        if norm in _CAPITAL_SET or norm == "Remoto":
            return True
        if norm in _MUNICIPIOS_NO_CAPITAL or norm in _SOLO_DEPARTAMENTO:
            return False
    return False


def ubicaciones_capitales_defecto() -> list[dict]:
    """Ubicaciones para scraping: las 33 capitales (sin «Remoto Colombia»)."""
    filas: list[dict] = [
        {"nombre": "Bogotá", "linkedin": "Bogotá, Colombia", "indeed": "Bogotá", "computrabajo": "bogota-dc"},
        {"nombre": "Medellín", "linkedin": "Medellín, Antioquia, Colombia", "indeed": "Medellín", "computrabajo": "antioquia"},
        {"nombre": "Cali", "linkedin": "Cali, Valle del Cauca, Colombia", "indeed": "Cali", "computrabajo": "valle-del-cauca"},
        {"nombre": "Barranquilla", "linkedin": "Barranquilla, Atlántico, Colombia", "indeed": "Barranquilla", "computrabajo": "atlantico"},
        {"nombre": "Cartagena", "linkedin": "Cartagena, Bolívar, Colombia", "indeed": "Cartagena", "computrabajo": "bolivar"},
        {"nombre": "Bucaramanga", "linkedin": "Bucaramanga, Santander, Colombia", "indeed": "Bucaramanga", "computrabajo": "santander"},
        {"nombre": "Cúcuta", "linkedin": "Cúcuta, Norte de Santander, Colombia", "indeed": "Cúcuta", "computrabajo": "norte-de-santander"},
        {"nombre": "Pereira", "linkedin": "Pereira, Risaralda, Colombia", "indeed": "Pereira", "computrabajo": "risaralda"},
        {"nombre": "Manizales", "linkedin": "Manizales, Caldas, Colombia", "indeed": "Manizales", "computrabajo": "caldas"},
        {"nombre": "Armenia", "linkedin": "Armenia, Quindío, Colombia", "indeed": "Armenia", "computrabajo": "quindio"},
        {"nombre": "Ibagué", "linkedin": "Ibagué, Tolima, Colombia", "indeed": "Ibagué", "computrabajo": "tolima"},
        {"nombre": "Neiva", "linkedin": "Neiva, Huila, Colombia", "indeed": "Neiva", "computrabajo": "huila"},
        {"nombre": "Villavicencio", "linkedin": "Villavicencio, Meta, Colombia", "indeed": "Villavicencio", "computrabajo": "meta"},
        {"nombre": "Santa Marta", "linkedin": "Santa Marta, Magdalena, Colombia", "indeed": "Santa Marta", "computrabajo": "magdalena"},
        {"nombre": "Montería", "linkedin": "Montería, Córdoba, Colombia", "indeed": "Montería", "computrabajo": "cordoba"},
        {"nombre": "Valledupar", "linkedin": "Valledupar, Cesar, Colombia", "indeed": "Valledupar", "computrabajo": "cesar"},
        {"nombre": "Pasto", "linkedin": "Pasto, Nariño, Colombia", "indeed": "Pasto", "computrabajo": "narino"},
        {"nombre": "Popayán", "linkedin": "Popayán, Cauca, Colombia", "indeed": "Popayán", "computrabajo": "cauca"},
        {"nombre": "Tunja", "linkedin": "Tunja, Boyacá, Colombia", "indeed": "Tunja", "computrabajo": "boyaca"},
        {"nombre": "Riohacha", "linkedin": "Riohacha, La Guajira, Colombia", "indeed": "Riohacha", "computrabajo": "la-guajira"},
        {"nombre": "Sincelejo", "linkedin": "Sincelejo, Sucre, Colombia", "indeed": "Sincelejo", "computrabajo": "sucre"},
        {"nombre": "Quibdó", "linkedin": "Quibdó, Chocó, Colombia", "indeed": "Quibdó", "computrabajo": "choco"},
        {"nombre": "Florencia", "linkedin": "Florencia, Caquetá, Colombia", "indeed": "Florencia", "computrabajo": "caqueta"},
        {"nombre": "Yopal", "linkedin": "Yopal, Casanare, Colombia", "indeed": "Yopal", "computrabajo": "casanare"},
        {"nombre": "Arauca", "linkedin": "Arauca, Arauca, Colombia", "indeed": "Arauca", "computrabajo": "arauca"},
        {"nombre": "Mocoa", "linkedin": "Mocoa, Putumayo, Colombia", "indeed": "Mocoa", "computrabajo": "putumayo"},
        {
            "nombre": "San José del Guaviare",
            "linkedin": "San José del Guaviare, Guaviare, Colombia",
            "indeed": "San José del Guaviare",
            "computrabajo": "guaviare",
        },
        {"nombre": "Inírida", "linkedin": "Inírida, Guainía, Colombia", "indeed": "Inírida", "computrabajo": "guainia"},
        {"nombre": "Puerto Carreño", "linkedin": "Puerto Carreño, Vichada, Colombia", "indeed": "Puerto Carreño", "computrabajo": "vichada"},
        {"nombre": "Mitú", "linkedin": "Mitú, Vaupés, Colombia", "indeed": "Mitú", "computrabajo": "vaupes"},
        {"nombre": "Leticia", "linkedin": "Leticia, Amazonas, Colombia", "indeed": "Leticia", "computrabajo": "amazonas"},
        {"nombre": "San Andrés", "linkedin": "San Andrés, Colombia", "indeed": "San Andrés", "computrabajo": "san-andres"},
    ]
    assert len(filas) == len(CAPITALES_DEPARTAMENTALES)
    return filas


def filtrar_ubicaciones_config(ubicaciones: list[dict], *, solo_capitales: bool) -> list[dict]:
    if not solo_capitales:
        return ubicaciones
    permitidos = {u["nombre"] for u in ubicaciones_capitales_defecto()}
    salida = [u for u in ubicaciones if u.get("nombre") in permitidos and not u.get("remoto")]
    return salida or ubicaciones_capitales_defecto()
