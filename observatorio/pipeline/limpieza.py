"""Limpieza (RF-07): de oferta cruda a fila con la estructura del diccionario de datos."""
from __future__ import annotations

import re
from datetime import date

from observatorio.pipeline.dedup import clave_dedup
from observatorio.texto import (
    detectar_modalidad, detectar_nivel, detectar_tipo_oferta, limpiar_descripcion, limpiar_espacios, normalizar_cargo,
    normalizar_ciudad, normalizar_empresa, normalizar_fecha,
)

PREFIJOS = {"LinkedIn": "LI", "Indeed": "IN", "Google Jobs": "GO", "Computrabajo": "CT"}
MAX_DESCRIPCION = 15000

_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TELEFONO = re.compile(r"(?<!\d)(?:\+?57\s?)?(?:3\d{2}|60\d)[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
_SALARIO = re.compile(r"(?i)(?:salario|sueldo|remuneraci[oó]n|asignaci[oó]n salarial)[^\n]{0,80}?\$\s?[\d.,]+[^\n]*|\$\s?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?")


def quitar_datos_personales(texto: str) -> str:
    """Quita correos, teléfonos y salarios (el documento excluye ambos)."""
    t = _CORREO.sub("[correo omitido]", texto or "")
    t = _TELEFONO.sub("[teléfono omitido]", t)
    t = _SALARIO.sub("", t)
    return t


def id_oferta(fuente: str, id_fuente: str, sufijo: str = "") -> str:
    return f"{PREFIJOS.get(fuente, fuente[:2].upper())}-{id_fuente}{sufijo}"


def normalizar_cruda(datos: dict, *, termino: str | None, carrera_termino: str | None, semestre: str, corte: str,
                     fecha_extraccion: date, id_ejecucion: str, sufijo_id: str = "") -> dict:
    descripcion = limpiar_descripcion(quitar_datos_personales(datos.get("descripcion") or ""))[:MAX_DESCRIPCION]
    cargo = normalizar_cargo(datos.get("cargo"))
    empresa = normalizar_empresa(datos.get("empresa"))
    remoto = datos.get("remoto")
    ciudad = normalizar_ciudad(datos.get("ubicacion"), remoto=bool(remoto))
    modalidad = detectar_modalidad(cargo, descripcion[:3000], datos.get("tipo_empleo") or "", datos.get("ubicacion") or "",
                                   remoto=remoto)
    if modalidad == "Remoto" and ciudad == "Colombia":
        ciudad = "Remoto"
    tipo = detectar_tipo_oferta(cargo, descripcion, datos.get("tipo_empleo") or "")
    nivel = detectar_nivel(cargo, descripcion, datos.get("nivel_fuente") or "", tipo)
    fecha_pub = normalizar_fecha(datos.get("fecha_publicacion"), hoy=fecha_extraccion)
    return {
        "id_oferta": id_oferta(datos["fuente"], str(datos["id_fuente"]), sufijo_id),
        "fuente": datos["fuente"],
        "url": datos.get("url") or "",
        "fecha_publicacion": fecha_pub,
        "fecha_extraccion": fecha_extraccion,
        "semestre": semestre,
        "corte": corte,
        "cargo": cargo[:500],
        "empresa": empresa[:500],
        "sector": limpiar_espacios(datos.get("sector"))[:255] or None,
        "ciudad": ciudad,
        "modalidad": modalidad,
        "tipo_oferta": tipo,
        "nivel_experiencia": nivel,
        "termino_busqueda": termino or "",
        "carrera_termino": carrera_termino,
        "descripcion": descripcion,
        "id_ejecucion": id_ejecucion,
        "id_fuente": str(datos["id_fuente"]),
        "ubicacion_original": datos.get("ubicacion") or "",
        "clave_dedup": clave_dedup(empresa, cargo, ciudad, descripcion),
    }
