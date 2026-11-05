"""Idiomas con nivel y habilidades blandas (RF-18)."""
from __future__ import annotations

import re

from observatorio.texto import plegar

IDIOMAS = {
    "Inglés": r"ingles|english|bilingue|bilingual",
    "Portugués": r"portugues|portuguese",
    "Francés": r"frances|french",
    "Alemán": r"aleman|german",
    "Italiano": r"italiano|italian",
    "Mandarín": r"mandarin|chino|chinese",
}
_NIVEL = r"(?:nivel\s+)?(a1|a2|b1\+?|b2\+?|c1|c2|basico|intermedio(?:\s*-?\s*avanzado)?|avanzado|nativo|fluido|conversacional|" \
         r"basic|intermediate|advanced|fluent|native|upper[\s-]intermediate)"

_NIVEL_LEGIBLE = {
    "basico": "básico", "basic": "básico", "intermedio": "intermedio", "intermediate": "intermedio",
    "upper intermediate": "B2", "upper-intermediate": "B2", "avanzado": "avanzado", "advanced": "avanzado",
    "nativo": "nativo", "native": "nativo", "fluido": "fluido", "fluent": "fluido", "conversacional": "conversacional",
}

HABILIDADES_BLANDAS = {
    "Comunicación": ["comunicacion asertiva", "comunicacion efectiva", "habilidades de comunicacion", "comunicacion oral", "comunicacion escrita", "communication skills"],
    "Trabajo en equipo": ["trabajo en equipo", "teamwork", "colaboracion", "trabajo colaborativo"],
    "Liderazgo": ["liderazgo", "leadership", "liderar equipos"],
    "Pensamiento analítico": ["pensamiento analitico", "capacidad analitica", "habilidades analiticas", "analytical skills", "pensamiento critico", "critical thinking"],
    "Resolución de problemas": ["resolucion de problemas", "solucion de problemas", "problem solving", "toma de decisiones"],
    "Orientación al resultado": ["orientacion al logro", "orientacion a resultados", "orientacion al resultado", "results oriented"],
    "Servicio al cliente": ["orientacion al cliente", "orientacion al servicio", "servicio al cliente", "customer service"],
    "Organización": ["organizacion", "planificacion", "gestion del tiempo", "atencion al detalle", "atencion a los detalles", "time management", "detail oriented"],
    "Adaptabilidad": ["adaptabilidad", "adaptacion al cambio", "flexibilidad", "manejo del cambio"],
    "Proactividad": ["proactividad", "proactivo", "proactiva", "iniciativa", "proactive"],
    "Negociación": ["negociacion", "negotiation", "habilidades de negociacion"],
    "Ética y responsabilidad": ["etica", "responsabilidad", "integridad", "confidencialidad", "honestidad"],
    "Trabajo bajo presión": ["trabajo bajo presion", "manejo de la presion", "bajo presion"],
    "Relaciones interpersonales": ["relaciones interpersonales", "habilidades interpersonales", "empatia", "interpersonal skills"],
}


def detectar_idiomas(texto: str) -> str:
    """Devuelve p. ej. 'Inglés B2; Portugués básico'."""
    t = plegar(texto or "")
    resultado: dict[str, str] = {}
    for idioma, patron in IDIOMAS.items():
        for m in re.finditer(rf"\b(?:{patron})\b", t):
            # primero se busca el nivel justo después ("inglés B2"), luego justo antes ("nivel B2 de inglés")
            n = re.search(rf"\b{_NIVEL}\b", t[m.end(): m.end() + 35]) or re.search(rf"\b{_NIVEL}\b(?:\s+(?:de|en))?\s*$", t[max(0, m.start() - 30): m.start()])
            nivel = ""
            if n:
                v = n.group(1).strip()
                nivel = v.upper() if re.match(r"^[abc][12]\+?$", v) else _NIVEL_LEGIBLE.get(re.sub(r"\s+", " ", v), v)
            if "bilingue" in m.group(0) or "bilingual" in m.group(0):
                nivel = nivel or "bilingüe"
            previo = resultado.get(idioma)
            if previo is None or (not previo and nivel):
                resultado[idioma] = nivel
    return "; ".join(f"{k} {v}".strip() for k, v in resultado.items())


def detectar_blandas(texto: str) -> str:
    t = plegar(texto or "")
    halladas = [nombre for nombre, frases in HABILIDADES_BLANDAS.items()
                if any(re.search(rf"\b{re.escape(f)}\b", t) for f in frases)]
    return "; ".join(halladas)
