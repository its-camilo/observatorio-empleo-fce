"""Corridas, ofertas, análisis, exportación, CSV para Power BI, validación y cursos."""
from __future__ import annotations

import random
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio import analisis
from observatorio.api.seguridad import get_db, usuario_actual
from observatorio.config import ajustes
from observatorio.consultas import buscar_ofertas, listar_cursos, oferta_resumen, valores_filtros
from observatorio.corridas import ErrorCorrida, ejecucion_dict, lanzar, progreso
from observatorio.db.modelos import Ejecucion, Oferta, Usuario, Validacion, ahora
from observatorio.exportar import COLUMNAS, a_csv, a_excel, filas
from observatorio.orquestador import normalizar_corte, normalizar_semestre

router = APIRouter()
META_VALIDACION = 90.0


def _corte(c: str | None) -> str | None:
    return normalizar_corte(c) if c else None


# ----------------------------------------------------------------- corridas
class LanzarIn(BaseModel):
    semestre: str
    corte: str
    modo: str = "completa"


@router.post("/corridas")
def lanzar_corrida(d: LanzarIn, u: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    try:
        e = lanzar(s, d.semestre, d.corte, u.email, d.modo)
    except (ErrorCorrida, ValueError) as ex:
        raise HTTPException(400, str(ex)) from ex
    return ejecucion_dict(e)


@router.get("/corridas")
def listar_corridas(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return [ejecucion_dict(e) for e in s.scalars(select(Ejecucion).order_by(Ejecucion.creado_en.desc()).limit(100))]


@router.get("/corridas/{id_ejecucion}")
def ver_corrida(id_ejecucion: str, _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    e = s.get(Ejecucion, id_ejecucion)
    if e is None:
        raise HTTPException(404, "Ejecución no encontrada")
    return {**ejecucion_dict(e), "progreso": progreso(s, e, consultar_github=True)}


# ----------------------------------------------------------------- ofertas
@router.get("/ofertas")
def ofertas(semestre: str | None = None, corte: str | None = None, carrera: str | None = None, fuente: str | None = None,
            ciudad: str | None = None, software: str | None = None, tipo_oferta: str | None = None, nivel: str | None = None,
            modalidad: str | None = None, texto: str | None = None, pagina: int = 1, tamano: int = Query(25, le=200),
            _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return buscar_ofertas(s, pagina, tamano, semestre=semestre, corte=corte, carrera=carrera, fuente=fuente, ciudad=ciudad,
                          software=software, tipo_oferta=tipo_oferta, nivel=nivel, modalidad=modalidad, texto=texto)


@router.get("/ofertas/filtros")
def filtros(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return valores_filtros(s)


@router.get("/ofertas/{id_oferta}")
def oferta(id_oferta: str, _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    o = s.get(Oferta, id_oferta)
    if o is None:
        raise HTTPException(404, "Oferta no encontrada")
    return oferta_resumen(o, con_descripcion=True)


# ----------------------------------------------------------------- análisis
@router.get("/analisis/cortes")
def cortes(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return analisis.cortes_disponibles(s)


@router.get("/analisis/resumen")
def resumen(semestre: str, corte: str, _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return analisis.resumen_corte(s, semestre, normalizar_corte(corte))


@router.get("/analisis/ranking")
def ranking(semestre: str, corte: str, carrera: str | None = None, _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return {"ranking": analisis.ranking(s, semestre, normalizar_corte(corte), carrera),
            "grupos": analisis.ranking_por_grupo(s, semestre, normalizar_corte(corte), carrera)}


@router.get("/analisis/comparar")
def comparar(semestre_a: str, corte_a: str, semestre_b: str, corte_b: str, carrera: str | None = None,
             _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return analisis.comparar(s, semestre_a, normalizar_corte(corte_a), semestre_b, normalizar_corte(corte_b), carrera)


@router.get("/dashboard")
def dashboard(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    cs = analisis.cortes_disponibles(s)
    ultimo = cs[-1] if cs else None
    return {"cortes": cs, "ultimo_corte": ultimo,
            "resumen": analisis.resumen_corte(s, ultimo["semestre"], ultimo["corte"]) if ultimo else None,
            "total_historico": s.scalar(select(func.count()).select_from(Oferta)) or 0,
            "ultimas_corridas": [ejecucion_dict(e) for e in s.scalars(select(Ejecucion).order_by(Ejecucion.creado_en.desc()).limit(5))]}


# ----------------------------------------------------------------- exportación (RF-11)
@router.get("/exportar/csv")
def exportar_csv(tabla: str, semestre: str | None = None, corte: str | None = None, descripcion: bool = True,
                 _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    if tabla not in COLUMNAS:
        raise HTTPException(400, f"Tabla no válida. Opciones: {', '.join(COLUMNAS)}")
    nombre = f"{tabla}_{semestre or 'todo'}_{(corte or 'todos').lower()}.csv"
    contenido = "".join(a_csv(tabla, filas(s, tabla, semestre, _corte(corte), incluir_descripcion=descripcion)))
    return Response(contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/exportar/excel")
def exportar_excel(semestre: str | None = None, corte: str | None = None, descripcion: bool = True,
                   _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    datos = a_excel(s, semestre, _corte(corte), incluir_descripcion=descripcion)
    nombre = f"observatorio_{semestre or 'historico'}_{(corte or 'todos').lower()}.xlsx"
    return Response(datos, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ----------------------------------------------------------------- CSV públicos para Power BI (RF-14)
@router.get("/publico/{tabla}.csv")
def csv_publico(tabla: str, semestre: str | None = None, corte: str | None = None, pagina: int = Query(1, ge=1),
                tamano: int = Query(5000, ge=1, le=20000), descripcion: bool = False, token: str | None = None,
                s: Session = Depends(get_db)):
    """CSV paginado para Power BI. Sin descripción por defecto (respuestas pequeñas, aptas para Vercel)."""
    esperado = ajustes().csv_token
    if esperado and token != esperado:
        raise HTTPException(401, "Token de CSV no válido")
    if tabla not in ("ofertas", "oferta_software", "oferta_carrera", "catalogo", "ejecuciones", "cursos"):
        raise HTTPException(404, "Tabla no disponible")
    datos = filas(s, tabla, semestre, _corte(corte), incluir_descripcion=descripcion, desde=(pagina - 1) * tamano, limite=tamano)
    return Response("".join(a_csv(tabla, datos)), media_type="text/csv; charset=utf-8",
                             headers={"Cache-Control": "public, max-age=300"})


# ----------------------------------------------------------------- validación (criterio de aceptación 90 %)
class MuestraIn(BaseModel):
    semestre: str
    corte: str
    tamano: int = 30


class RevisionIn(BaseModel):
    resultado: str  # correcto | incorrecto
    softwares_faltantes: str | None = None
    softwares_sobrantes: str | None = None
    comentario: str | None = None


def _estadisticas(items: list[Validacion]) -> dict:
    validados = [v for v in items if v.resultado]
    correctos = sum(1 for v in validados if v.resultado == "correcto")
    precision = round(100 * correctos / len(validados), 1) if validados else None
    return {"total": len(items), "validados": len(validados), "correctos": correctos, "precision": precision,
            "meta": META_VALIDACION, "cumple_meta": precision is not None and precision >= META_VALIDACION and len(validados) == len(items)}


@router.post("/validacion/muestras")
def crear_muestra(d: MuestraIn, u: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    sem, cor = normalizar_semestre(d.semestre), normalizar_corte(d.corte)
    ids = [i for (i,) in s.execute(select(Oferta.id_oferta).where(Oferta.semestre == sem, Oferta.corte == cor))]
    if not ids:
        raise HTTPException(400, "No hay ofertas en ese corte.")
    muestra = random.sample(ids, min(max(1, d.tamano), len(ids), 200))
    mid = f"{sem}-{cor.lower()}-{datetime.now().strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:4]}"
    for i in muestra:
        o = s.get(Oferta, i)
        s.add(Validacion(muestra_id=mid, id_oferta=i, semestre=sem, corte=cor,
                         softwares_detectados="; ".join(x.software for x in o.softwares)))
    return {"muestra_id": mid, "tamano": len(muestra)}


@router.get("/validacion/muestras")
def listar_muestras(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    grupos: dict[str, list[Validacion]] = {}
    for v in s.scalars(select(Validacion).order_by(Validacion.creado_en.desc())):
        grupos.setdefault(v.muestra_id, []).append(v)
    return [{"muestra_id": k, "semestre": v[0].semestre, "corte": v[0].corte, **_estadisticas(v)} for k, v in grupos.items()]


@router.get("/validacion/muestras/{muestra_id}")
def ver_muestra(muestra_id: str, _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    items = list(s.scalars(select(Validacion).where(Validacion.muestra_id == muestra_id).order_by(Validacion.id)))
    if not items:
        raise HTTPException(404, "Muestra no encontrada")
    salida = []
    for v in items:
        o = s.get(Oferta, v.id_oferta)
        salida.append({"id": v.id, "resultado": v.resultado, "softwares_detectados": v.softwares_detectados,
                       "softwares_faltantes": v.softwares_faltantes, "softwares_sobrantes": v.softwares_sobrantes,
                       "comentario": v.comentario, "validado_por": v.validado_por,
                       "oferta": oferta_resumen(o, con_descripcion=True) if o else None})
    return {"muestra_id": muestra_id, "estadisticas": _estadisticas(items), "items": salida}


@router.put("/validacion/items/{vid}")
def revisar(vid: int, d: RevisionIn, u: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    v = s.get(Validacion, vid)
    if v is None:
        raise HTTPException(404, "Elemento no encontrado")
    if d.resultado not in ("correcto", "incorrecto"):
        raise HTTPException(400, "El resultado debe ser 'correcto' o 'incorrecto'.")
    v.resultado, v.softwares_faltantes, v.softwares_sobrantes, v.comentario = d.resultado, d.softwares_faltantes, d.softwares_sobrantes, d.comentario
    v.validado_por, v.fecha_validacion = u.email, ahora()
    return {"ok": True}


# ----------------------------------------------------------------- cursos (RF-19)
@router.get("/cursos")
def cursos(semestre: str | None = None, corte: str | None = None, plataforma: str | None = None, termino: str | None = None,
           _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return listar_cursos(s, semestre, corte, plataforma, termino, limite=500)
