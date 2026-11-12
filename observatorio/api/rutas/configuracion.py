"""Catálogo y sinónimos, términos de búsqueda, no catalogados y parámetros (RF-01, RF-05, RF-17)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from observatorio.api.seguridad import get_db, solo_admin, usuario_actual
from observatorio.db.modelos import Catalogo, Config, NoCatalogado, Sinonimo, TerminoBusqueda, Usuario
from observatorio.distribucion import FUENTES_EXTRACCION, normalizar_porcentajes, validar_distribucion
from observatorio.parametros import POR_DEFECTO, leer_config
router = APIRouter()


# ----------------------------------------------------------------- catálogo
class SinonimoIn(BaseModel):
    texto: str
    sensible_mayusculas: bool = False
    requiere_contexto: bool = False
    patron_exclusion: str | None = None


class SoftwareIn(BaseModel):
    software: str
    grupo: str
    activo: bool = True
    contexto: str | None = None
    notas: str | None = None
    sinonimos: list[SinonimoIn] | None = None


def _sin(x: Sinonimo) -> dict:
    return {"id": x.id, "texto": x.texto, "sensible_mayusculas": x.sensible_mayusculas,
            "requiere_contexto": x.requiere_contexto, "patron_exclusion": x.patron_exclusion}


def _sw(c: Catalogo) -> dict:
    return {"id": c.id, "software": c.software, "grupo": c.grupo, "activo": c.activo, "contexto": c.contexto,
            "notas": c.notas, "sinonimos": [_sin(x) for x in c.sinonimos]}


def _validar_regex(patron: str | None) -> None:
    import re
    if patron:
        try:
            re.compile(patron)
        except re.error as e:
            raise HTTPException(400, f"El patrón de exclusión no es una expresión regular válida: {e}") from e


@router.get("/catalogo")
def listar_catalogo(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return [_sw(c) for c in s.scalars(select(Catalogo).order_by(Catalogo.grupo, Catalogo.software))]


@router.post("/catalogo")
def crear_software(d: SoftwareIn, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    c = Catalogo(software=d.software.strip(), grupo=d.grupo.strip(), activo=d.activo, contexto=d.contexto, notas=d.notas)
    for x in d.sinonimos or [SinonimoIn(texto=d.software.strip())]:
        _validar_regex(x.patron_exclusion)
        c.sinonimos.append(Sinonimo(**x.model_dump()))
    s.add(c)
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Ya existe un software con ese nombre.") from e
    return _sw(c)


@router.put("/catalogo/{cid}")
def editar_software(cid: int, d: SoftwareIn, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    c = s.get(Catalogo, cid)
    if c is None:
        raise HTTPException(404, "Software no encontrado")
    c.software, c.grupo, c.activo, c.contexto, c.notas = d.software.strip(), d.grupo.strip(), d.activo, d.contexto, d.notas
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Ya existe un software con ese nombre.") from e
    return _sw(c)


@router.delete("/catalogo/{cid}")
def borrar_software(cid: int, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    c = s.get(Catalogo, cid)
    if c is None:
        raise HTTPException(404, "Software no encontrado")
    s.delete(c)
    return {"ok": True, "aviso": "Las ofertas ya procesadas conservan sus detecciones; el cambio aplica desde la próxima ejecución."}


@router.post("/catalogo/{cid}/sinonimos")
def agregar_sinonimo(cid: int, d: SinonimoIn, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    c = s.get(Catalogo, cid)
    if c is None:
        raise HTTPException(404, "Software no encontrado")
    _validar_regex(d.patron_exclusion)
    x = Sinonimo(catalogo_id=cid, **d.model_dump())
    s.add(x)
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Ese sinónimo ya existe para este software.") from e
    return _sin(x)


@router.put("/sinonimos/{sid}")
def editar_sinonimo(sid: int, d: SinonimoIn, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    x = s.get(Sinonimo, sid)
    if x is None:
        raise HTTPException(404, "Sinónimo no encontrado")
    _validar_regex(d.patron_exclusion)
    for k, v in d.model_dump().items():
        setattr(x, k, v)
    return _sin(x)


@router.delete("/sinonimos/{sid}")
def borrar_sinonimo(sid: int, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    x = s.get(Sinonimo, sid)
    if x is None:
        raise HTTPException(404, "Sinónimo no encontrado")
    s.delete(x)
    return {"ok": True}


class TextoPrueba(BaseModel):
    texto: str
    empresa: str = ""


@router.post("/catalogo/probar")
def probar_deteccion(d: TextoPrueba, _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    """Muestra qué softwares detectaría el catálogo actual en un texto (útil para ajustar sinónimos)."""
    from observatorio.pipeline.software import DetectorSoftware

    det = DetectorSoftware.desde_bd(s)
    return [{"software": x.software, "grupo": x.grupo, "texto_encontrado": x.texto_encontrado} for x in det.detectar("", d.texto, d.empresa)]


# ----------------------------------------------------------------- términos
class TerminoIn(BaseModel):
    termino: str
    carrera: str
    tipo: str = "principal"
    fuentes: str | None = None
    activo: bool = True


def _term(t: TerminoBusqueda) -> dict:
    return {"id": t.id, "termino": t.termino, "carrera": t.carrera, "tipo": t.tipo, "fuentes": t.fuentes, "activo": t.activo}


@router.get("/terminos")
def listar_terminos(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return [_term(t) for t in s.scalars(select(TerminoBusqueda).order_by(TerminoBusqueda.carrera, TerminoBusqueda.tipo, TerminoBusqueda.termino))]


def _validar_termino(d: TerminoIn, s: Session) -> None:
    if d.tipo not in ("principal", "ampliado"):
        raise HTTPException(400, "El tipo debe ser 'principal' o 'ampliado'.")
    if d.carrera not in leer_config(s)["carreras"]:
        raise HTTPException(400, "Carrera no configurada. Agréguela primero en Configuración → carreras.")


@router.post("/terminos")
def crear_termino(d: TerminoIn, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    _validar_termino(d, s)
    t = TerminoBusqueda(**{**d.model_dump(), "termino": d.termino.strip()})
    s.add(t)
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Ese término ya existe para esa carrera.") from e
    return _term(t)


@router.put("/terminos/{tid}")
def editar_termino(tid: int, d: TerminoIn, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    t = s.get(TerminoBusqueda, tid)
    if t is None:
        raise HTTPException(404, "Término no encontrado")
    _validar_termino(d, s)
    for k, v in d.model_dump().items():
        setattr(t, k, v.strip() if isinstance(v, str) else v)
    return _term(t)


@router.delete("/terminos/{tid}")
def borrar_termino(tid: int, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    t = s.get(TerminoBusqueda, tid)
    if t is None:
        raise HTTPException(404, "Término no encontrado")
    s.delete(t)
    return {"ok": True}


# ----------------------------------------------------------------- no catalogados
def _nc(x: NoCatalogado) -> dict:
    return {"id": x.id, "termino": x.termino_original, "frecuencia_total": x.frecuencia_total, "frecuencia_ultima": x.frecuencia_ultima,
            "estado": x.estado, "ejemplo_id_oferta": x.ejemplo_id_oferta, "semestre": x.semestre, "corte": x.corte,
            "ultima_vez": x.ultima_vez.isoformat() if x.ultima_vez else None}


@router.get("/no-catalogados")
def listar_nc(estado: str | None = "pendiente", _: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    q = select(NoCatalogado).order_by(NoCatalogado.frecuencia_ultima.desc(), NoCatalogado.frecuencia_total.desc())
    if estado:
        q = q.where(NoCatalogado.estado == estado)
    return [_nc(x) for x in s.scalars(q.limit(500))]


class DecisionNc(BaseModel):
    estado: str  # agregado | descartado | pendiente
    software: str | None = None  # al agregar: nombre en el catálogo (nuevo o existente)
    grupo: str | None = None


@router.put("/no-catalogados/{nid}")
def decidir_nc(nid: int, d: DecisionNc, _: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    x = s.get(NoCatalogado, nid)
    if x is None:
        raise HTTPException(404, "Término no encontrado")
    if d.estado not in ("agregado", "descartado", "pendiente"):
        raise HTTPException(400, "Estado no válido")
    if d.estado == "agregado":
        nombre = (d.software or x.termino_original).strip()
        c = s.scalars(select(Catalogo).where(Catalogo.software == nombre)).one_or_none()
        if c is None:
            if not d.grupo:
                raise HTTPException(400, "Indique el grupo del nuevo software.")
            c = Catalogo(software=nombre, grupo=d.grupo, activo=True)
            s.add(c)
            s.flush()
        if not any(sn.texto.lower() == x.termino_original.lower() for sn in c.sinonimos):
            c.sinonimos.append(Sinonimo(texto=x.termino_original))
    x.estado = d.estado
    return _nc(x)


# ----------------------------------------------------------------- parámetros
class ValorConfig(BaseModel):
    valor: dict | list | int | float | str | bool | None


@router.get("/config")
def ver_config(_: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    cfg = leer_config(s)
    return [{"clave": k, "valor": cfg.get(k), "descripcion": POR_DEFECTO[k]["descripcion"]} for k in POR_DEFECTO]


def _validar_valor_config(clave: str, valor, cfg: dict):
    if clave == "distribucion_fuentes":
        if not isinstance(valor, dict):
            raise HTTPException(400, "distribucion_fuentes debe ser un objeto con porcentajes.")
        try:
            return validar_distribucion(valor, claves=list(FUENTES_EXTRACCION))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    if clave == "distribucion_carreras":
        if not isinstance(valor, dict):
            raise HTTPException(400, "distribucion_carreras debe ser un objeto con porcentajes.")
        carreras = list(cfg.get("carreras") or [])
        try:
            return validar_distribucion(valor, claves=carreras)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    return valor


@router.post("/config/distribucion/normalizar")
def normalizar_distribucion(
    clave: str,
    d: ValorConfig,
    admin: Usuario = Depends(solo_admin),
    s: Session = Depends(get_db),
):
    if clave not in ("distribucion_fuentes", "distribucion_carreras"):
        raise HTTPException(400, "Solo aplican distribucion_fuentes o distribucion_carreras.")
    if not isinstance(d.valor, dict):
        raise HTTPException(400, "El cuerpo debe incluir «valor» como objeto de porcentajes.")
    try:
        normalizado = normalizar_porcentajes(d.valor)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    cfg = leer_config(s)
    claves = list(FUENTES_EXTRACCION) if clave == "distribucion_fuentes" else list(cfg.get("carreras") or [])
    try:
        normalizado = validar_distribucion(normalizado, claves=claves)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    fila = s.get(Config, clave)
    if fila is None:
        fila = Config(clave=clave, descripcion=POR_DEFECTO[clave]["descripcion"])
        s.add(fila)
    fila.valor = normalizado
    fila.actualizado_por = admin.email
    s.commit()
    return {"clave": clave, "valor": normalizado}


@router.put("/config/{clave}")
def editar_config(clave: str, d: ValorConfig, admin: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    if clave not in POR_DEFECTO:
        raise HTTPException(404, "Parámetro desconocido")
    esperado = type(POR_DEFECTO[clave]["valor"])
    if not isinstance(d.valor, esperado) and not (esperado is int and isinstance(d.valor, float)):
        raise HTTPException(400, f"El valor debe ser de tipo {esperado.__name__} (como el valor por defecto).")
    cfg = leer_config(s)
    d.valor = _validar_valor_config(clave, d.valor, cfg)
    fila = s.get(Config, clave)
    if fila is None:
        fila = Config(clave=clave, descripcion=POR_DEFECTO[clave]["descripcion"])
        s.add(fila)
    fila.valor = d.valor
    fila.actualizado_por = admin.email
    return {"clave": clave, "valor": fila.valor}
