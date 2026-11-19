"""Validación Pydantic de parámetros `config` (RF-01)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from observatorio.distribucion import FUENTES_EXTRACCION, validar_distribucion
from observatorio.parametros import POR_DEFECTO, valores_por_defecto

NIVELES_EXPERIENCIA = (
    "Practicante",
    "Sin experiencia / Junior",
    "Intermedio",
    "Senior",
    "Directivo",
    "No especificado",
)


def formato_errores_config(exc: ValidationError) -> str:
    partes: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        msg = err.get("msg", "valor inválido")
        partes.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(partes) if partes else "Valor de configuración inválido."


class _ListaTexto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]

    @classmethod
    def from_list(cls, valor: list) -> "_ListaTexto":
        if not isinstance(valor, list):
            raise TypeError("Se esperaba una lista.")
        limpia = [str(x).strip() for x in valor if str(x).strip()]
        return cls(items=limpia)

    def to_python(self) -> list[str]:
        return list(self.items)


class CarrerasValor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: list[str] = Field(min_length=1, max_length=12)

    @classmethod
    def adapt(cls, valor: Any) -> list[str]:
        if not isinstance(valor, list):
            raise ValueError("carreras debe ser una lista de textos.")
        out = [str(x).strip() for x in valor if str(x).strip()]
        if not out:
            raise ValueError("Debe haber al menos una carrera.")
        return out

    @classmethod
    def validate_valor(cls, valor: Any) -> list[str]:
        return cls(root=cls.adapt(valor)).root


class FuenteExtraccion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activa: bool = True
    max_por_particion: int = Field(ge=1, le=500)
    retraso_segundos: tuple[float, float]
    fragmentos: int = Field(ge=1, le=12)
    max_paginas: int | None = Field(default=None, ge=1, le=20)

    @field_validator("retraso_segundos", mode="before")
    @classmethod
    def _retraso(cls, v: Any) -> tuple[float, float]:
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ValueError("retraso_segundos debe tener exactamente dos números [mín, máx].")
        a, b = float(v[0]), float(v[1])
        if a < 0 or b < 0 or b < a:
            raise ValueError("retraso_segundos: el máximo debe ser ≥ al mínimo y ambos ≥ 0.")
        return (a, b)


class FuentesValor(BaseModel):
    model_config = ConfigDict(extra="allow")

    linkedin: FuenteExtraccion | None = None
    indeed: FuenteExtraccion | None = None
    computrabajo: FuenteExtraccion | None = None

    @classmethod
    def validate_valor(cls, valor: Any) -> dict:
        if not isinstance(valor, dict):
            raise ValueError("fuentes debe ser un objeto.")
        base = dict(valores_por_defecto().get("fuentes") or {})
        merged = {**base, **valor}
        for clave, payload in list(merged.items()):
            if not isinstance(payload, dict):
                continue
            modelo = FuenteExtraccion.model_validate(payload)
            merged[clave] = modelo.model_dump(mode="python")
            r = merged[clave]["retraso_segundos"]
            merged[clave]["retraso_segundos"] = list(r)
        return merged


class UbicacionFila(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=120)
    linkedin: str = ""
    indeed: str = ""
    computrabajo: str = ""
    remoto: bool | None = None


class UbicacionesValor(BaseModel):
    root: list[UbicacionFila] = Field(min_length=1)

    @classmethod
    def validate_valor(cls, valor: Any) -> list[dict]:
        if not isinstance(valor, list):
            raise ValueError("ubicaciones debe ser una lista.")
        filas = [UbicacionFila.model_validate(x).model_dump(mode="python") for x in valor]
        nombres = [f["nombre"] for f in filas]
        if len(nombres) != len(set(nombres)):
            raise ValueError("Hay nombres de ciudad duplicados en ubicaciones.")
        return filas


class NivelesExperienciaValor(BaseModel):
    modo: Literal["todos", "algunos"]
    niveles: list[str]

    @model_validator(mode="after")
    def _coherencia(self) -> "NivelesExperienciaValor":
        invalidos = [n for n in self.niveles if n not in NIVELES_EXPERIENCIA]
        if invalidos:
            raise ValueError(f"Niveles no reconocidos: {', '.join(invalidos[:5])}")
        if self.modo == "algunos" and not self.niveles:
            raise ValueError("En modo «algunos» debe elegir al menos un nivel.")
        if self.modo == "todos":
            self.niveles = list(NIVELES_EXPERIENCIA)
        return self


class MiniCorridaValor(BaseModel):
    habilitada: bool
    max_minutos: int = Field(ge=5, le=720)
    fuentes: list[str] = Field(min_length=1, max_length=8)

    @field_validator("fuentes")
    @classmethod
    def _fuentes(cls, v: list[str]) -> list[str]:
        return [str(x).strip() for x in v if str(x).strip()]


class AjusteProporcionValor(BaseModel):
    habilitado: bool
    tolerancia_proporcion_pp: int = Field(ge=0, le=50)


class RondaExtraCuposValor(BaseModel):
    habilitada: bool
    max_rondas: int = Field(ge=0, le=10)
    consultas_por_celda: int = Field(ge=1, le=50)
    max_minutos_fuente: int = Field(ge=1, le=240)


class DedupValor(BaseModel):
    alcance: Literal["global", "corte"]
    dias: int = Field(ge=1, le=60)


class ReglaCarreraValor(BaseModel):
    titulo: list[str] = Field(default_factory=list)
    descripcion: list[str] = Field(default_factory=list)


class ReglasCarreraValor(BaseModel):
    model_config = ConfigDict(extra="allow")

    @classmethod
    def validate_valor(cls, valor: Any) -> dict:
        if not isinstance(valor, dict):
            raise ValueError("reglas_carrera debe ser un objeto por carrera.")
        out: dict[str, Any] = {}
        for carrera, reglas in valor.items():
            if not isinstance(reglas, dict):
                raise ValueError(f"Reglas de «{carrera}» inválidas.")
            modelo = ReglaCarreraValor.model_validate(reglas)
            out[str(carrera)] = modelo.model_dump(mode="python")
        return out


class CursosConfigValor(BaseModel):
    activo: bool
    plataformas: list[str] = Field(min_length=1, max_length=10)
    max_por_termino: int = Field(ge=1, le=100)
    max_terminos_demanda: int = Field(ge=1, le=200)
    min_ofertas_habilidad: int = Field(ge=1, le=100)
    min_terminos: int = Field(ge=1, le=100)
    peso_demanda_puntaje: float = Field(ge=0, le=1)
    terminos_respaldo: list[str] = Field(min_length=1, max_length=100)


class NoCatalogadosValor(BaseModel):
    min_frecuencia: int = Field(ge=1, le=1000)
    max_terminos: int = Field(ge=10, le=5000)


def _validar_distribucion(clave: str, valor: Any, cfg: dict) -> dict:
    if not isinstance(valor, dict):
        raise ValueError(f"{clave} debe ser un objeto de porcentajes.")
    claves = list(FUENTES_EXTRACCION) if clave == "distribucion_fuentes" else list(cfg.get("carreras") or [])
    try:
        return validar_distribucion(valor, claves=claves)
    except ValueError as e:
        raise ValueError(str(e)) from e


def validar_valor_config(clave: str, valor: Any, cfg: dict | None = None) -> Any:
    """Valida y normaliza un valor antes de guardarlo. Lanza ValueError con mensaje legible."""
    cfg = cfg or {}
    if clave not in POR_DEFECTO:
        raise ValueError("Parámetro desconocido.")

    if clave in ("distribucion_fuentes", "distribucion_carreras"):
        return _validar_distribucion(clave, valor, cfg)

    if clave == "carreras":
        return CarrerasValor.validate_valor(valor)
    if clave == "fuentes":
        return FuentesValor.validate_valor(valor)
    if clave == "ubicaciones":
        return UbicacionesValor.validate_valor(valor)
    if clave == "solo_capitales_departamento":
        if not isinstance(valor, bool):
            raise ValueError("Debe ser verdadero o falso.")
        return valor
    if clave == "ventana_dias":
        n = int(valor)
        if n < 1 or n > 365:
            raise ValueError("ventana_dias debe estar entre 1 y 365.")
        return n
    if clave == "tipo_oferta":
        if valor not in ("practica", "empleo", "ambas"):
            raise ValueError("tipo_oferta debe ser practica, empleo o ambas.")
        return valor
    if clave == "niveles_experiencia":
        return NivelesExperienciaValor.model_validate(valor).model_dump(mode="python")
    if clave == "objetivo_ofertas_corrida":
        n = int(valor)
        if n < 100 or n > 500_000:
            raise ValueError("objetivo_ofertas_corrida debe estar entre 100 y 500000.")
        return n
    if clave == "mini_corrida":
        m = MiniCorridaValor.model_validate(valor)
        d = m.model_dump(mode="python")
        return d
    if clave == "factor_extraccion_crudas":
        f = float(valor)
        if f < 1.0 or f > 5.0:
            raise ValueError("factor_extraccion_crudas debe estar entre 1.0 y 5.0.")
        return round(f, 2)
    if clave == "ajuste_proporcion_final":
        return AjusteProporcionValor.model_validate(valor).model_dump(mode="python")
    if clave == "ronda_extra_cupos":
        return RondaExtraCuposValor.model_validate(valor).model_dump(mode="python")
    if clave == "dedup":
        return DedupValor.model_validate(valor).model_dump(mode="python")
    if clave == "reglas_carrera":
        return ReglasCarreraValor.validate_valor(valor)
    if clave in ("exclusion_titulo", "exclusion_operativa_titulo"):
        return _ListaTexto.from_list(valor).to_python()
    if clave == "requiere_software_o_habilidad":
        if not isinstance(valor, bool):
            raise ValueError("Debe ser verdadero o falso.")
        return valor
    if clave == "cursos":
        d = CursosConfigValor.model_validate(valor).model_dump(mode="python")
        d["terminos_respaldo"] = [str(t).strip() for t in d["terminos_respaldo"] if str(t).strip()]
        return d
    if clave == "no_catalogados":
        return NoCatalogadosValor.model_validate(valor).model_dump(mode="python")

    esperado = type(POR_DEFECTO[clave]["valor"])
    if not isinstance(valor, esperado) and not (esperado is int and isinstance(valor, float)):
        raise ValueError(f"El valor debe ser de tipo {esperado.__name__}.")
    return valor