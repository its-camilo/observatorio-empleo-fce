"""Ajustes del aplicativo leídos desde variables de entorno.

Los parámetros funcionales (fuentes, ubicaciones, límites, reglas de carrera,
etc.) NO viven aquí: están en la tabla `config` de la base de datos y se
editan desde el aplicativo (RF-01). Aquí solo van secretos y conexiones.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # .env opcional para uso local
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# Único endpoint grativo documentado por OpenRouter para clasificación.
# https://openrouter.ai/openrouter/free
MODELO_OPENROUTER_GRATIS = "openrouter/free"


def _lista(valor: str) -> list[str]:
    return [x.strip() for x in (valor or "").split(",") if x.strip()]


def _bool(valor: str | None) -> bool:
    return str(valor or "").strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


def _preferir_pooler_neon(url: str) -> str:
    """En serverless, Neon recomienda el host con sufijo `-pooler` (PgBouncer)."""
    if os.getenv("NEON_POOLER", "1").strip().lower() in {"0", "false", "no"}:
        return url
    if "neon.tech" not in url or "-pooler." in url:
        return url
    host_start = url.find("@")
    if host_start == -1:
        return url
    rest = url[host_start + 1 :]
    slash = rest.find("/")
    host = rest if slash == -1 else rest[:slash]
    suffix = rest[len(host) :]
    if "-pooler." in host:
        return url
    partes = host.split(".", 1)
    if len(partes) < 2:
        return url
    nuevo_host = f"{partes[0]}-pooler.{partes[1]}"
    return url[: host_start + 1] + nuevo_host + suffix


def normalizar_url_bd(url: str) -> str:
    """Neon/Heroku entregan a veces `postgres://`; SQLAlchemy necesita `postgresql://`."""
    # Una URL nunca lleva espacios; al pegarla en un formulario a veces se cuelan
    # saltos de línea o espacios (p. ej. en el secreto de GitHub o Vercel).
    url = "".join(url.split())
    if not url:
        return "sqlite:///./observatorio_local.db"
    # SQLAlchemy 2.1 usa psycopg (v3) por defecto para `postgresql://`;
    # el proyecto instala psycopg2-binary, así que se fija el driver.
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            url = "postgresql+psycopg2://" + url[len(prefijo):]
    if url.startswith("postgresql") and os.getenv("VERCEL"):
        url = _preferir_pooler_neon(url)
    return url


@dataclass
class Ajustes:
    database_url: str = ""
    openrouter_api_key: str = ""
    google_client_id: str = ""
    dominio_permitido: str = "unal.edu.co"
    admins_iniciales: list[str] = field(default_factory=list)
    jwt_secret: str = ""
    jwt_horas: int = 12
    github_token: str = ""
    github_repo: str = ""
    github_workflow: str = "corrida.yml"
    github_ref: str = "main"
    proxies: list[str] = field(default_factory=list)
    csv_token: str = ""
    auth_dev_mode: bool = False


def ajustes() -> Ajustes:
    """Lee el entorno en cada llamada (barato y amigable con las pruebas)."""
    return Ajustes(
        database_url=normalizar_url_bd(os.getenv("DATABASE_URL", "")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        dominio_permitido=os.getenv("DOMINIO_PERMITIDO", "unal.edu.co").lstrip("@").lower(),
        admins_iniciales=[e.lower() for e in _lista(
            os.getenv("ADMINS_INICIALES", "uniic_bog@unal.edu.co,clagosm@unal.edu.co"))],
        jwt_secret=os.getenv("JWT_SECRET", ""),
        jwt_horas=int(os.getenv("JWT_HORAS", "12") or 12),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_repo=os.getenv("GITHUB_REPO", ""),
        github_workflow=os.getenv("GITHUB_WORKFLOW", "corrida.yml"),
        github_ref=os.getenv("GITHUB_REF", "main"),
        proxies=_lista(os.getenv("PROXIES", "")),
        csv_token=os.getenv("CSV_TOKEN", ""),
        auth_dev_mode=_bool(os.getenv("AUTH_DEV_MODE")),
    )
