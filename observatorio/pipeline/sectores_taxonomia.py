"""Taxonomía canónica de sectores industriales (≤100 etiquetas en español)."""
from __future__ import annotations

import re
from functools import lru_cache

from observatorio.texto import limpiar_espacios, plegar

# Etiquetas permitidas tras normalización (conteo ≤ 100)
SECTORES_CANONICOS: tuple[str, ...] = (
    "Administración pública",
    "Agricultura y agroindustria",
    "Alquiler de bienes y equipos",
    "Arquitectura y planificación",
    "Aviación y aeronáutica",
    "Banca",
    "Bienes de consumo",
    "Bienes inmuebles",
    "Casinos y juegos de azar",
    "Comercio al por mayor",
    "Comercio al por mayor de materiales de construcción",
    "Comercio al por menor",
    "Construcción",
    "Consultoría de externalización y deslocalización",
    "Consultoría y servicios a empresas",
    "Contabilidad",
    "Desarrollo de software",
    "Desarrollo y comercio internacional",
    "Educación básica y secundaria",
    "Educación superior",
    "Energía eléctrica y servicios públicos",
    "Energías renovables",
    "Entretenimiento y ocio",
    "Fabricación de alimentos y bebidas",
    "Fabricación de electrodomésticos y electrónica",
    "Fabricación de equipo médico",
    "Fabricación de maquinaria industrial",
    "Fabricación de productos de cuidado personal",
    "Fabricación de productos de plástico y envases",
    "Fabricación de productos farmacéuticos",
    "Fabricación de productos químicos",
    "Fabricación de vehículos y automotriz",
    "Gestión de inversiones y capital privado",
    "Gestión educativa y formación profesional",
    "Hostelería y restauración",
    "Hospitales y atención sanitaria",
    "Importación y exportación",
    "Industria manufacturera",
    "Industria textil y moda",
    "Ingeniería civil",
    "Inteligencia artificial y robótica",
    "Investigación biotecnológica",
    "Investigación de mercado",
    "Medios y publicaciones en línea",
    "Oficinas ejecutivas y holdings",
    "Organización de viajes",
    "Organizaciones sin ánimo de lucro",
    "Otros sectores",
    "Petróleo, gas y minería",
    "Salud pública y servicios sociales",
    "Seguridad de redes y sistemas informáticos",
    "Seguridad física e investigación",
    "Seguros",
    "Servicios al consumidor",
    "Servicios de alimentos y bebidas",
    "Servicios de diseño",
    "Servicios de información y datos",
    "Servicios de ingeniería",
    "Servicios de publicidad y marketing",
    "Servicios de recursos humanos y selección de personal",
    "Servicios financieros",
    "Servicios jurídicos",
    "Servicios medioambientales",
    "Servicios profesionales",
    "Servicios públicos y servicios de instalaciones",
    "Servicios médicos y consultorios",
    "Servicios veterinarios",
    "Servicios y consultoría de TI",
    "Tecnología, información e internet",
    "Tecnología, información y medios de comunicación",
    "Telecomunicaciones",
    "Transporte, logística y almacenamiento",
)

_CANONICO_POR_CLAVE: dict[str, str] = {plegar(c): c for c in SECTORES_CANONICOS}

# Coincidencia exacta tras plegar (variantes inglés / LinkedIn ya traducidas parcialmente)
_ALIASES_EXACTOS: dict[str, str] = {
    plegar("Consulting And Business Services"): "Consultoría y servicios a empresas",
    plegar("Consumer Goods And Services"): "Bienes de consumo",
    plegar("Food And Beverages"): "Servicios de alimentos y bebidas",
    plegar("Construction"): "Construcción",
    plegar("Industrial Manufacturing"): "Industria manufacturera",
    plegar("Organization"): "Otros sectores",
    plegar("Internet And Software"): "Tecnología, información e internet",
    plegar("Computers And Electronics"): "Fabricación de electrodomésticos y electrónica",
    plegar("Energy And Utilities"): "Energía eléctrica y servicios públicos",
    plegar("Education And Schools"): "Educación básica y secundaria",
    plegar("Health Care"): "Hospitales y atención sanitaria",
    plegar("Insurance"): "Seguros",
    plegar("Pharmaceuticals"): "Fabricación de productos farmacéuticos",
    plegar("Retail"): "Comercio al por menor",
    plegar("Media News And Publishing"): "Medios y publicaciones en línea",
    plegar("Restaurants Travel And Leisure"): "Hostelería y restauración",
    plegar("Aerospace And Defense"): "Aviación y aeronáutica",
    plegar("Banks And Financial Services"): "Servicios financieros",
    plegar("Subcontrataciones/Offshoring"): "Consultoría de externalización y deslocalización",
    plegar("Dotación y selección de personal"): "Servicios de recursos humanos y selección de personal",
    plegar("Sector automovilístico"): "Fabricación de vehículos y automotriz",
    plegar("Fabricación de vehículos de motor"): "Fabricación de vehículos y automotriz",
    plegar("Fabricación"): "Industria manufacturera",
    plegar("Comercio minorista"): "Comercio al por menor",
    plegar("Comercio al por mayor de materiales de construcción"): "Comercio al por mayor de materiales de construcción",
    plegar("Transporte, logística, cadena de suministro y almacenamiento"): "Transporte, logística y almacenamiento",
    plegar("Tecnología, información y medios de comunicación"): "Tecnología, información y medios de comunicación",
    plegar("Servicios de publicidad"): "Servicios de publicidad y marketing",
    plegar("Servicios de marketing"): "Servicios de publicidad y marketing",
    plegar("Servicios y tecnologías de la información"): "Tecnología, información e internet",
    plegar("Servicios de recursos humanos"): "Servicios de recursos humanos y selección de personal",
    plegar("Consultoría y servicios a empresas"): "Consultoría y servicios a empresas",
    plegar("Consultoría de externalización y deslocalización"): "Consultoría de externalización y deslocalización",
    plegar("Gestión educativa"): "Gestión educativa y formación profesional",
    plegar("Educación"): "Gestión educativa y formación profesional",
    plegar("Enseñanza superior"): "Educación superior",
    plegar("Educación primaria y secundaria"): "Educación básica y secundaria",
    plegar("Hostelería"): "Hostelería y restauración",
    plegar("Restauración"): "Hostelería y restauración",
    plegar("Hoteles y moteles"): "Hostelería y restauración",
    plegar("Artículos de consumo"): "Bienes de consumo",
    plegar("Servicios para el individuo y la familia"): "Servicios al consumidor",
    plegar("Servicios al consumidor"): "Servicios al consumidor",
    plegar("Servicios financieros"): "Servicios financieros",
    plegar("Entretenimiento"): "Entretenimiento y ocio",
    plegar("Proveedores de entretenimiento"): "Entretenimiento y ocio",
    plegar("Espectáculos deportivos"): "Entretenimiento y ocio",
    plegar("Salud y servicios sociales"): "Salud pública y servicios sociales",
    plegar("Salud pública"): "Salud pública y servicios sociales",
    plegar("Consultorios médicos"): "Servicios médicos y consultorios",
    plegar("Servicios médicos"): "Servicios médicos y consultorios",
    plegar("Despachos de abogados"): "Servicios jurídicos",
    plegar("Desarrollo de software personalizado de sistemas de TI"): "Desarrollo de software",
    plegar("Servicios de información"): "Servicios de información y datos",
    plegar("Publicaciones en línea"): "Medios y publicaciones en línea",
    plegar("Plataformas de comercio en internet"): "Comercio al por menor",
    plegar("Importación y exportación al por mayor"): "Importación y exportación",
    plegar("Gestión de inversiones"): "Gestión de inversiones y capital privado",
    plegar("Entidades de capital riesgo y capital privado"): "Gestión de inversiones y capital privado",
    plegar("Banca de inversión"): "Gestión de inversiones y capital privado",
    plegar("Fondos de pensiones"): "Servicios financieros",
    plegar("Oficinas ejecutivas"): "Oficinas ejecutivas y holdings",
    plegar("Sociedades holding"): "Oficinas ejecutivas y holdings",
    plegar("Asuntos exteriores"): "Administración pública",
    plegar("Oficinas de política pública"): "Administración pública",
    plegar("Cosmética"): "Fabricación de productos de cuidado personal",
    plegar("Inteligencia Artificial"): "Inteligencia artificial y robótica",
    plegar("Ingeniería robótica"): "Inteligencia artificial y robótica",
    plegar("Inteligencia artificial y robótica"): "Inteligencia artificial y robótica",
    plegar("Minería"): "Petróleo, gas y minería",
    plegar("Petróleo y gas"): "Petróleo, gas y minería",
    plegar("Agricultura"): "Agricultura y agroindustria",
    plegar("Alimentación y bebidas"): "Servicios de alimentos y bebidas",
    plegar("Materiales de construcción"): "Comercio al por mayor de materiales de construcción",
    plegar("Bienes inmuebles"): "Bienes inmuebles",
    plegar("Alquiler de bienes inmuebles residenciales"): "Bienes inmuebles",
    plegar("Servicios públicos"): "Servicios públicos y servicios de instalaciones",
    plegar("Servicios de instalaciones"): "Servicios públicos y servicios de instalaciones",
    plegar("Generación de energía eléctrica"): "Energía eléctrica y servicios públicos",
    plegar("Generación de energía renovable"): "Energías renovables",
    plegar("Servicios para energías renovables"): "Energías renovables",
    plegar("Tecnología energética"): "Energías renovables",
    plegar("Programas de conservación medioambiental"): "Servicios medioambientales",
    plegar("Servicios medioambientales"): "Servicios medioambientales",
    plegar("Transporte de mercancías y paquetes"): "Transporte, logística y almacenamiento",
    plegar("Transporte terrestre en camión"): "Transporte, logística y almacenamiento",
    plegar("Transporte terrestre de pasajeros"): "Transporte, logística y almacenamiento",
    plegar("Transporte marítimo"): "Transporte, logística y almacenamiento",
    plegar("Centros de atención telefónica"): "Servicios profesionales",
    plegar("Productos de redes informáticos"): "Seguridad de redes y sistemas informáticos",
    plegar("Servicios de consultoría y asesoramiento"): "Consultoría y servicios a empresas",
    plegar("Servicios y consultoría en TI"): "Servicios y consultoría de TI",
    plegar("Selección de personal y reclutamiento"): "Servicios de recursos humanos y selección de personal",
    plegar("Externalización y consultoría de offshoring"): "Consultoría de externalización y deslocalización",
    plegar("Aseguradoras"): "Seguros",
    plegar("Intermediarios financieros"): "Servicios financieros",
    plegar("Farmacias minoristas"): "Comercio al por menor",
}

_RE_FRAG = re.compile(r"\s*,\s*|\s+y\s+", re.I)


def _fragmentos(valor: str) -> list[str]:
    trozos = _RE_FRAG.split(valor)
    return [limpiar_espacios(t) for t in trozos if limpiar_espacios(t)]


def _regla_por_clave(clave: str) -> str | None:
    if clave in _CANONICO_POR_CLAVE:
        return _CANONICO_POR_CLAVE[clave]
    if clave in _ALIASES_EXACTOS:
        return _ALIASES_EXACTOS[clave]

  # Seguridad informática antes que “seguros/seguridad física”
    if "seguridad de redes" in clave or "sistemas informaticos" in clave or "ciber" in clave:
        return "Seguridad de redes y sistemas informáticos"
    if "seguridad e investigacion" in clave or clave.startswith("seguridad "):
        return "Seguridad física e investigación"

    if clave.startswith("banca"):
        return "Banca"
    if "banca" in clave and "inversion" in clave:
        return "Gestión de inversiones y capital privado"
    if clave == "banca" or (clave.startswith("banca ") and "seguro" not in clave):
        return "Banca"
    if "seguro" in clave or "asegur" in clave or "reclamacion" in clave:
        return "Seguros"
    if "contab" in clave:
        return "Contabilidad"
    if "financier" in clave or "fondo de pension" in clave:
        return "Servicios financieros"

    if "desarrollo de software" in clave or clave == "software development":
        return "Desarrollo de software"
    if "consultoria de ti" in clave or "it services" in clave or "consultoria ti" in clave:
        return "Servicios y consultoría de TI"
    if "tecnologia informacion" in clave and "internet" in clave:
        return "Tecnología, información e internet"
    if "tecnologia" in clave and ("medio" in clave or "comunicacion" in clave):
        return "Tecnología, información y medios de comunicación"
    if "telecomunicacion" in clave or "inalambric" in clave:
        return "Telecomunicaciones"
    if "inteligencia artificial" in clave or "robotica" in clave:
        return "Inteligencia artificial y robótica"
    if "prueba y evaluacion de sistemas" in clave or "operaciones y mantenimiento de sistemas" in clave:
        return "Servicios y consultoría de TI"
    if "formacion y soporte de sistemas" in clave or "datos de sistemas" in clave:
        return "Servicios y consultoría de TI"
    if "plataformas de inteligencia empresarial" in clave or "infraestructura y analisis de datos" in clave:
        return "Servicios de información y datos"
    if "datos y analisis climaticos" in clave:
        return "Servicios de información y datos"

    if "externalizacion" in clave or "offshor" in clave or "deslocalizacion" in clave:
        return "Consultoría de externalización y deslocalización"
    if "consultoria" in clave and "empresa" in clave:
        return "Consultoría y servicios a empresas"
    if "consultoria" in clave:
        return "Consultoría y servicios a empresas"
    if "recursos humanos" in clave or "dotacion" in clave or "seleccion de personal" in clave or "staffing" in clave:
        return "Servicios de recursos humanos y selección de personal"
    if "publicidad" in clave or "marketing" in clave or "relaciones publicas" in clave:
        return "Servicios de publicidad y marketing"
    if "investigacion de mercado" in clave:
        return "Investigación de mercado"
    if "servicios profesionales" in clave:
        return "Servicios profesionales"
    if "servicios de informacion" in clave or "medios de audio" in clave:
        return "Servicios de información y datos"

    if "comercio al por menor" in clave or clave == "retail":
        return "Comercio al por menor"
    if "comercio al por mayor" in clave:
        if "construccion" in clave or "materiales de construccion" in clave:
            return "Comercio al por mayor de materiales de construcción"
        return "Comercio al por mayor"
    if "importacion" in clave or "exportacion" in clave or "comercio internacional" in clave:
        return "Importación y exportación"

    if "farmac" in clave or "biotecnolog" in clave:
        if "investigacion biotecnolog" in clave or "biotecnolog" in clave:
            return "Investigación biotecnológica"
        return "Fabricación de productos farmacéuticos"
    if "aliment" in clave or "bebida" in clave:
        if "fabricacion" in clave:
            return "Fabricación de alimentos y bebidas"
        return "Servicios de alimentos y bebidas"
    if "quimic" in clave:
        return "Fabricación de productos químicos"
    if "vehiculo" in clave or "automov" in clave or "automotriz" in clave:
        return "Fabricación de vehículos y automotriz"
    if "maquinaria" in clave or "automatizacion" in clave:
        return "Fabricación de maquinaria industrial"
    if "electrodomestic" in clave or "electron" in clave or "semiconductor" in clave or "comunicaciones" in clave:
        return "Fabricación de electrodomésticos y electrónica"
    if "plastico" in clave or "envase" in clave or "embalaje" in clave:
        return "Fabricación de productos de plástico y envases"
    if "equipo medico" in clave or "medico" in clave and "fabricacion" in clave:
        return "Fabricación de equipo médico"
    if "cuidado personal" in clave or "cosmet" in clave:
        return "Fabricación de productos de cuidado personal"
    if "textil" in clave or "moda" in clave or "prendas" in clave:
        return "Industria textil y moda"
    if "fabricacion" in clave or "manufactur" in clave:
        return "Industria manufacturera"

    if "ingenieria civil" in clave:
        return "Ingeniería civil"
    if "construccion" in clave or "obras publicas" in clave:
        return "Construcción"
    if "arquitectura" in clave or "planificacion" in clave:
        return "Arquitectura y planificación"
    if "inmobili" in clave or "alquiler de bienes inmuebles" in clave:
        return "Bienes inmuebles"

    if "hospital" in clave or "sanitar" in clave or "health care" in clave:
        return "Hospitales y atención sanitaria"
    if "salud mental" in clave or "medicina alternativa" in clave or "bienestar" in clave:
        return "Hospitales y atención sanitaria"
    if "salud" in clave or "veterinar" in clave:
        if "veterinar" in clave:
            return "Servicios veterinarios"
        return "Salud pública y servicios sociales"
    if "veterinar" in clave:
        return "Servicios veterinarios"

    if "ensenanza superior" in clave or "universidad" in clave:
        return "Educación superior"
    if "primaria" in clave or "secundaria" in clave or "school" in clave:
        return "Educación básica y secundaria"
    if "educacion" in clave or "e-learning" in clave or "coaching" in clave:
        return "Gestión educativa y formación profesional"

    if "petroleo" in clave or "gas" in clave and "mineria" in clave:
        return "Petróleo, gas y minería"
    if "petroleo" in clave or "mineria" in clave:
        return "Petróleo, gas y minería"
    if "energia electrica" in clave or "utilities" in clave:
        return "Energía eléctrica y servicios públicos"
    if "energia renovable" in clave or "energias renovables" in clave:
        return "Energías renovables"
    if "medioambient" in clave or "conservacion" in clave:
        return "Servicios medioambientales"

    if "transporte" in clave or "logistica" in clave or "almacen" in clave or "cadena de suministro" in clave:
        return "Transporte, logística y almacenamiento"
    if "aero" in clave or "aviacion" in clave or "aerospace" in clave or "defensa" in clave and "espacio" in clave:
        return "Aviación y aeronáutica"

    if "agricult" in clave or "agrari" in clave:
        return "Agricultura y agroindustria"

    if "hosteler" in clave or "hotel" in clave or "restaur" in clave or "motel" in clave:
        return "Hostelería y restauración"
    if "casino" in clave or "apuesta" in clave:
        return "Casinos y juegos de azar"
    if "entreten" in clave or "deport" in clave and "espectac" in clave:
        return "Entretenimiento y ocio"
    if "consumidor" in clave or "consumer" in clave:
        return "Servicios al consumidor"
    if "bienes de consumo" in clave or "consumer goods" in clave:
        return "Bienes de consumo"

    if "juridic" in clave or "abogad" in clave or "legal" in clave:
        return "Servicios jurídicos"
    if "ingenieria" in clave:
        return "Servicios de ingeniería"
    if "diseno" in clave:
        return "Servicios de diseño"

    if "sin animo de lucro" in clave or "filantrop" in clave or "recaudacion de fondos" in clave:
        return "Organizaciones sin ánimo de lucro"
    if "administracion publica" in clave:
        return "Administración pública"

    if "viaje" in clave or "turismo" in clave:
        return "Organización de viajes"
    if "holding" in clave or "oficinas ejecutivas" in clave:
        return "Oficinas ejecutivas y holdings"
    if "alquiler" in clave:
        return "Alquiler de bienes y equipos"
    if "museo" in clave or "publicacion" in clave:
        return "Medios y publicaciones en línea"

    return None


@lru_cache(maxsize=4096)
def sector_canonico(valor: str | None) -> str | None:
    """Mapea un sector crudo (posiblemente compuesto) a una etiqueta canónica."""
    if not valor:
        return None
    t = limpiar_espacios(valor)
    if not t:
        return None

    partes = _fragmentos(t) if ("," in t or re.search(r"\s+y\s+", t, re.I)) else [t]
    mapeados: list[str] = []
    for parte in partes:
        clave = plegar(parte)
        canon = _regla_por_clave(clave)
        if canon:
            mapeados.append(canon)

    if not mapeados:
        clave_completa = plegar(t)
        canon = _regla_por_clave(clave_completa)
        if canon:
            mapeados.append(canon)

    if not mapeados:
        return "Otros sectores"

    # Preferir el fragmento más específico (no “Otros”) — el primero suele ser el principal en LinkedIn
    for c in mapeados:
        if c != "Otros sectores":
            return c[:255]
    return mapeados[0][:255]


def resumen_mapeo(valores_distintos: list[str]) -> dict[str, list[str] | int]:
    """Agrupa valores crudos por etiqueta canónica (para vista previa / documentación)."""
    from collections import defaultdict

    por_canon: dict[str, list[str]] = defaultdict(list)
    for v in valores_distintos:
        c = sector_canonico(v) or "Otros sectores"
        por_canon[c].append(v)
    return {
        "sectores_canonicos_distintos": len(por_canon),
        "por_canonico": {k: sorted(vs) for k, vs in sorted(por_canon.items(), key=lambda x: (-len(x[1]), x[0]))},
    }