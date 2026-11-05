"""Exportación a CSV y Excel (RF-11) y tablas para Power BI (RF-14).

Las columnas siguen el diccionario de datos (sección 9) y su orden no cambia
entre ejecuciones, para que Power BI no se rompa.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Iterable, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Catalogo, Curso, Ejecucion, Oferta, OfertaSoftware

COLUMNAS = {
    "ofertas": ["id_oferta", "fuente", "url", "fecha_publicacion", "fecha_extraccion", "semestre", "corte", "cargo", "empresa",
                "sector", "ciudad", "modalidad", "tipo_oferta", "nivel_experiencia", "carrera", "termino_busqueda", "descripcion",
                "num_softwares", "idiomas", "carrera_principal", "habilidades_blandas", "id_ejecucion"],
    "oferta_software": ["id_oferta", "software", "grupo_software", "texto_encontrado", "carrera", "semestre", "corte"],
    "oferta_carrera": ["id_oferta", "carrera", "semestre", "corte"],
    "catalogo": ["software", "grupo", "sinonimos", "activo"],
    "ejecuciones": ["id_ejecucion", "fecha", "semestre", "corte", "ejecutado_por", "fuentes", "ofertas_encontradas",
                    "duplicados_eliminados", "errores", "estado", "ejecutor", "ofertas_guardadas", "no_relevantes", "total_corte",
                    "mini_corrida", "duracion_segundos"],
    "cursos": ["plataforma", "termino", "titulo", "url", "organizacion", "nivel", "tipo", "calificacion", "num_calificaciones",
               "inscritos_recientes", "posicion", "semestre", "corte", "fecha_extraccion"],
}
TABLAS = tuple(COLUMNAS)


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return str(v)


def filas(s: Session, tabla: str, semestre: str | None = None, corte: str | None = None, carrera: str | None = None,
          incluir_descripcion: bool = True, desde: int = 0, limite: int | None = None) -> Iterator[dict]:
    """Genera diccionarios con las columnas de COLUMNAS[tabla]."""
    def filtrar(q, modelo):
        if semestre and hasattr(modelo, "semestre"):
            q = q.where(modelo.semestre == semestre)
        if corte and hasattr(modelo, "corte"):
            q = q.where(modelo.corte == corte)
        return q

    if tabla == "ofertas":
        q = filtrar(select(Oferta), Oferta)
        if carrera:
            q = q.where(Oferta.carrera.contains(carrera))
        q = q.order_by(Oferta.id_oferta).offset(desde)
        if limite:
            q = q.limit(limite)
        for o in s.scalars(q):
            d = {c: getattr(o, c) for c in COLUMNAS["ofertas"]}
            if not incluir_descripcion:
                d["descripcion"] = ""
            yield d
    elif tabla == "oferta_software":
        q = filtrar(select(OfertaSoftware), OfertaSoftware).order_by(OfertaSoftware.id).offset(desde)
        if limite:
            q = q.limit(limite)
        for o in s.scalars(q):
            yield {c: getattr(o, c) for c in COLUMNAS["oferta_software"]}
    elif tabla == "oferta_carrera":
        q = filtrar(select(Oferta.id_oferta, Oferta.carrera, Oferta.semestre, Oferta.corte), Oferta).order_by(Oferta.id_oferta).offset(desde)
        if limite:
            q = q.limit(limite)
        for idf, car, sem, cor in s.execute(q):
            for c in (car or "").split("; "):
                if c:
                    yield {"id_oferta": idf, "carrera": c, "semestre": sem, "corte": cor}
    elif tabla == "catalogo":
        for c in s.scalars(select(Catalogo).order_by(Catalogo.grupo, Catalogo.software)):
            yield {"software": c.software, "grupo": c.grupo, "sinonimos": " | ".join(x.texto for x in c.sinonimos), "activo": c.activo}
    elif tabla == "ejecuciones":
        q = filtrar(select(Ejecucion), Ejecucion).order_by(Ejecucion.creado_en)
        for e in s.scalars(q):
            yield {c: getattr(e, c) for c in COLUMNAS["ejecuciones"]}
    elif tabla == "cursos":
        q = filtrar(select(Curso), Curso).order_by(Curso.id).offset(desde)
        if limite:
            q = q.limit(limite)
        for c in s.scalars(q):
            yield {k: getattr(c, k) for k in COLUMNAS["cursos"]}
    else:
        raise ValueError(f"Tabla desconocida: {tabla}")


def a_csv(tabla: str, datos: Iterable[dict]) -> Iterator[str]:
    """CSV UTF-8 con BOM (Excel y Power BI lo abren con tildes correctas)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    yield "\ufeff"
    w.writerow(COLUMNAS[tabla])
    for d in datos:
        w.writerow([_texto(d.get(c)) for c in COLUMNAS[tabla]])
        if buf.tell() > 64_000:
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()
    yield buf.getvalue()


def a_excel(s: Session, semestre: str | None = None, corte: str | None = None, incluir_descripcion: bool = True) -> bytes:
    """Libro con las tablas del diccionario + ranking por carrera."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    from observatorio.analisis import cortes_disponibles, ranking

    wb = Workbook(write_only=False)
    wb.remove(wb.active)
    for tabla, titulo in (("ofertas", "Ofertas"), ("oferta_software", "Oferta_Software"), ("catalogo", "Catalogo"),
                          ("ejecuciones", "Ejecuciones"), ("cursos", "Cursos")):
        ws = wb.create_sheet(titulo)
        ws.append(COLUMNAS[tabla])
        for c in ws[1]:
            c.font = Font(bold=True)
        for d in filas(s, tabla, semestre, corte, incluir_descripcion=incluir_descripcion):
            ws.append([_texto(d.get(c))[:32000] for c in COLUMNAS[tabla]])
    ws = wb.create_sheet("Ranking")
    cab = ["semestre", "corte", "carrera", "posicion", "software", "grupo", "ofertas", "porcentaje", "variacion_pp", "corte_anterior"]
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True)
    cortes = [(semestre, corte)] if semestre and corte else [(x["semestre"], x["corte"]) for x in cortes_disponibles(s)
                                                             if (not semestre or x["semestre"] == semestre)]
    from observatorio.parametros import leer_config
    carreras = ["Todas"] + list(leer_config(s)["carreras"])
    for sem, cor in cortes:
        for car in carreras:
            for r in ranking(s, sem, cor, car):
                ws.append([_texto(r.get(c)) if c not in ("porcentaje", "variacion_pp", "posicion", "ofertas") else r.get(c) for c in cab])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
