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


MODELOS_OPENROUTER_POR_DEFECTO = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "qwen/qwen3-235b-a22b:free",
]


def _lista(valor: str) -> list[str]:
    return [x.strip() for x in (valor or "").split(",") if x.strip()]


def _bool(valor: str | None) -> bool:
    return str(valor or "").strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


def normalizar_url_bd(url: str) -> str:
    """Neon/Heroku entregan a veces `postgres://`; SQLAlchemy necesita `postgresql://`."""
    if not url:
        return "sqlite:///./observatorio_local.db"
    # SQLAlchemy 2.1 usa psycopg (v3) por defecto para `postgresql://`;
    # el proyecto instala psycopg2-binary, así que se fija el driver.
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            url = "postgresql+psycopg2://" + url[len(prefijo):]
    return url


@dataclass
class Ajustes:
    database_url: str = ""
    openrouter_api_key: str = ""
    openrouter_modelos: list[str] = field(default_factory=list)
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
        openrouter_modelos=_lista(os.getenv("OPENROUTER_MODELS", "")) or list(MODELOS_OPENROUTER_POR_DEFECTO),
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
