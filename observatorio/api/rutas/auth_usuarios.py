"""Inicio de sesión, usuarios y tokens MCP."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.api.seguridad import (
    correo_permitido, crear_jwt, generar_token_mcp, get_db, registrar_ingreso, solo_admin, usuario_actual, verificar_google,
)
from observatorio.config import ajustes
from observatorio.db.modelos import TokenMcp, Usuario

router = APIRouter()


class CredencialGoogle(BaseModel):
    credential: str


class IngresoDev(BaseModel):
    email: str


def _usuario(u: Usuario) -> dict:
    return {"id": u.id, "email": u.email, "nombre": u.nombre, "rol": u.rol, "estado": u.estado,
            "creado_en": u.creado_en.isoformat() if u.creado_en else None,
            "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None}


def _respuesta_ingreso(u: Usuario) -> dict:
    if u.estado != "aprobado":
        raise HTTPException(403, "Su cuenta quedó registrada y está pendiente de aprobación por un administrador.")
    return {"token": crear_jwt(u), "usuario": _usuario(u)}


@router.get("/auth/config")
def config_auth():
    a = ajustes()
    return {"google_client_id": a.google_client_id, "dominio": a.dominio_permitido, "modo_dev": a.auth_dev_mode}


@router.post("/auth/google")
def ingresar_google(datos: CredencialGoogle, s: Session = Depends(get_db)):
    info = verificar_google(datos.credential)
    email = correo_permitido(info)
    u = registrar_ingreso(s, email, info.get("name"))
    s.commit()
    return _respuesta_ingreso(u)


@router.post("/auth/dev")
def ingresar_dev(datos: IngresoDev, s: Session = Depends(get_db)):
    """Solo desarrollo local (AUTH_DEV_MODE=true). Nunca en producción."""
    if not ajustes().auth_dev_mode:
        raise HTTPException(404, "No disponible")
    email = correo_permitido({"email": datos.email, "email_verified": True})
    u = registrar_ingreso(s, email)
    s.commit()
    return _respuesta_ingreso(u)


@router.get("/auth/yo")
def yo(u: Usuario = Depends(usuario_actual)):
    return _usuario(u)


# ----------------------------------------------------------------- usuarios
class CambioUsuario(BaseModel):
    rol: str | None = None
    estado: str | None = None


@router.get("/usuarios")
def listar_usuarios(_: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    return [_usuario(u) for u in s.scalars(select(Usuario).order_by(Usuario.estado.desc(), Usuario.email))]


@router.put("/usuarios/{uid}")
def cambiar_usuario(uid: int, datos: CambioUsuario, admin: Usuario = Depends(solo_admin), s: Session = Depends(get_db)):
    u = s.get(Usuario, uid)
    if u is None:
        raise HTTPException(404, "Usuario no encontrado")
    if u.email in ajustes().admins_iniciales and (datos.rol not in (None, "admin") or datos.estado not in (None, "aprobado")):
        raise HTTPException(400, "Los administradores iniciales no se pueden degradar ni bloquear.")
    if datos.rol:
        if datos.rol not in ("admin", "usuario"):
            raise HTTPException(400, "Rol no válido")
        u.rol = datos.rol
    if datos.estado:
        if datos.estado not in ("pendiente", "aprobado", "rechazado"):
            raise HTTPException(400, "Estado no válido")
        u.estado = datos.estado
        if datos.estado == "aprobado":
            u.aprobado_por = admin.email
    return _usuario(u)


# ----------------------------------------------------------------- tokens MCP
class NuevoToken(BaseModel):
    nombre: str = "Token MCP"


def _token(t: TokenMcp) -> dict:
    return {"id": t.id, "nombre": t.nombre, "prefijo": t.prefijo, "revocado": t.revocado,
            "creado_en": t.creado_en.isoformat() if t.creado_en else None,
            "ultimo_uso": t.ultimo_uso.isoformat() if t.ultimo_uso else None}


@router.get("/tokens-mcp")
def listar_tokens(u: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    return [_token(t) for t in s.scalars(select(TokenMcp).where(TokenMcp.email == u.email).order_by(TokenMcp.id.desc()))]


@router.post("/tokens-mcp")
def crear_token(datos: NuevoToken, u: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    token, fila = generar_token_mcp(s, u.email, datos.nombre)
    s.commit()
    return {**_token(fila), "token": token,
            "aviso": "Copie el token ahora: no se volverá a mostrar. Se guarda solo su huella (hash). Hereda su rol "
                     f"({'administrador' if u.rol == 'admin' else 'solo lectura'} en el MCP)."}


@router.delete("/tokens-mcp/{tid}")
def revocar_token(tid: int, u: Usuario = Depends(usuario_actual), s: Session = Depends(get_db)):
    t = s.get(TokenMcp, tid)
    if t is None or t.email != u.email:
        raise HTTPException(404, "Token no encontrado")
    t.revocado = True
    return _token(t)
