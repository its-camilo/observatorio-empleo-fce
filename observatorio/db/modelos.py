"""Modelos de base de datos (SQLAlchemy 2).

Las tablas `ofertas`, `oferta_software`, `catalogo` y `ejecuciones` siguen el
diccionario de datos de la sección 9 del documento de requerimientos. Las
columnas extra (marcadas "interno") sirven para trazabilidad y deduplicación y
van siempre al final, para que Power BI no se rompa si se agregan más.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Ejecucion(Base):
    """Tabla "Ejecuciones" (sec. 9.3, RF-09, RF-15, RF-16)."""

    __tablename__ = "ejecuciones"

    id_ejecucion: Mapped[str] = mapped_column(String(64), primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, default=lambda: ahora().date())
    semestre: Mapped[str] = mapped_column(String(16), index=True)
    corte: Mapped[str] = mapped_column(String(16), index=True)
    ejecutado_por: Mapped[str | None] = mapped_column(String(255))
    fuentes: Mapped[str | None] = mapped_column(String(255))
    ofertas_encontradas: Mapped[int] = mapped_column(Integer, default=0)
    duplicados_eliminados: Mapped[int] = mapped_column(Integer, default=0)
    errores: Mapped[str | None] = mapped_column(Text)
    # --- interno / reporte ---
    estado: Mapped[str] = mapped_column(String(20), default="en_cola")  # en_cola, en_curso, completada, incompleta, fallida
    modo: Mapped[str] = mapped_column(String(20), default="completa")  # completa, prueba
    # github: GitHub Actions (aplicativo o MCP) | local: CLI en un computador (si la IP del servidor está bloqueada)
    ejecutor: Mapped[str] = mapped_column(String(20), default="github", index=True)
    parametros: Mapped[dict | None] = mapped_column(JSON)  # límites opcionales (prueba), fuentes elegidas
    duplicados_proceso: Mapped[int] = mapped_column(Integer, default=0)
    ofertas_relevantes: Mapped[int] = mapped_column(Integer, default=0)
    ofertas_guardadas: Mapped[int] = mapped_column(Integer, default=0)
    no_relevantes: Mapped[int] = mapped_column(Integer, default=0)
    total_corte: Mapped[int] = mapped_column(Integer, default=0)
    meta_ofertas: Mapped[int] = mapped_column(Integer, default=10000)
    mini_corrida: Mapped[bool] = mapped_column(Boolean, default=False)
    conteo_por_fuente: Mapped[dict | None] = mapped_column(JSON)
    conteo_por_carrera: Mapped[dict | None] = mapped_column(JSON)
    errores_detalle: Mapped[list | None] = mapped_column(JSON)
    terminos_usados: Mapped[list | None] = mapped_column(JSON)
    uso_llm: Mapped[dict | None] = mapped_column(JSON)
    duracion_segundos: Mapped[int] = mapped_column(Integer, default=0)
    inicio: Mapped[datetime | None] = mapped_column(DateTime)
    fin: Mapped[datetime | None] = mapped_column(DateTime)
    fase: Mapped[str | None] = mapped_column(String(40))
    github_run_url: Mapped[str | None] = mapped_column(String(500))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Oferta(Base):
    """Tabla "Ofertas" (sec. 9.1): una fila por oferta única."""

    __tablename__ = "ofertas"

    id_oferta: Mapped[str] = mapped_column(String(120), primary_key=True)
    fuente: Mapped[str] = mapped_column(String(40), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    fecha_publicacion: Mapped[date | None] = mapped_column(Date)
    fecha_extraccion: Mapped[date] = mapped_column(Date)
    semestre: Mapped[str] = mapped_column(String(16), index=True)
    corte: Mapped[str] = mapped_column(String(16), index=True)
    cargo: Mapped[str] = mapped_column(String(500))
    empresa: Mapped[str | None] = mapped_column(String(500))
    sector: Mapped[str | None] = mapped_column(String(255))
    ciudad: Mapped[str | None] = mapped_column(String(120), index=True)
    modalidad: Mapped[str | None] = mapped_column(String(40))
    tipo_oferta: Mapped[str | None] = mapped_column(String(40))
    nivel_experiencia: Mapped[str | None] = mapped_column(String(60))
    carrera: Mapped[str | None] = mapped_column(String(255))
    termino_busqueda: Mapped[str | None] = mapped_column(String(255))
    descripcion: Mapped[str | None] = mapped_column(Text)
    num_softwares: Mapped[int] = mapped_column(Integer, default=0)
    idiomas: Mapped[str | None] = mapped_column(String(255))
    # --- interno ---
    carrera_principal: Mapped[str | None] = mapped_column(String(120), index=True)
    habilidades_blandas: Mapped[str | None] = mapped_column(Text)
    id_ejecucion: Mapped[str | None] = mapped_column(String(64), ForeignKey("ejecuciones.id_ejecucion"), index=True)
    id_fuente: Mapped[str | None] = mapped_column(String(120))
    clave_dedup: Mapped[str | None] = mapped_column(String(600), index=True)
    clasificado_por: Mapped[str | None] = mapped_column(String(30))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)

    softwares: Mapped[list["OfertaSoftware"]] = relationship(
        back_populates="oferta", cascade="all, delete-orphan", passive_deletes=True)


class OfertaSoftware(Base):
    """Tabla "Oferta–Software" (sec. 9.2): una fila por software detectado."""

    __tablename__ = "oferta_software"
    __table_args__ = (UniqueConstraint("id_oferta", "software", name="uq_oferta_software"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_oferta: Mapped[str] = mapped_column(String(120), ForeignKey("ofertas.id_oferta", ondelete="CASCADE"), index=True)
    software: Mapped[str] = mapped_column(String(120), index=True)
    grupo_software: Mapped[str | None] = mapped_column(String(160))
    texto_encontrado: Mapped[str | None] = mapped_column(String(255))
    carrera: Mapped[str | None] = mapped_column(String(255))
    semestre: Mapped[str] = mapped_column(String(16), index=True)
    corte: Mapped[str] = mapped_column(String(16), index=True)

    oferta: Mapped[Oferta] = relationship(back_populates="softwares")


class Catalogo(Base):
    """Tabla "Catálogo" (sec. 9.3). Los sinónimos van en `sinonimos`."""

    __tablename__ = "catalogo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    software: Mapped[str] = mapped_column(String(120), unique=True)
    grupo: Mapped[str] = mapped_column(String(160))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Palabras de contexto (separadas por coma) exigidas a los sinónimos ambiguos.
    contexto: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)

    sinonimos: Mapped[list["Sinonimo"]] = relationship(
        back_populates="catalogo", cascade="all, delete-orphan", passive_deletes=True, order_by="Sinonimo.id")


class Sinonimo(Base):
    __tablename__ = "sinonimos"
    __table_args__ = (UniqueConstraint("catalogo_id", "texto", name="uq_sinonimo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalogo_id: Mapped[int] = mapped_column(ForeignKey("catalogo.id", ondelete="CASCADE"), index=True)
    texto: Mapped[str] = mapped_column(String(160))
    sensible_mayusculas: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_contexto: Mapped[bool] = mapped_column(Boolean, default=False)
    patron_exclusion: Mapped[str | None] = mapped_column(String(500))

    catalogo: Mapped[Catalogo] = relationship(back_populates="sinonimos")


class TerminoBusqueda(Base):
    __tablename__ = "terminos_busqueda"
    __table_args__ = (UniqueConstraint("termino", "carrera", name="uq_termino_carrera"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    termino: Mapped[str] = mapped_column(String(255))
    carrera: Mapped[str] = mapped_column(String(120))
    # principal: corrida normal; ampliado: solo para la mini corrida
    tipo: Mapped[str] = mapped_column(String(20), default="principal")
    # Fuentes separadas por coma; vacío = todas las activas
    fuentes: Mapped[str | None] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    nombre: Mapped[str | None] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default="usuario")  # admin | usuario
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente | aprobado | rechazado
    aprobado_por: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)


class Validacion(Base):
    """Muestra de validación manual de GC (criterio de aceptación: 90 %)."""

    __tablename__ = "validaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    muestra_id: Mapped[str] = mapped_column(String(64), index=True)
    id_oferta: Mapped[str] = mapped_column(String(120), ForeignKey("ofertas.id_oferta", ondelete="CASCADE"))
    semestre: Mapped[str] = mapped_column(String(16))
    corte: Mapped[str] = mapped_column(String(16))
    softwares_detectados: Mapped[str | None] = mapped_column(Text)
    resultado: Mapped[str | None] = mapped_column(String(20))  # correcto | incorrecto
    softwares_faltantes: Mapped[str | None] = mapped_column(Text)
    softwares_sobrantes: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str | None] = mapped_column(Text)
    validado_por: Mapped[str | None] = mapped_column(String(255))
    fecha_validacion: Mapped[datetime | None] = mapped_column(DateTime)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class NoCatalogado(Base):
    """Términos frecuentes que no están en el catálogo (RF-17)."""

    __tablename__ = "no_catalogados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    termino: Mapped[str] = mapped_column(String(160), unique=True)  # normalizado
    termino_original: Mapped[str] = mapped_column(String(160))
    frecuencia_total: Mapped[int] = mapped_column(Integer, default=0)
    frecuencia_ultima: Mapped[int] = mapped_column(Integer, default=0)
    ejemplo_id_oferta: Mapped[str | None] = mapped_column(String(120))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente | agregado | descartado
    semestre: Mapped[str | None] = mapped_column(String(16))
    corte: Mapped[str | None] = mapped_column(String(16))
    primera_vez: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ultima_vez: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Curso(Base):
    """Cursos en tendencia (RF-19), tabla aparte de las ofertas."""

    __tablename__ = "cursos"
    __table_args__ = (UniqueConstraint("id_ejecucion", "plataforma", "url", name="uq_curso"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_ejecucion: Mapped[str | None] = mapped_column(String(64), index=True)
    semestre: Mapped[str] = mapped_column(String(16), index=True)
    corte: Mapped[str] = mapped_column(String(16))
    plataforma: Mapped[str] = mapped_column(String(40))
    termino: Mapped[str | None] = mapped_column(String(160))
    titulo: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(700))
    organizacion: Mapped[str | None] = mapped_column(String(255))
    nivel: Mapped[str | None] = mapped_column(String(80))
    tipo: Mapped[str | None] = mapped_column(String(80))
    calificacion: Mapped[float | None] = mapped_column(Float)
    num_calificaciones: Mapped[int | None] = mapped_column(Integer)
    inscritos_recientes: Mapped[int | None] = mapped_column(Integer)
    posicion: Mapped[int | None] = mapped_column(Integer)
    fecha_extraccion: Mapped[date] = mapped_column(Date, default=lambda: ahora().date())


class Config(Base):
    """Parámetros editables sin tocar el código (RF-01)."""

    __tablename__ = "config"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[dict | list | int | str | None] = mapped_column(JSON)
    descripcion: Mapped[str | None] = mapped_column(Text)
    actualizado_por: Mapped[str | None] = mapped_column(String(255))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)


class OfertaCruda(Base):
    """Ofertas tal como llegan de cada fuente; permiten reanudar sin duplicar."""

    __tablename__ = "ofertas_crudas"
    __table_args__ = (UniqueConstraint("id_ejecucion", "fuente", "id_fuente", name="uq_cruda"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_ejecucion: Mapped[str] = mapped_column(String(64), index=True)
    fuente: Mapped[str] = mapped_column(String(40))
    id_fuente: Mapped[str] = mapped_column(String(120))
    termino: Mapped[str | None] = mapped_column(String(255))
    carrera_termino: Mapped[str | None] = mapped_column(String(120))
    ubicacion: Mapped[str | None] = mapped_column(String(160))
    datos: Mapped[dict] = mapped_column(JSON)
    procesada: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Particion(Base):
    """Unidad de trabajo del scraping: fuente × término × ubicación."""

    __tablename__ = "particiones"
    __table_args__ = (
        UniqueConstraint("id_ejecucion", "fuente", "termino", "ubicacion", name="uq_particion"),
        Index("ix_particion_estado", "id_ejecucion", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_ejecucion: Mapped[str] = mapped_column(String(64), index=True)
    fuente: Mapped[str] = mapped_column(String(40))
    termino: Mapped[str] = mapped_column(String(255))
    carrera: Mapped[str | None] = mapped_column(String(120))
    ubicacion: Mapped[str] = mapped_column(String(160))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente, hecha, error
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    ofertas: Mapped[int] = mapped_column(Integer, default=0)
    omitidas: Mapped[int] = mapped_column(Integer, default=0)  # ya conocidas: no se pidió el detalle
    error: Mapped[str | None] = mapped_column(Text)
    mini: Mapped[bool] = mapped_column(Boolean, default=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)


class LlmCache(Base):
    __tablename__ = "llm_cache"

    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    resultado: Mapped[dict] = mapped_column(JSON)
    modelo: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class TokenMcp(Base):
    """Token personal de acceso de un administrador para las herramientas de
    administración del servidor MCP. Solo se guarda el hash SHA-256."""

    __tablename__ = "tokens_mcp"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefijo: Mapped[str] = mapped_column(String(16))  # primeros caracteres, para reconocerlo en la lista
    revocado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ultimo_uso: Mapped[datetime | None] = mapped_column(DateTime)
