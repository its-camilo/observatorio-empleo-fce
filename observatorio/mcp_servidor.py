"""Servidor MCP remoto del Observatorio (HTTP "streamable", ruta /mcp).

- Público y de SOLO LECTURA para cualquiera, sin iniciar sesión: ofertas,
  rankings, comparación entre cortes, catálogo, ejecuciones, cursos y resúmenes.
  No expone usuarios, validaciones, tokens ni configuración interna.
- Herramientas de administración (lanzar_corrida, estado_corrida) solo con un
  token personal de administrador (cabecera `Authorization: Bearer obs_...`),
  generado y revocado en el aplicativo (página "Tokens MCP"). Sin token válido
  esas herramientas ni siquiera aparecen en la lista.
- Límite básico de solicitudes por IP y topes en los resultados.

Se implementa con el SDK oficial de Python (`mcp`, MCPServer) en modo sin
estado (stateless) y respuestas JSON: cada solicitud HTTP es independiente,
lo que funciona tanto en Vercel (funciones serverless) como en servidor propio.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from observatorio import analisis
from observatorio.consultas import buscar_ofertas, catalogo_publico, listar_cursos, oferta_resumen, valores_filtros
from observatorio.db.sesion import fabrica_sesiones

log = logging.getLogger("observatorio.mcp")

MAX_OFERTAS_POR_PAGINA = 50
MAX_DESCRIPCION = 2000
MAX_RANKING = 50
MAX_CURSOS = 100
MAX_EJECUCIONES = 50
HERRAMIENTAS_ADMIN = {"lanzar_corrida", "estado_corrida"}

# Correo del admin autenticado en la solicitud actual (None = anónimo, solo lectura)
_admin_actual: ContextVar[str | None] = ContextVar("mcp_admin_actual", default=None)


# ---------------------------------------------------------------------------
# Límite de solicitudes por IP (ventana deslizante en memoria, por instancia)
# ---------------------------------------------------------------------------
class LimitadorPorIp:
    def __init__(self, por_minuto: int = 60):
        self.por_minuto = por_minuto
        self._ventanas: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, ip: str) -> bool:
        ahora = time.monotonic()
        with self._lock:
            v = self._ventanas[ip]
            while v and ahora - v[0] > 60:
                v.popleft()
            if len(v) >= self.por_minuto:
                return False
            v.append(ahora)
            if len(self._ventanas) > 10_000:  # evitar crecer sin límite
                self._ventanas.clear()
            return True


def _corte(c: str | None) -> str | None:
    if not c:
        return None
    c = c.strip().capitalize()
    if c not in ("Inicio", "Mitad", "Final"):
        raise ToolError("El corte debe ser Inicio, Mitad o Final.")
    return c


def _requiere_admin() -> str:
    email = _admin_actual.get()
    if not email:
        raise ToolError("Esta herramienta requiere un token de administrador del Observatorio (Authorization: Bearer obs_...).")
    return email


class ServidorObservatorio(MCPServer):
    """MCPServer que oculta las herramientas de administración a quien no tiene token válido."""

    async def list_tools(self):
        herramientas = await super().list_tools()
        if _admin_actual.get() is None:
            herramientas = [h for h in herramientas if h.name not in HERRAMIENTAS_ADMIN]
        return herramientas

    async def call_tool(self, name: str, arguments: dict[str, Any], context=None, *args, **kwargs):
        if name in HERRAMIENTAS_ADMIN and _admin_actual.get() is None:
            raise ToolError(f"Herramienta desconocida o no autorizada: {name}")
        return await super().call_tool(name, arguments, context, *args, **kwargs)


def construir_servidor() -> ServidorObservatorio:
    mcp = ServidorObservatorio(
        name="observatorio-empleo-fce",
        title="Observatorio de Empleo FCE (UNAL)",
        version="1.0.0",
        instructions=(
            "Datos públicos del Observatorio de Empleo de la Facultad de Ciencias Económicas de la Universidad Nacional "
            "de Colombia: ofertas de empleo y práctica para Administración de Empresas, Contaduría Pública y Economía, "
            "softwares que piden, rankings por carrera y corte (semestre como 2026-II; corte Inicio, Mitad o Final), "
            "comparación entre cortes y cursos en tendencia. Empiece con listar_cortes o resumen_corte."
        ),
    )

    @mcp.tool()
    def listar_cortes() -> list[dict]:
        """Lista los cortes con datos (semestre, corte y número de ofertas), del más antiguo al más reciente."""
        with fabrica_sesiones()() as s:
            return analisis.cortes_disponibles(s)

    @mcp.tool()
    def valores_filtro() -> dict:
        """Valores posibles para los filtros: semestres, fuentes, ciudades, carreras, softwares, tipos de oferta, niveles."""
        with fabrica_sesiones()() as s:
            return valores_filtros(s)

    @mcp.tool()
    def buscar_ofertas_empleo(carrera: str | None = None, semestre: str | None = None, corte: str | None = None,
                              fuente: str | None = None, ciudad: str | None = None, software: str | None = None,
                              texto: str | None = None, tipo_oferta: str | None = None, pagina: int = 1,
                              tamano: int = 20, incluir_descripcion: bool = False) -> dict:
        """Busca ofertas con filtros (todos opcionales) y paginación. tamano máximo 50.

        carrera: "Administración de Empresas", "Contaduría Pública" o "Economía". software: nombre del catálogo (p. ej. "Power BI").
        texto: busca en cargo, empresa y descripción. incluir_descripcion: añade la descripción (recortada a 2000 caracteres).
        """
        with fabrica_sesiones()() as s:
            return buscar_ofertas(s, pagina=max(1, pagina), tamano=max(1, min(tamano, MAX_OFERTAS_POR_PAGINA)),
                                  con_descripcion=incluir_descripcion, max_desc=MAX_DESCRIPCION, semestre=semestre,
                                  corte=_corte(corte), carrera=carrera, fuente=fuente, ciudad=ciudad, software=software,
                                  texto=texto, tipo_oferta=tipo_oferta)

    @mcp.tool()
    def ver_oferta(id_oferta: str) -> dict:
        """Detalle de una oferta (descripción recortada a 2000 caracteres y softwares detectados con el texto encontrado)."""
        from observatorio.db.modelos import Oferta
        with fabrica_sesiones()() as s:
            o = s.get(Oferta, id_oferta)
            if o is None:
                raise ToolError("Oferta no encontrada")
            return oferta_resumen(o, con_descripcion=True, max_desc=MAX_DESCRIPCION)

    @mcp.tool()
    def ranking_software(semestre: str, corte: str, carrera: str | None = None, limite: int = 20) -> dict:
        """Ranking de softwares pedidos en un corte: posición, número y % de ofertas, y variación (puntos porcentuales)
        frente al corte anterior. Sin carrera = todas las ofertas. limite máximo 50."""
        with fabrica_sesiones()() as s:
            c = _corte(corte)
            return {"ranking": analisis.ranking(s, semestre, c, carrera)[:max(1, min(limite, MAX_RANKING))],
                    "por_grupo": analisis.ranking_por_grupo(s, semestre, c, carrera)}

    @mcp.tool()
    def comparar_cortes(semestre_a: str, corte_a: str, semestre_b: str, corte_b: str, carrera: str | None = None,
                        limite: int = 30) -> dict:
        """Compara dos cortes (A anterior, B posterior): por software indica subió, bajó, igual, nuevo o desapareció,
        con advertencias si cambiaron fuentes o términos de búsqueda. limite máximo 50."""
        with fabrica_sesiones()() as s:
            r = analisis.comparar(s, semestre_a, _corte(corte_a), semestre_b, _corte(corte_b), carrera)
            r["softwares"] = r["softwares"][:max(1, min(limite, MAX_RANKING))]
            return r

    @mcp.tool()
    def resumen_corte(semestre: str, corte: str) -> dict:
        """Resumen de un corte: total de ofertas, por fuente, carrera, ciudad, tipo, modalidad, nivel y top 10 de softwares."""
        with fabrica_sesiones()() as s:
            return analisis.resumen_corte(s, semestre, _corte(corte))

    @mcp.tool()
    def listar_catalogo(incluir_inactivos: bool = False) -> list[dict]:
        """Catálogo de softwares que se detectan, con su grupo y sinónimos."""
        with fabrica_sesiones()() as s:
            return catalogo_publico(s, solo_activos=not incluir_inactivos)

    @mcp.tool()
    def listar_ejecuciones(semestre: str | None = None, limite: int = 20) -> list[dict]:
        """Ejecuciones (corridas) registradas: fecha, semestre, corte, fuentes, ofertas encontradas, duplicados, estado y errores."""
        from sqlalchemy import select

        from observatorio.db.modelos import Ejecucion
        with fabrica_sesiones()() as s:
            q = select(Ejecucion).order_by(Ejecucion.creado_en.desc()).limit(max(1, min(limite, MAX_EJECUCIONES)))
            if semestre:
                q = q.where(Ejecucion.semestre == semestre)
            return [{"id_ejecucion": e.id_ejecucion, "fecha": e.fecha.isoformat() if e.fecha else None, "semestre": e.semestre,
                     "corte": e.corte, "fuentes": e.fuentes, "estado": e.estado, "ofertas_encontradas": e.ofertas_encontradas,
                     "ofertas_guardadas": e.ofertas_guardadas, "duplicados_eliminados": e.duplicados_eliminados,
                     "total_corte": e.total_corte, "errores": e.errores, "duracion_segundos": e.duracion_segundos}
                    for e in s.scalars(q)]

    @mcp.tool()
    def listar_cursos_tendencia(semestre: str | None = None, corte: str | None = None, plataforma: str | None = None,
                                termino: str | None = None, limite: int = 30) -> list[dict]:
        """Cursos en tendencia (Coursera, edX, Platzi) por término de búsqueda. limite máximo 100."""
        with fabrica_sesiones()() as s:
            return listar_cursos(s, semestre, _corte(corte), plataforma, termino, limite=max(1, min(limite, MAX_CURSOS)))

    # ------------------------------------------------------------- administración
    @mcp.tool()
    def lanzar_corrida(semestre: str, corte: str, modo: str = "completa") -> dict:
        """[Solo administradores] Lanza una corrida normal en GitHub Actions. semestre: p. ej. 2026-II;
        corte: inicio, mitad o final; modo: completa o prueba. Devuelve el id de ejecución para estado_corrida."""
        email = _requiere_admin()
        from observatorio.corridas import ErrorCorrida, ejecucion_dict, lanzar
        with fabrica_sesiones()() as s:
            try:
                e = lanzar(s, semestre, corte, f"{email} (MCP)", modo)
            except (ErrorCorrida, ValueError) as ex:
                raise ToolError(str(ex)) from ex
            return {"mensaje": "Corrida enviada a GitHub Actions.", **ejecucion_dict(e)}

    @mcp.tool()
    def estado_corrida(run_id: str) -> dict:
        """[Solo administradores] Estado y progreso de una corrida (consultas hechas por fuente, ofertas, reporte final)."""
        _requiere_admin()
        from observatorio.corridas import ejecucion_dict, progreso
        from observatorio.db.modelos import Ejecucion
        with fabrica_sesiones()() as s:
            e = s.get(Ejecucion, run_id)
            if e is None:
                raise ToolError("No existe esa ejecución.")
            d = ejecucion_dict(e)
            d.pop("terminos_usados", None)
            return {**d, "progreso": progreso(s, e, consultar_github=True)}

    return mcp


class AppMcp:
    """Aplicación ASGI para montar en /mcp: límite por IP, token admin opcional y transporte HTTP sin estado."""

    def __init__(self, por_minuto: int | None = None):
        self.servidor = construir_servidor()
        self.limitador = LimitadorPorIp(por_minuto or int(os.getenv("MCP_LIMITE_POR_MINUTO", "60")))
        self.seguridad = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    @staticmethod
    def _cabecera(scope, nombre: bytes) -> str | None:
        for k, v in scope.get("headers") or []:
            if k.lower() == nombre:
                return v.decode("latin-1")
        return None

    async def _responder(self, send, codigo: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": codigo,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"retry-after", b"60")]})
        await send({"type": "http.response.body", "body": datos})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return
        reenviada = self._cabecera(scope, b"x-forwarded-for")
        ip = (reenviada.split(",")[0].strip() if reenviada else (scope.get("client") or ("?",))[0])
        if not self.limitador.permitir(ip):
            await self._responder(send, 429, {"error": "Demasiadas solicitudes. Espere un minuto e intente de nuevo."})
            return
        email = None
        auth = self._cabecera(scope, b"authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

            def verificar() -> str | None:
                from observatorio.api.seguridad import admin_por_token_mcp
                with fabrica_sesiones()() as s:
                    u = admin_por_token_mcp(s, token)
                    return u.email if u else None
            email = await anyio.to_thread.run_sync(verificar)
        marca = _admin_actual.set(email)
        try:
            gestor = StreamableHTTPSessionManager(app=self.servidor._lowlevel_server, stateless=True, json_response=True,
                                                  security_settings=self.seguridad)
            async with gestor.run():
                await gestor.handle_request(scope, receive, send)
        finally:
            _admin_actual.reset(marca)
