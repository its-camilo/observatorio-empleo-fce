"""API del Observatorio (FastAPI). Rutas bajo /api y servidor MCP remoto en /mcp.

Despliegue:
- Vercel: api/index.py importa `app` (ver vercel.json).
- Servidor propio: `uvicorn observatorio.api.main:app` (Dockerfile / docker-compose);
  si existe web/dist, también sirve el front.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.routing import Route

from observatorio import __version__
from observatorio.api.rutas import auth_usuarios, configuracion, datos
from observatorio.config import ajustes

log = logging.getLogger("observatorio.api")
for _ruidoso in ("mcp", "mcp.server", "mcp.server.streamable_http_manager", "httpx"):
    logging.getLogger(_ruidoso).setLevel(logging.WARNING)


def _preparar_bd() -> None:
    """En SQLite (local) crea las tablas; siempre carga la semilla idempotente."""
    from observatorio.db.semilla import sembrar_todo
    from observatorio.db.sesion import crear_tablas, fabrica_sesiones

    try:
        if ajustes().database_url.startswith("sqlite"):
            crear_tablas()
        with fabrica_sesiones()() as s:
            sembrar_todo(s)
            s.commit()
    except Exception as e:  # noqa: BLE001 - la API arranca aunque la BD aún no esté migrada
        log.warning("No se pudo preparar la base de datos (¿falta ejecutar 'python -m observatorio.run migrar'?): %s", e)


def crear_app() -> FastAPI:
    app = FastAPI(title="Observatorio de Empleo FCE", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json",
                  description="API del Observatorio de Empleo de la Facultad de Ciencias Económicas (UNAL).")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["Content-Disposition", "Mcp-Session-Id"])
    for r in (auth_usuarios.router, configuracion.router, datos.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/salud")
    def salud():
        return {"ok": True, "version": __version__}

    @app.exception_handler(ValueError)
    async def error_valor(_: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    # Servidor MCP remoto (solo lectura + herramientas de admin con token)
    from observatorio.mcp_servidor import AppMcp

    mcp_app = AppMcp()
    app.router.routes.append(Route("/mcp", endpoint=mcp_app, methods=["GET", "POST", "DELETE"]))
    app.router.routes.append(Route("/mcp/", endpoint=mcp_app, methods=["GET", "POST", "DELETE"]))

    # Front compilado (solo en servidor propio; en Vercel lo sirve la CDN)
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if dist.is_dir():
        @app.get("/{ruta:path}", include_in_schema=False)
        def front(ruta: str):
            archivo = (dist / ruta).resolve()
            if ruta and archivo.is_file() and dist in archivo.parents:
                return FileResponse(archivo)
            return FileResponse(dist / "index.html")

    _preparar_bd()
    return app


app = crear_app()
