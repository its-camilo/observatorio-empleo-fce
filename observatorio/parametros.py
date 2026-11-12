"""Parámetros funcionales (RF-01) con sus valores por defecto.

Cada clave se guarda en la tabla `config` y se edita desde el aplicativo
(página Configuración). Si una clave no existe en la base, se usa el valor de
este archivo. Nada de esto es secreto.
"""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from observatorio.capitales import filtrar_ubicaciones_config, ubicaciones_capitales_defecto

CARRERAS = ["Administración de Empresas", "Contaduría Pública", "Economía"]

POR_DEFECTO: dict[str, dict[str, Any]] = {
    "carreras": {
        "valor": CARRERAS,
        "descripcion": "Carreras de la FCE. Se pueden agregar otras (agregue también sus reglas en reglas_carrera).",
    },
    "fuentes": {
        "valor": {
            "linkedin": {"activa": True, "max_por_particion": 100, "retraso_segundos": [2.5, 5.0], "fragmentos": 4},
            "indeed": {"activa": True, "max_por_particion": 100, "retraso_segundos": [2.0, 4.0], "fragmentos": 2},
            "computrabajo": {"activa": True, "max_por_particion": 60, "max_paginas": 3, "retraso_segundos": [2.0, 4.0], "fragmentos": 2},
        },
        "descripcion": "Fuentes de ofertas: activar/desactivar, máximo de ofertas por término y ciudad, pausas entre consultas y número de trabajos paralelos en GitHub Actions.",
    },
    "distribucion_fuentes": {
        "valor": {"linkedin": 42, "indeed": 30, "computrabajo": 28},
        "descripcion": "Porcentaje del objetivo de extracción (ofertas crudas) por fuente. Debe sumar 100. 0 % desactiva la fuente en corridas nuevas.",
    },
    "distribucion_carreras": {
        "valor": {"Administración de Empresas": 34, "Contaduría Pública": 33, "Economía": 33},
        "descripcion": "Porcentaje del objetivo de extracción repartido entre carreras (por término de búsqueda). Debe sumar 100.",
    },
    "ubicaciones": {
        "valor": ubicaciones_capitales_defecto(),
        "descripcion": "Capitales departamentales (33 jurisdicciones) a consultar en cada fuente. Vacío en computrabajo = no se consulta en esa fuente.",
    },
    "solo_capitales_departamento": {
        "valor": True,
        "descripcion": "Si está activo, solo se guardan ofertas cuya ciudad normalizada sea una capital departamental "
                       "(o Remoto). «Colombia»/vacío sin capital explícita se descarta. Las corridas usan solo ubicaciones del catálogo de capitales.",
    },
    "ventana_dias": {"valor": 30, "descripcion": "Solo ofertas publicadas en los últimos N días."},
    "tipo_oferta": {"valor": "ambas", "descripcion": "practica, empleo o ambas."},
    "objetivo_ofertas_corrida": {
        "valor": 10000,
        "descripcion": "Número de ofertas crudas a recolectar en cada corrida. El orquestador reparte este cupo según "
                       "distribucion_fuentes y distribucion_carreras (LinkedIn primero) y detiene la extracción al alcanzarlo. "
                       "También define la meta de relevantes guardadas para la mini corrida. "
                       "max_por_particion en «fuentes» sigue siendo el tope por consulta (término × ciudad).",
    },
    "mini_corrida": {
        "valor": {"habilitada": True, "max_minutos": 240, "fuentes": ["linkedin", "indeed", "computrabajo"]},
        "descripcion": "Si no se llega a la meta, se hace una mini corrida con los términos 'ampliado'.",
    },
    "dedup": {
        "valor": {"alcance": "global", "dias": 7},
        "descripcion": "Duplicados (RF-08): misma empresa + cargo + ciudad con fechas a menos de N días. alcance=global compara contra todo el historial; alcance=corte solo dentro del mismo semestre y corte.",
    },
    "llm": {
        "valor": {
            "habilitado": True,
            "tamano_lote": 20,
            "max_solicitudes_dia": 50,
            "solicitudes_por_minuto": 12,
            "max_solicitudes_corrida": 600,
        },
        "descripcion": "Clasificación con OpenRouter solo para ofertas dudosas. Modelo fijo openrouter/free "
                       "(tier gratuito ~20 req/min; cupo diario según créditos OpenRouter, p. ej. 50–1000/día). "
                       "solicitudes_por_minuto conservador (12) para evitar 429.",
    },
    "reglas_carrera": {
        "valor": {
            "Contaduría Pública": {
                "titulo": ["contador", "contadora", "contable", "contabilidad", "auditor", "auditora", "auditoría", "auditoria", "revisor fiscal",
                            "revisoría fiscal", "tributari", "impuestos", "nómina", "nomina", "tesorer", "facturación", "facturacion", "cartera",
                            "cuentas por pagar", "cuentas por cobrar", "costos", "niif", "accountant", "accounting", "audit", "tax ", "payroll",
                            "control interno", "contralor", "conciliacion", "conciliación"],
                "descripcion": ["contaduría pública", "contaduria publica", "contador público", "contador publico", "contaduría", "contaduria",
                                 "tarjeta profesional de contador", "estados financieros", "niif", "declaraciones tributarias", "conciliaciones bancarias",
                                 "revisoría fiscal", "medios magnéticos", "exógena", "retención en la fuente", "cierre contable"],
            },
            "Economía": {
                "titulo": ["economista", "económic", "economic", "econom", "riesgo", "riesgos", "inversion", "inversión", "financier", "finanzas",
                            "data analyst", "analista de datos", "analítica", "analitica", "estadístic", "estadistic", "cuantitativ", "pricing", "precios",
                            "crédito", "credito", "investment", "risk", "financial", "fp&a", "planeación financiera", "planeacion financiera",
                            "business intelligence", "inteligencia de negocios", "actuari", "mercado de capitales", "investigador", "research"],
                "descripcion": ["economía", "economia", "economista", "ciencias económicas", "ciencias economicas", "econometría", "econometria",
                                 "finanzas", "ingeniería financiera", "estadística", "modelos econométricos", "riesgo de crédito", "riesgo de mercado",
                                 "análisis económico", "analisis economico", "indicadores económicos", "macroeconom"],
            },
            "Administración de Empresas": {
                "titulo": ["administrador", "administradora", "administrativ", "administración", "administracion", "gerente", "gerencia", "coordinador",
                            "coordinadora", "jefe", "director", "directora", "proyectos", "procesos", "operaciones", "comercial", "compras", "logística",
                            "logistica", "talento humano", "recursos humanos", "gestión humana", "gestion humana", "mercadeo", "marketing", "calidad",
                            "planeación", "planeacion", "business analyst", "project manager", "management", "asistente de gerencia", "ejecutivo",
                            "abastecimiento", "supply", "ventas", "servicio al cliente", "operations", "manager"],
                "descripcion": ["administración de empresas", "administracion de empresas", "administrador de empresas", "ciencias administrativas",
                                 "administración", "gestión empresarial", "gestion empresarial", "negocios internacionales", "mercadeo", "ingeniería industrial"],
            },
        },
        "descripcion": "Palabras que asignan carrera por título (fuerte) y por descripción (débil). Ver documentación técnica.",
    },
    "exclusion_titulo": {
        "valor": ["desarrollador", "developer", "software engineer", "ingeniero de software", "ingeniero de sistemas", "devops", "frontend", "backend",
                  "full stack", "fullstack", "enfermer", "médico", "medico", "odontólog", "fisioterapeut", "conductor", "mensajero", "mesero", "cocinero",
                  "chef", "vigilante", "guarda de seguridad", "operario", "soldador", "electricista", "mecánico", "mecanico", "técnico de mantenimiento",
                  "auxiliar de bodega", "bodeguero", "aseo", "oficios varios", "docente de", "profesor de", "estilista", "barista", "domiciliario",
                  "auxiliar de enfermería", "regente de farmacia", "psicólogo", "abogado", "arquitecto", "diseñador gráfico", "ingeniero civil",
                  "ingeniero electrónico", "ingeniero mecánico", "data engineer", "ingeniero de datos", "qa ", "tester", "soporte técnico"],
        "descripcion": "Si el título tiene alguna de estas palabras y ninguna palabra fuerte de carrera, la oferta se descarta como no relevante.",
    },
    "exclusion_operativa_titulo": {
        "valor": [
            "auxiliar administrativ", "asistente administrativ", "aprendiz administrativ", "practicante administrativ",
            "coordinador administrativ", "secretari", "recepcionista", "auxiliar de oficina", "asistente de oficina",
            "auxiliar general", "digitador", "auxiliar de archivo", "auxiliar de correspondencia", "auxiliar de servicios generales",
            "auxiliar de gestion documental", "auxiliar de gestión documental", "auxiliar de soporte administrativ",
            "asistente de archivo", "mensajero", "auxiliar de logistica", "auxiliar de logística", "auxiliar de almacen",
            "auxiliar de almacén", "auxiliar de inventario", "asistente de gerencia", "asistente de gestion", "asistente de gestión",
            "auxiliar de servicio al cliente", "auxiliar de servicios al cliente", "asesor comercial", "asesora comercial",
            "asesor de ventas", "asesora de ventas", "asesor de venta", "cajero", "cajera", "data entry",
            "auxiliar contable y administrativ", "asistente contable y administrativ",
            "auxiliar administrativ y contable", "asistente administrativ y contable",
            "auxiliar administrativa bilingue", "asistente administrativa bilingue", "auxiliar administrativo bilingue",
            "auxiliar de correspondencia", "operador de call center", "teleoperador", "agente de call center",
        ],
        "descripcion": "Cargos administrativos u operativos de bajo nivel que se descartan siempre (incluso si la descripción menciona Excel). "
                       "No aplican si el cargo es claramente profesional (analista, contador, economista, coordinador financiero, etc.).",
    },
    "requiere_software_o_habilidad": {
        "valor": True,
        "descripcion": "Solo guardar ofertas relevantes que mencionen software del catálogo (excepto Office genérico) "
                       "o una habilidad técnica cursable. Ver observatorio/pipeline/valor_formativo.py.",
    },
    "cursos": {
        "valor": {
            "activo": True, "plataformas": ["coursera", "edx", "platzi"], "max_por_termino": 15,
            "terminos": ["excel", "power bi", "python", "sql", "inteligencia artificial", "análisis de datos", "contabilidad", "finanzas",
                          "economía", "gestión de proyectos", "sap", "tableau", "estadística", "chatgpt"],
        },
        "descripcion": "Módulo de cursos en tendencia (RF-19).",
    },
    "no_catalogados": {
        "valor": {"min_frecuencia": 3, "max_terminos": 300},
        "descripcion": "Términos frecuentes fuera del catálogo (RF-17): frecuencia mínima por corrida.",
    },
}


def valores_por_defecto() -> dict[str, Any]:
    return {k: copy.deepcopy(v["valor"]) for k, v in POR_DEFECTO.items()}


def leer_config(s: Session) -> dict[str, Any]:
    """Combina los valores por defecto con lo guardado en la tabla `config`."""
    from observatorio.db.modelos import Config

    cfg = valores_por_defecto()
    for fila in s.query(Config).all():
        if fila.clave in cfg and isinstance(cfg[fila.clave], dict) and isinstance(fila.valor, dict) \
                and fila.clave not in ("reglas_carrera",):
            base = cfg[fila.clave]
            for k, v in fila.valor.items():
                if isinstance(base.get(k), dict) and isinstance(v, dict):
                    base[k] = {**base[k], **v}
                else:
                    base[k] = v
        else:
            cfg[fila.clave] = fila.valor
    # Migración suave: claves antiguas → objetivo_ofertas_corrida
    if cfg.get("objetivo_ofertas_corrida") is None:
        lim = cfg.get("limite_extraccion_corrida")
        meta = cfg.get("meta_ofertas")
        if lim is not None and int(lim or 0) > 0:
            cfg["objetivo_ofertas_corrida"] = int(lim)
        elif meta is not None:
            cfg["objetivo_ofertas_corrida"] = int(meta or 10000)
    from observatorio.distribucion import DISTRIBUCION_FUENTES_DEFECTO, distribucion_carreras_igualitaria

    if not cfg.get("distribucion_fuentes"):
        cfg["distribucion_fuentes"] = dict(DISTRIBUCION_FUENTES_DEFECTO)
    if not cfg.get("distribucion_carreras"):
        cfg["distribucion_carreras"] = distribucion_carreras_igualitaria(cfg.get("carreras") or [])
    solo_cap = bool(cfg.get("solo_capitales_departamento", True))
    cfg["ubicaciones"] = filtrar_ubicaciones_config(cfg.get("ubicaciones") or [], solo_capitales=solo_cap)
    return cfg
