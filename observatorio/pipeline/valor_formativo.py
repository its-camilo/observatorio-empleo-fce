"""Valor formativo: software del catálogo o habilidades técnicas cursables (RF-06).

Criterio (documentado para Camilo y el GC):

- Cuenta software detectado por el catálogo, **excepto** el paquete Office genérico
  (Excel, Word, PowerPoint, Outlook, «Microsoft Office») cuando es la única señal.
  Sí cuentan entradas específicas del catálogo (p. ej. Excel avanzado, Power BI, SAP, Python).
- Cuentan habilidades técnicas o de dominio que justifican un curso corto: NIIF/IFRS,
  SQL, análisis de datos, modelación financiera, tributación con herramientas, SAP, VBA, etc.
- **No** cuentan habilidades blandas genéricas (trabajo en equipo, comunicación, proactividad)
  ni menciones vagas de «manejo de Office», «paquete Office», «Word y Excel» sin nivel avanzado.
"""
from __future__ import annotations

import re

from observatorio.pipeline.clasificacion import titulo_es_cargo_profesional
from observatorio.pipeline.software import Deteccion, DetectorSoftware
from observatorio.texto import limpiar_espacios, plegar

# Software del catálogo que, por sí solo, no justifica un curso (Office básico).
SOFTWARE_GENERICO_OFFICE = frozenset(
    {
        "excel",
        "word",
        "powerpoint",
        "outlook",
        "microsoft office",
        "office",
        "teams",
    }
)

# Habilidades técnicas / de dominio (regex sobre texto plegado). Orden: más específicas primero.
_HABILIDADES_CURSABLES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.I), etiqueta)
    for p, etiqueta in (
        (r"excel\s+(?:avanzado|intermedio|financiero)|advanced\s+excel|tablas?\s+dinamic", "excel avanzado"),
        (r"\b(?:macros?|vba)\b", "vba/macros"),
        (r"power\s*bi|\bpbi\b", "power bi"),
        (r"power\s*query|\bdax\b", "power query/dax"),
        (r"power\s+automate|microsoft\s+power\s+automate", "power automate"),
        (r"\bsap\b|s/4hana|sap\s+fi|sap\s+co|sap\s+mm", "sap"),
        (r"\berp\b|dynamics\s+365|microsoft\s+dynamics", "erp"),
        (r"\bcrm\b|salesforce|hubspot|dynamics\s+crm", "crm"),
        (r"\bsql\b|consultas\s+sql|bases?\s+de\s+datos", "sql"),
        (r"\bpython\b|pandas|numpy\b", "python/datos"),
        (r"\br\b(?=\s*(?:studio|program|lenguaje|stat|analisis))|rstudio|\blenguaje\s+r\b", "r estadístico"),
        (r"\bstata\b", "stata"),
        (r"\bspss\b", "spss"),
        (r"\btableau\b|\bqlik\b|\blooker\b", "tableau/bi"),
        (r"\bniif\b|\bifrs\b|normas?\s+internacionales?\s+de\s+informacion\s+financiera", "niif"),
        (r"contabilidad\s+tributaria|tributari|tributacion|dian\b|facturacion\s+electronica", "contabilidad tributaria"),
        (r"presupuesto|presupuestos|planeacion\s+financiera", "presupuesto"),
        (r"analisis\s+de\s+datos|data\s+analytics|business\s+intelligence|big\s+data", "análisis de datos"),
        (r"modelacion\s+financiera|modelos?\s+financieros?|valuation|valoracion", "modelación financiera"),
        (r"auditoria\s+interna|control\s+interno", "auditoría/control"),
        (r"estadistica\s+(?:aplicada|avanzada)|econometria", "estadística/econometría"),
        (r"\bsas\b(?!\s*\.?\s*a\.?\s*s\.?)", "sas"),
        (r"quickbooks|siigo|helisa|world\s*office|contaplus", "software contable"),
        (r"marketing\s+digital|google\s+ads|meta\s+ads|facebook\s+ads|seo\b|sem\b|google\s+analytics", "marketing digital"),
        (r"\bwms\b|gestion\s+de\s+inventarios?|software\s+de\s+inventario|sistema\s+de\s+inventario", "logística/inventarios"),
        (r"logistica|cadena\s+de\s+suministro|supply\s+chain", "logística"),
        (r"nomina|nómina|payroll|software\s+de\s+nomina", "nómina"),
        (r"\bingles\s+(?:certificado|avanzado|bilingue|b2|c1)|toefl|ielts", "inglés certificado"),
        (r"lean\s+six\s+sigma|six\s+sigma|\blean\b", "lean/six sigma"),
        (r"\bpmp\b|project\s+management\s+professional|scrum\s+master|\bscrum\b|agile\s+project", "gestión de proyectos"),
        (r"\brpa\b|automatizacion|automation|robotic\s+process", "automatización/rpa"),
        (r"chatgpt|inteligencia\s+artificial\s+aplicada", "ia aplicada"),
        (r"analista\s+de\s+inventarios?|gestion\s+de\s+inventarios?", "inventarios"),
        (r"mercad(?:eo|o)\s+y\s+desarrollo|desarrollo\s+de\s+proyectos", "mercadeo/proyectos"),
        (r"talento\s+humano|recursos\s+humanos|\brrhh\b", "talento humano"),
        (r"\bcompras\b|comercial\s+y\s+de\s+compras", "compras/comercial"),
    )
)

_BASICO_OFFICE = re.compile(
    r"manejo\s+(?:de\s+)?(?:microsoft\s+)?office|paquete\s+office|office\s+basico|"
    r"conocimiento\s+(?:de\s+)?(?:microsoft\s+)?office|dominio\s+basico\s+de\s+excel|"
    r"manejo\s+de\s+(?:word|power\s*point)(?:\s+y\s+excel)?",
    re.I,
)

_MIN_DESCRIPCION_PURGA = 30


def tiene_descripcion_util(descripcion: str | None, *, minimo: int = _MIN_DESCRIPCION_PURGA) -> bool:
    """Texto de descripción guardado en `ofertas.descripcion` con longitud útil para evaluar software/habilidades."""
    return len(limpiar_espacios(descripcion or "")) >= minimo


def detectar_habilidades_tecnicas(texto: str) -> list[str]:
    """Devuelve etiquetas de habilidades técnicas encontradas (sin duplicados)."""
    d = plegar(texto or "")
    if not d.strip():
        return []
    found: list[str] = []
    vistos: set[str] = set()
    for patron, etiqueta in _HABILIDADES_CURSABLES:
        if patron.search(d) and etiqueta not in vistos:
            vistos.add(etiqueta)
            found.append(etiqueta)
    return found


def _software_cuenta(detectados: list[Deteccion]) -> bool:
    for d in detectados:
        if plegar(d.software) not in SOFTWARE_GENERICO_OFFICE:
            return True
    return False


def oferta_tiene_valor_formativo(
    cargo: str,
    descripcion: str,
    detector: DetectorSoftware,
    *,
    empresa: str = "",
    habilidades_llm: list[str] | None = None,
    herramientas_llm: list[str] | None = None,
    tiene_habilidad_cursable_llm: bool | None = None,
) -> tuple[bool, str]:
    """
    True si la oferta tiene software relevante o habilidad técnica cursable.
    El segundo elemento es un motivo corto para logs o purga.
    """
    if tiene_habilidad_cursable_llm is True:
        return True, "llm_habilidad_cursable"
    if herramientas_llm and any(h.strip() for h in herramientas_llm):
        return True, "llm_herramienta"
    texto = f"{cargo or ''}\n{descripcion or ''}"
    detectados = detector.detectar(cargo or "", descripcion or "", empresa or "")
    if _software_cuenta(detectados):
        return True, "software_catalogo"
    # Solo Excel/Word genérico: no basta si el texto huele a Office básico sin otra señal
    solo_office = detectados and all(plegar(d.software) in SOFTWARE_GENERICO_OFFICE for d in detectados)
    if solo_office and _BASICO_OFFICE.search(plegar(texto)):
        detectados = []

    habs = detectar_habilidades_tecnicas(texto)
    if titulo_es_cargo_profesional(cargo or ""):
        # Excel genérico en cargos profesionales (p. ej. analista) sí cuenta si no es solo «Office básico».
        if re.search(r"\bexcel\b", plegar(texto)) and not _BASICO_OFFICE.search(plegar(descripcion or "")):
            if "excel" not in habs and "excel avanzado" not in habs:
                habs.append("excel (rol profesional)")
    if habilidades_llm:
        for h in habilidades_llm:
            if h and h.strip():
                habs = habs + [h.strip()[:80]]
    if habs:
        return True, "habilidad_tecnica"
    if detectados and _software_cuenta(detectados):
        return True, "software_catalogo"
    if detectados and not solo_office:
        return True, "software_catalogo"
    return False, "sin_software_ni_habilidad_cursable"
