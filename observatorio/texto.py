"""Normalización de textos, ciudades, fechas y empresas (RF-07)."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta

_ESPACIOS = re.compile(r"\s+")


def sin_tildes(texto: str) -> str:
    """Quita tildes y diacríticos conservando la ñ como n (para comparar)."""
    nfkd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def plegar_caracter(c: str) -> str:
    """Pliega un carácter a minúscula sin tilde, garantizando longitud 1."""
    p = sin_tildes(c).lower()
    return p[:1] if p else c


def plegar(texto: str) -> str:
    """Versión minúscula y sin tildes con la MISMA longitud que el original.

    Mantener la longitud permite mapear coincidencias de vuelta al texto
    original (para reportar `texto_encontrado` tal como aparece).
    """
    return "".join(plegar_caracter(c) for c in (texto or ""))


def limpiar_espacios(texto: str | None) -> str:
    return _ESPACIOS.sub(" ", (texto or "").replace("\u00a0", " ")).strip()


def normalizar_clave(texto: str | None) -> str:
    """Minúsculas, sin tildes, sin signos y con espacios simples."""
    t = sin_tildes(texto or "").lower()
    t = re.sub(r"[^a-z0-9ñ&+#/ ]+", " ", t)
    return limpiar_espacios(t)


def limpiar_descripcion(texto: str | None) -> str:
    """Limpia una descripción conservando saltos de línea útiles."""
    t = (texto or "").replace("\r", "\n").replace("\u00a0", " ")
    t = re.sub(r"[ \t\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    t = re.sub(r" *\n *", "\n", t)
    # Markdown de JobSpy: quitar asteriscos y escapes
    t = re.sub(r"\\([\-*_#+.()!\[\]])", r"\1", t)
    t = re.sub(r"\*{1,3}", "", t)
    return t.strip()


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------
_SUFIJOS_EMPRESA = re.compile(
    r"\b(s\s?a\s?s|s\s?a|ltda|limitada|e\s?s\s?p|bic|inc|llc|corp|corporation|ltd|sociedad anonima|"
    r"y cia|& cia|cia|s en c|plc|gmbh|sl|zomac)\b"
)
GENERICAS = ("importante empresa", "empresa confidencial", "confidencial", "empresa del sector", "reconocida empresa",
             "empresa reconocida", "compania confidencial")


def normalizar_empresa(nombre: str | None) -> str:
    """Nombre legible: espacios limpios; si viene todo en mayúsculas, se pasa a tipo título."""
    t = limpiar_espacios(nombre)
    if t.lower() in {"unknown", "nan", "none", ""}:
        return ""
    if t.isupper() and len(t) > 5:
        t = t.title()
    return t


def clave_empresa(nombre: str | None) -> str:
    t = normalizar_clave((nombre or "").replace(".", " ").replace(",", " "))
    t = _SUFIJOS_EMPRESA.sub(" ", t)
    t = re.sub(r"\bcolombia\b", " ", t)
    return limpiar_espacios(t)


def es_empresa_generica(nombre: str | None) -> bool:
    t = normalizar_clave(nombre)
    return not t or any(g in t for g in GENERICAS)


# ---------------------------------------------------------------------------
# Cargos
# ---------------------------------------------------------------------------
def normalizar_cargo(cargo: str | None) -> str:
    t = limpiar_espacios(cargo)
    if t.isupper() and len(t) > 4:
        t = t.capitalize()
    return t


def clave_cargo(cargo: str | None) -> str:
    t = (cargo or "").lower()
    t = re.sub(r"\((?:a|o|as|os|e)\)|/(?:a|o|as|os)\b", "", t)  # marcadores de género
    t = re.sub(r"\b(urgente|vacante|importante empresa|se busca|se requiere)\b", " ", t)
    return normalizar_clave(t)


# ---------------------------------------------------------------------------
# Ciudades
# ---------------------------------------------------------------------------
CIUDADES = {
    "bogota": "Bogotá", "bogota d c": "Bogotá", "bogota dc": "Bogotá", "santafe de bogota": "Bogotá", "santa fe de bogota": "Bogotá",
    "medellin": "Medellín", "cali": "Cali", "santiago de cali": "Cali", "barranquilla": "Barranquilla", "bucaramanga": "Bucaramanga",
    "cartagena": "Cartagena", "cartagena de indias": "Cartagena", "pereira": "Pereira", "manizales": "Manizales", "cucuta": "Cúcuta",
    "ibague": "Ibagué", "villavicencio": "Villavicencio", "santa marta": "Santa Marta", "pasto": "Pasto", "monteria": "Montería",
    "neiva": "Neiva", "armenia": "Armenia", "tunja": "Tunja", "popayan": "Popayán", "valledupar": "Valledupar", "sincelejo": "Sincelejo",
    "soacha": "Soacha", "chia": "Chía", "mosquera": "Mosquera", "funza": "Funza", "cota": "Cota", "tocancipa": "Tocancipá",
    "zipaquira": "Zipaquirá", "madrid": "Madrid (Cundinamarca)", "facatativa": "Facatativá", "envigado": "Envigado", "itagui": "Itagüí",
    "sabaneta": "Sabaneta", "bello": "Bello", "rionegro": "Rionegro", "yumbo": "Yumbo", "palmira": "Palmira", "floridablanca": "Floridablanca",
    "girardot": "Girardot", "usaquen": "Bogotá", "chapinero": "Bogotá", "teusaquillo": "Bogotá", "suba": "Bogotá",
    "engativa": "Bogotá", "fontibon": "Bogotá", "kennedy": "Bogotá", "bosa": "Bogotá", "puente aranda": "Bogotá",
    "barrios unidos": "Bogotá", "los martires": "Bogotá", "santa fe": "Bogotá", "usme": "Bogotá", "tunjuelito": "Bogotá",
    "ciudad bolivar": "Bogotá", "rafael uribe uribe": "Bogotá", "antonio narino": "Bogotá", "san cristobal": "Bogotá",
    "la candelaria": "Bogotá", "sumapaz": "Bogotá", "cun": "Cundinamarca", "ant": "Antioquia", "vac": "Valle del Cauca", "sogamoso": "Sogamoso", "duitama": "Duitama", "soledad": "Soledad", "malambo": "Malambo",
}
DEPARTAMENTOS_A_CAPITAL = {
    "capital district": "Bogotá", "distrito capital": "Bogotá", "cundinamarca": "Cundinamarca", "antioquia": "Antioquia",
    "valle del cauca": "Valle del Cauca", "atlantico": "Atlántico", "santander": "Santander", "bolivar": "Bolívar",
}


def normalizar_ciudad(ubicacion: str | None, remoto: bool = False) -> str:
    """Convierte 'Bogota, D.C., Capital District, Colombia' en 'Bogotá'."""
    t = normalizar_clave((ubicacion or "").replace(".", ""))
    if not t or t in {"colombia", "co"}:
        return "Remoto" if remoto else "Colombia"
    partes = [limpiar_espacios(p) for p in re.split(r",| - |\|", sin_tildes((ubicacion or "").replace(".", "")).lower())]
    for p in partes:
        p = normalizar_clave(p)
        if p in CIUDADES:
            return CIUDADES[p]
    for nombre, canon in CIUDADES.items():
        if re.search(rf"\b{re.escape(nombre)}\b", t):
            return canon
    for nombre, canon in DEPARTAMENTOS_A_CAPITAL.items():
        if nombre in t:
            return canon
    if re.search(r"\b(remoto|remote|teletrabajo)\b", t):
        return "Remoto"
    primera = limpiar_espacios((ubicacion or "").split(",")[0])
    if not primera or not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{3,}", primera):
        return "Colombia"
    return primera.title()


def es_colombia(ubicacion: str | None) -> bool:
    """Descarta ubicaciones claramente fuera de Colombia."""
    t = normalizar_clave(ubicacion)
    if not t:
        return True
    if "colombia" in t:
        return True
    if any(re.search(rf"\b{re.escape(c)}\b", t) for c in CIUDADES):
        return True
    extranjero = ("mexico", "peru", "chile", "argentina", "ecuador", "spain", "espana", "united states", "estados unidos",
                  "venezuela", "panama", "costa rica", "brasil", "brazil", "usa", "canada", "lima", "santiago", "quito", "madrid spain")
    return not any(re.search(rf"\b{x}\b", t) for x in extranjero)


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------
_MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def normalizar_fecha(valor, hoy: date | None = None) -> date | None:
    """Acepta date, datetime, ISO, '15 hours ago', 'Hace 3 días', 'Ayer', '2 de octubre'."""
    hoy = hoy or date.today()
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    if s.lower() in {"nat", "nan", "none"}:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    t = sin_tildes(s).lower()
    if "hoy" in t or "today" in t or "just now" in t or "momento" in t:
        return hoy
    if "ayer" in t or "yesterday" in t:
        return hoy - timedelta(days=1)
    m = re.search(r"(\d+)\s*\+?\s*(minuto|minute|min|hora|hour|hr|dia|day|semana|week|mes|month)", t)
    if m:
        n = int(m[1])
        u = m[2]
        if u.startswith(("minuto", "minute", "min", "hora", "hour", "hr")):
            return hoy
        if u.startswith(("dia", "day")):
            return hoy - timedelta(days=n)
        if u.startswith(("semana", "week")):
            return hoy - timedelta(weeks=n)
        return hoy - timedelta(days=30 * n)
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-z]{3})[a-z]*(?:\s+(?:de\s+)?(\d{4}))?", t)
    if m and m[2] in _MESES:
        anio = int(m[3]) if m[3] else hoy.year
        try:
            d = date(anio, _MESES[m[2]], int(m[1]))
        except ValueError:
            return None
        if d > hoy and not m[3]:
            d = date(anio - 1, d.month, d.day)
        return d
    return None


# ---------------------------------------------------------------------------
# Modalidad, tipo de oferta y nivel
# ---------------------------------------------------------------------------
def detectar_modalidad(*textos: str, remoto: bool | None = None) -> str:
    t = plegar(" ".join(x or "" for x in textos))
    if re.search(r"\b(hibrid[oa]|hybrid|modalidad mixta)\b", t):
        return "Híbrido"
    if remoto or re.search(r"\b(remot[oa]|remote|teletrabajo|trabajo en casa|home office|100% virtual|work from home)\b", t):
        return "Remoto"
    return "Presencial"


_PRACTICA = re.compile(r"\b(practica(?:s)?(?: profesional(?:es)?)?|practicante|pasant[ei]a?s?|pasante|aprendiz|aprendices|intern|internship|"
                       r"trainee|etapa productiva|contrato de aprendizaje|estudiante en practica)\b")


def detectar_tipo_oferta(cargo: str, descripcion: str = "", tipo_empleo: str = "") -> str:
    t_cargo = plegar(cargo)
    if _PRACTICA.search(t_cargo) or re.search(r"\b(internship|practicas|prácticas)\b", plegar(tipo_empleo)):
        return "Práctica/pasantía"
    if re.search(r"\b(contrato de aprendizaje|etapa productiva|practica profesional|practicas profesionales)\b", plegar(descripcion)[:1500]):
        return "Práctica/pasantía"
    return "Empleo"


_NIVELES_FUENTE = {
    "internship": "Practicante", "practicas": "Practicante", "prácticas": "Practicante",
    "entry level": "Sin experiencia / Junior", "sin experiencia": "Sin experiencia / Junior", "algo de responsabilidad": "Sin experiencia / Junior",
    "associate": "Intermedio", "asociado": "Intermedio",
    "mid-senior level": "Senior", "intermedio": "Intermedio", "mid-senior": "Senior",
    "director": "Directivo", "executive": "Directivo", "ejecutivo": "Directivo",
}


def detectar_nivel(cargo: str, descripcion: str = "", nivel_fuente: str = "", tipo_oferta: str = "") -> str:
    if tipo_oferta.startswith("Práctica"):
        return "Practicante"
    t = plegar(cargo)
    if re.search(r"\b(gerente|director|directora|vicepresidente|head of|chief|cfo|jefe nacional)\b", t):
        return "Directivo"
    if re.search(r"\b(senior|sr|lider|lead|especialista|experto|jefe|coordinador|coordinadora|manager)\b", t):
        return "Senior"
    if re.search(r"\b(junior|jr|auxiliar|asistente|trainee|primer empleo|recien egresado)\b", t):
        return "Sin experiencia / Junior"
    nf = plegar(nivel_fuente).strip()
    if nf in _NIVELES_FUENTE:
        return _NIVELES_FUENTE[nf]
    d = plegar(descripcion)[:3000]
    if re.search(r"\bsin experiencia|primer empleo|recien egresad|no se requiere experiencia\b", d):
        return "Sin experiencia / Junior"
    m = re.search(r"(\d{1,2})\s*(?:\+\s*)?(?:a|años|anos)\s+de\s+experiencia", d)
    if m:
        n = int(m[1])
        return "Sin experiencia / Junior" if n <= 1 else ("Intermedio" if n <= 4 else "Senior")
    if re.search(r"\b(analista|profesional)\b", t):
        return "Intermedio"
    return "No especificado"


def hash_texto(*partes: str) -> str:
    return hashlib.sha256("\x1f".join(p or "" for p in partes).encode("utf-8")).hexdigest()


def clave_ciudad_dedup(ciudad: str | None) -> str:
    """La ciudad ya normalizada, como clave ('Bogotá' -> 'bogota')."""
    c = normalizar_clave(ciudad)
    return "colombia" if c in {"remoto", "colombia", ""} else c
