"""Consultas de solo lectura compartidas por la API y el servidor MCP."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Catalogo, Curso, Oferta, OfertaSoftware
from observatorio.filtro_ofertas import oferta_incluida_en_resultados


def filtrar_ofertas(q, semestre=None, corte=None, carrera=None, fuente=None, ciudad=None, software=None, tipo_oferta=None,
                    nivel=None, modalidad=None, texto=None, incluir_excluidas: bool = False):
    if not incluir_excluidas:
        q = q.where(oferta_incluida_en_resultados())
    if semestre:
        q = q.where(Oferta.semestre == semestre)
    if corte:
        q = q.where(Oferta.corte == corte.capitalize())
    if carrera:
        q = q.where(Oferta.carrera.contains(carrera))
    if fuente:
        q = q.where(Oferta.fuente == fuente)
    if ciudad:
        q = q.where(Oferta.ciudad == ciudad)
    if tipo_oferta:
        q = q.where(Oferta.tipo_oferta == tipo_oferta)
    if nivel:
        q = q.where(Oferta.nivel_experiencia == nivel)
    if modalidad:
        q = q.where(Oferta.modalidad == modalidad)
    if software:
        q = q.where(Oferta.id_oferta.in_(select(OfertaSoftware.id_oferta).where(OfertaSoftware.software == software)))
    if texto:
        t = f"%{texto.strip()}%"
        q = q.where(or_(Oferta.cargo.ilike(t), Oferta.empresa.ilike(t), Oferta.descripcion.ilike(t)))
    return q


def oferta_resumen(o: Oferta, con_descripcion: bool = False, max_desc: int | None = None) -> dict:
    d = {"id_oferta": o.id_oferta, "fuente": o.fuente, "url": o.url,
         "fecha_publicacion": o.fecha_publicacion.isoformat() if o.fecha_publicacion else None,
         "fecha_extraccion": o.fecha_extraccion.isoformat() if o.fecha_extraccion else None,
         "semestre": o.semestre, "corte": o.corte, "cargo": o.cargo, "empresa": o.empresa, "sector": o.sector, "ciudad": o.ciudad,
         "modalidad": o.modalidad, "tipo_oferta": o.tipo_oferta, "nivel_experiencia": o.nivel_experiencia, "carrera": o.carrera,
         "termino_busqueda": o.termino_busqueda, "num_softwares": o.num_softwares, "idiomas": o.idiomas,
         "habilidades_blandas": o.habilidades_blandas, "softwares": [x.software for x in o.softwares]}
    if con_descripcion:
        desc = o.descripcion or ""
        d["descripcion"] = desc[:max_desc] + ("…" if max_desc and len(desc) > max_desc else "") if max_desc else desc
        d["detecciones"] = [{"software": x.software, "grupo": x.grupo_software, "texto_encontrado": x.texto_encontrado} for x in o.softwares]
    return d


def _solo_filtros_conteo_precalculado(filtros: dict) -> bool:
    return not any(
        filtros.get(k)
        for k in ("fuente", "ciudad", "software", "tipo_oferta", "nivel", "modalidad", "texto")
    )


def buscar_ofertas(s: Session, pagina: int = 1, tamano: int = 25, con_descripcion: bool = False, max_desc: int | None = None,
                   **filtros) -> dict:
    q = filtrar_ofertas(select(Oferta), **filtros)
    total: int | None = None
    if _solo_filtros_conteo_precalculado(filtros):
        # Import perezoso: agregados ya importa valores_filtros de este módulo.
        from observatorio.agregados import conteo_ofertas_precalculado

        total = conteo_ofertas_precalculado(s, filtros.get("semestre"), filtros.get("corte"), filtros.get("carrera"))
    if total is None:
        total = s.scalar(filtrar_ofertas(select(func.count()).select_from(Oferta), **filtros)) or 0
    pagina = max(1, pagina)
    filas = s.scalars(q.order_by(Oferta.fecha_publicacion.desc().nullslast(), Oferta.id_oferta).offset((pagina - 1) * tamano).limit(tamano))
    return {"total": total, "pagina": pagina, "tamano": tamano, "paginas": (total + tamano - 1) // tamano if tamano else 0,
            "items": [oferta_resumen(o, con_descripcion, max_desc) for o in filas]}


def valores_filtros(s: Session) -> dict:
    def distintos(col):
        return [v for (v,) in s.execute(select(col).distinct().order_by(col)) if v]
    carreras = set()
    for (c,) in s.execute(select(Oferta.carrera).distinct()):
        carreras.update(x for x in (c or "").split("; ") if x)
    return {"semestres": distintos(Oferta.semestre), "cortes": ["Inicio", "Mitad", "Final"], "fuentes": distintos(Oferta.fuente),
            "ciudades": distintos(Oferta.ciudad), "tipos_oferta": distintos(Oferta.tipo_oferta),
            "niveles": distintos(Oferta.nivel_experiencia), "modalidades": distintos(Oferta.modalidad),
            "carreras": sorted(carreras), "softwares": [c for (c,) in s.execute(select(Catalogo.software).order_by(Catalogo.software))]}


def catalogo_publico(s: Session, solo_activos: bool = True) -> list[dict]:
    q = select(Catalogo).order_by(Catalogo.grupo, Catalogo.software)
    if solo_activos:
        q = q.where(Catalogo.activo.is_(True))
    return [{"software": c.software, "grupo": c.grupo, "activo": c.activo, "sinonimos": [x.texto for x in c.sinonimos]} for c in s.scalars(q)]


def listar_cursos(
    s: Session,
    semestre=None,
    corte=None,
    plataforma=None,
    termino=None,
    carrera=None,
    limite: int = 100,
) -> list[dict]:
    import json

    q = select(Curso)
    if semestre:
        q = q.where(Curso.semestre == semestre)
    if corte:
        q = q.where(Curso.corte == corte.capitalize())
    if plataforma:
        q = q.where(Curso.plataforma == plataforma)
    if termino:
        q = q.where(
            Curso.termino.ilike(f"%{termino}%") | Curso.habilidad_demanda.ilike(f"%{termino}%")
        )
    q = q.order_by(Curso.puntaje_recomendacion.desc().nullslast(), Curso.demanda_pct.desc().nullslast(), Curso.posicion).limit(limite)
    out: list[dict] = []
    for c in s.scalars(q):
        dem_car = None
        if c.demanda_carreras:
            try:
                dem_car = json.loads(c.demanda_carreras)
            except json.JSONDecodeError:
                dem_car = None
        if carrera and dem_car and carrera not in dem_car:
            continue
        out.append(
            {
                "plataforma": c.plataforma,
                "termino": c.termino,
                "habilidad_demanda": c.habilidad_demanda,
                "demanda_ofertas": c.demanda_ofertas,
                "demanda_pct": c.demanda_pct,
                "demanda_carreras": dem_car,
                "puntaje_recomendacion": c.puntaje_recomendacion,
                "posicion": c.posicion,
                "titulo": c.titulo,
                "url": c.url,
                "organizacion": c.organizacion,
                "nivel": c.nivel,
                "tipo": c.tipo,
                "calificacion": c.calificacion,
                "num_calificaciones": c.num_calificaciones,
                "inscritos_recientes": c.inscritos_recientes,
                "semestre": c.semestre,
                "corte": c.corte,
                "fecha_extraccion": c.fecha_extraccion.isoformat() if c.fecha_extraccion else None,
            }
        )
    return out


def listar_temas_recomendados(
    s: Session,
    semestre: str,
    corte: str,
    carrera: str | None = None,
    limite: int = 50,
) -> list[dict]:
    from observatorio.cursos_demanda import temas_recomendados_dictado
    from observatorio.parametros import leer_config

    cfg = leer_config(s)
    return temas_recomendados_dictado(s, semestre, corte.capitalize(), cfg, carrera=carrera, limite=limite)
