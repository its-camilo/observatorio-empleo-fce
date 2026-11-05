"""Términos frecuentes que parecen herramientas y no están en el catálogo (RF-17).

Heurística: se toman las listas que siguen a frases como "manejo de",
"conocimientos en", "herramientas como", "experiencia en" y se separan por
comas, "y", "o", "/". Se conservan los elementos cortos (1-3 palabras) que
parecen nombre propio de producto (mayúscula inicial, siglas, CamelCase o
con dígitos) y que no coinciden con ningún sinónimo del catálogo. GC decide
después si los agrega o los descarta.
"""
from __future__ import annotations

import re
from collections import Counter

from observatorio.texto import normalizar_clave, plegar

_DISPARADORES = re.compile(
    r"(?:manejo|conocimiento|conocimientos|dominio|experiencia|uso|herramientas?|programas?|software|plataformas?|sistemas?|"
    r"knowledge|proficiency|experience|tools?)\s+(?:avanzado\s+|intermedio\s+|b[aá]sico\s+|s[oó]lidos?\s+)?"
    r"(?:en|de|del|con|como|with|in|of|:)\s+(?:herramientas\s+como\s+|programas\s+como\s+|el\s+|la\s+|los\s+|las\s+)?",
    re.I,
)
_SEPARADORES = re.compile(r",|;|/|\(|\)|\s+y\s+|\s+o\s+|\s+and\s+|\s+or\s+|\s+e\s+", re.I)
_FIN_LISTA = re.compile(r"[.\n:•·\-–]|\s+(?:para|que|con|en el|en la|a nivel)\s+", re.I)

PALABRAS_VACIAS = set("""
el la los las un una de del en y o a con para por al lo su sus se que como más mas muy entre sobre sin otras otros
office ofimatica herramientas herramienta programas programa software sistemas sistema plataformas plataforma paquete
microsoft google adobe ibm oracle manejo conocimiento conocimientos dominio experiencia uso nivel avanzado intermedio basico
procesos normas normatividad contabilidad finanzas impuestos tributaria indicadores informes reportes bases datos base
ingles espanol excelente buen buena manejo areas area empresa empresas clientes cliente ventas gestion equipo equipos
the and or of in with tools tool experience knowledge advanced basic intermediate skills data
""".split())


def _parece_producto(item: str) -> bool:
    palabras = item.split()
    if not 1 <= len(palabras) <= 3 or len(item) < 2 or len(item) > 40:
        return False
    if all(normalizar_clave(p) in PALABRAS_VACIAS for p in palabras):
        return False
    for p in palabras:
        if re.match(r"^[A-Z0-9][A-Za-z0-9.+#&\-]*$", p) and (p[0].isupper() or any(ch.isdigit() for ch in p)):
            return True
        if re.search(r"[a-z][A-Z]", p):  # CamelCase
            return True
    return False


def extraer_candidatos(descripcion: str) -> set[str]:
    texto = descripcion or ""
    candidatos: set[str] = set()
    for m in _DISPARADORES.finditer(texto):
        resto = texto[m.end(): m.end() + 160]
        corte = _FIN_LISTA.search(resto)
        if corte:
            resto = resto[: corte.start()]
        for item in _SEPARADORES.split(resto):
            item = re.sub(r"^\W+|\W+$", "", item.strip())
            if _parece_producto(item):
                candidatos.add(item)
    return candidatos


def contar_no_catalogados(ofertas: list[dict], detector, min_frecuencia: int = 3, max_terminos: int = 300) -> list[dict]:
    """Devuelve [{termino, termino_original, frecuencia, ejemplo_id_oferta}] ordenado."""
    conteo: Counter[str] = Counter()
    originales: dict[str, Counter] = {}
    ejemplo: dict[str, str] = {}
    for o in ofertas:
        vistos = set()
        for cand in extraer_candidatos(o.get("descripcion") or ""):
            clave = normalizar_clave(cand)
            if not clave or clave in vistos or clave in PALABRAS_VACIAS:
                continue
            if detector is not None and detector.coincide_algun_sinonimo(cand):
                continue
            empresa = plegar(o.get("empresa") or "")
            if empresa and clave in normalizar_clave(empresa):
                continue
            vistos.add(clave)
            conteo[clave] += 1
            originales.setdefault(clave, Counter())[cand] += 1
            ejemplo.setdefault(clave, o.get("id_oferta"))
    salida = []
    for clave, n in conteo.most_common(max_terminos):
        if n < min_frecuencia:
            break
        salida.append({"termino": clave, "termino_original": originales[clave].most_common(1)[0][0],
                       "frecuencia": n, "ejemplo_id_oferta": ejemplo[clave]})
    return salida
