"""Autenticación: Google (solo @unal.edu.co), sesión JWT propia y tokens MCP."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterator

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.config import ajustes
from observatorio.db.modelos import TokenMcp, Usuario, ahora
from observatorio.db.sesion import fabrica_sesiones

ALGORITMO = "HS256"
PREFIJO_TOKEN_MCP = "obs_"


def get_db() -> Iterator[Session]:
    s = fabrica_sesiones()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _secreto() -> str:
    secreto = ajustes().jwt_secret
    if not secreto:
        raise HTTPException(500, "Falta configurar JWT_SECRET en el servidor.")
    return secreto


def verificar_google(credencial: str) -> dict:
    """Verifica el ID token de Google Identity Services y devuelve sus datos."""
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    client_id = ajustes().google_client_id
    if not client_id:
        raise HTTPException(500, "Falta configurar GOOGLE_CLIENT_ID en el servidor.")
    try:
        return id_token.verify_oauth2_token(credencial, g_requests.Request(), client_id)
    except ValueError as e:
        raise HTTPException(401, f"No se pudo verificar el inicio de sesión con Google: {e}") from e


def correo_permitido(datos: dict) -> str:
    email = (datos.get("email") or "").lower()
    dominio = ajustes().dominio_permitido
    if not datos.get("email_verified", False):
        raise HTTPException(403, "El correo de Google no está verificado.")
    if not email.endswith("@" + dominio):
        raise HTTPException(403, f"Solo se permiten cuentas @{dominio}.")
    return email


def registrar_ingreso(s: Session, email: str, nombre: str | None = None) -> Usuario:
    """Crea el usuario si no existe. Los nuevos quedan pendientes hasta que un admin los apruebe."""
    u = s.scalars(select(Usuario).where(Usuario.email == email)).one_or_none()
    if u is None:
        es_admin = email in ajustes().admins_iniciales
        u = Usuario(email=email, nombre=nombre, rol="admin" if es_admin else "usuario",
                    estado="aprobado" if es_admin else "pendiente", aprobado_por="semilla" if es_admin else None)
        s.add(u)
    elif email in ajustes().admins_iniciales and (u.rol != "admin" or u.estado != "aprobado"):
        u.rol, u.estado = "admin", "aprobado"  # los admins iniciales no se pueden bloquear por error
    if nombre and not u.nombre:
        u.nombre = nombre
    u.ultimo_acceso = ahora()
    s.flush()
    return u


def crear_jwt(u: Usuario) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=ajustes().jwt_horas)
    return jwt.encode({"sub": u.email, "rol": u.rol, "exp": exp}, _secreto(), algorithm=ALGORITMO)


def usuario_actual(authorization: str | None = Header(default=None), s: Session = Depends(get_db)) -> Usuario:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicie sesión para continuar.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        datos = jwt.decode(token, _secreto(), algorithms=[ALGORITMO])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(401, "La sesión expiró. Inicie sesión de nuevo.") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, "Sesión no válida.") from e
    u = s.scalars(select(Usuario).where(Usuario.email == datos.get("sub"))).one_or_none()
    if u is None:
        raise HTTPException(401, "Usuario no encontrado.")
    if u.estado != "aprobado":
        raise HTTPException(403, "Su cuenta está pendiente de aprobación por un administrador.")
    return u


def solo_admin(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != "admin":
        raise HTTPException(403, "Solo los administradores pueden hacer esto.")
    return u


# ---------------------------------------------------------------------------
# Tokens personales para el servidor MCP (solo administradores)
# ---------------------------------------------------------------------------
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generar_token_mcp(s: Session, email: str, nombre: str) -> tuple[str, TokenMcp]:
    token = PREFIJO_TOKEN_MCP + secrets.token_urlsafe(32)
    fila = TokenMcp(email=email, nombre=nombre[:120] or "Token MCP", hash=hash_token(token), prefijo=token[:10])
    s.add(fila)
    s.flush()
    return token, fila


def usuario_por_token_mcp(s: Session, token: str | None) -> Usuario | None:
    """Devuelve el usuario dueño del token si es válido, no revocado y sigue aprobado (hereda su rol en el MCP)."""
    if not token or not token.startswith(PREFIJO_TOKEN_MCP):
        return None
    fila = s.scalars(select(TokenMcp).where(TokenMcp.hash == hash_token(token))).one_or_none()
    if fila is None or fila.revocado:
        return None
    u = s.scalars(select(Usuario).where(Usuario.email == fila.email)).one_or_none()
    if u is None or u.estado != "aprobado":
        return None
    fila.ultimo_uso = ahora()
    s.commit()
    return u


def admin_por_token_mcp(s: Session, token: str | None) -> Usuario | None:
    """Compatibilidad: solo si el token pertenece a un administrador aprobado."""
    u = usuario_por_token_mcp(s, token)
    return u if u is not None and u.rol == "admin" else None
