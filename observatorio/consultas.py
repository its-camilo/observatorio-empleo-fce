"""Consultas de solo lectura compartidas por la API y el servidor MCP."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Catalogo, Curso, Oferta, OfertaSoftware


def filtrar_ofertas(q, semestre=None, corte=None, carrera=None, fuente=None, ciudad=None, software=None, tipo_oferta=None,
                    nivel=None, modalidad=None, texto=None):
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


def buscar_ofertas(s: Session, pagina: int = 1, tamano: int = 25, con_descripcion: bool = False, max_desc: int | None = None,
                   **filtros) -> dict:
    q = filtrar_ofertas(select(Oferta), **filtros)
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
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


def listar_cursos(s: Session, semestre=None, corte=None, plataforma=None, termino=None, limite: int = 100) -> list[dict]:
    q = select(Curso)
    if semestre:
        q = q.where(Curso.semestre == semestre)
    if corte:
        q = q.where(Curso.corte == corte.capitalize())
    if plataforma:
        q = q.where(Curso.plataforma == plataforma)
    if termino:
        q = q.where(Curso.termino.ilike(f"%{termino}%"))
    q = q.order_by(Curso.fecha_extraccion.desc(), Curso.termino, Curso.plataforma, Curso.posicion).limit(limite)
    return [{"plataforma": c.plataforma, "termino": c.termino, "posicion": c.posicion, "titulo": c.titulo, "url": c.url,
             "organizacion": c.organizacion, "nivel": c.nivel, "tipo": c.tipo, "calificacion": c.calificacion,
             "num_calificaciones": c.num_calificaciones, "inscritos_recientes": c.inscritos_recientes,
             "semestre": c.semestre, "corte": c.corte, "fecha_extraccion": c.fecha_extraccion.isoformat() if c.fecha_extraccion else None}
            for c in s.scalars(q)]
