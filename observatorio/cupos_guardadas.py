"""Cupos de ofertas guardadas (finales) por fuente, carrera y celda fuente×carrera."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.filtro_ofertas import oferta_incluida_en_resultados
from observatorio.normas_corrida import NOMBRES_FUENTE
from observatorio.plan_extraccion import presupuesto_fuente_carrera, presupuesto_por_carrera, presupuesto_por_fuente

FUENTE_INV = {v: k for k, v in NOMBRES_FUENTE.items()}


def _clave_fuente(fuente_display: str) -> str:
    return FUENTE_INV.get(fuente_display, fuente_display.strip().lower())


def presupuestos_guardadas(params: dict, cfg: dict) -> tuple[dict[str, int], dict[str, int], dict[str, dict[str, int]]]:
    """Lee o reconstruye presupuestos de ofertas finales guardadas."""
    pf = params.get("presupuesto_guardadas_fuentes")
    pc = params.get("presupuesto_guardadas_carreras")
    pfc = params.get("presupuesto_guardadas_fuente_carrera")
    if pf and pc and pfc:
        return dict(pf), dict(pc), {f: dict(v) for f, v in pfc.items()}
    pf = params.get("presupuesto_fuentes") or {}
    pc = params.get("presupuesto_carreras") or {}
    pfc = params.get("presupuesto_fuente_carrera") or presupuesto_fuente_carrera(pf, cfg)
    return dict(pf), dict(pc), {f: dict(v) for f, v in (pfc or {}).items()}


def escalar_presupuestos_crudas(
    presu_fuentes: dict[str, int],
    presu_carreras: dict[str, int],
    presu_fc: dict[str, dict[str, int]],
    factor: float,
) -> tuple[dict[str, int], dict[str, int], dict[str, dict[str, int]], int]:
    import math

    f = max(1.0, float(factor))
    ext_f = {k: int(math.ceil(v * f)) for k, v in presu_fuentes.items()}
    ext_c = {k: int(math.ceil(v * f)) for k, v in presu_carreras.items()}
    ext_fc: dict[str, dict[str, int]] = {}
    for fuente, carreras in (presu_fc or {}).items():
        ext_fc[fuente] = {c: int(math.ceil(v * f)) for c, v in carreras.items()}
    objetivo = sum(ext_f.values()) if ext_f else int(math.ceil(sum(presu_fuentes.values()) * f))
    return ext_f, ext_c, ext_fc, objetivo


def contar_guardadas_fuente(s: Session, id_ejecucion: str, fuente_key: str) -> int:
    from observatorio.db.modelos import Oferta

    nombre = NOMBRES_FUENTE.get(fuente_key, fuente_key)
    return int(
        s.scalar(
            select(func.count()).select_from(Oferta).where(
                Oferta.id_ejecucion == id_ejecucion,
                Oferta.fuente == nombre,
                oferta_incluida_en_resultados(),
            )
        )
        or 0
    )


def contar_guardadas_carrera(s: Session, id_ejecucion: str, carrera: str) -> int:
    from observatorio.db.modelos import Oferta

    return int(
        s.scalar(
            select(func.count()).select_from(Oferta).where(
                Oferta.id_ejecucion == id_ejecucion,
                Oferta.carrera_principal == carrera,
                oferta_incluida_en_resultados(),
            )
        )
        or 0
    )


def contar_guardadas_fuente_carrera(s: Session, id_ejecucion: str, fuente_key: str, carrera: str) -> int:
    from observatorio.db.modelos import Oferta

    nombre = NOMBRES_FUENTE.get(fuente_key, fuente_key)
    return int(
        s.scalar(
            select(func.count()).select_from(Oferta).where(
                Oferta.id_ejecucion == id_ejecucion,
                Oferta.fuente == nombre,
                Oferta.carrera_principal == carrera,
                oferta_incluida_en_resultados(),
            )
        )
        or 0
    )


def logro_guardadas(s: Session, id_ejecucion: str, presu_fc: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    salida: dict[str, dict[str, int]] = {}
    for fuente, carreras in (presu_fc or {}).items():
        nom = NOMBRES_FUENTE.get(fuente, fuente)
        salida[nom] = {c: contar_guardadas_fuente_carrera(s, id_ejecucion, fuente, c) for c in carreras}
    return salida


def deficits_guardadas(
    s: Session,
    id_ejecucion: str,
    presu_fc: dict[str, dict[str, int]],
) -> list[tuple[str, str, int, int]]:
    """Lista (fuente_key, carrera, meta, guardadas) donde guardadas < meta."""
    faltan: list[tuple[str, str, int, int]] = []
    for fuente, carreras in (presu_fc or {}).items():
        for carrera, meta in carreras.items():
            meta_i = int(meta or 0)
            if meta_i <= 0:
                continue
            hecho = contar_guardadas_fuente_carrera(s, id_ejecucion, fuente, carrera)
            if hecho < meta_i:
                faltan.append((fuente, carrera, meta_i, hecho))
    return faltan


class ControlCuposGuardadas:
    """Impide guardar más ofertas de las presupuestadas por celda y agregados."""

    def __init__(
        self,
        s: Session,
        id_ejecucion: str,
        meta_fuentes: dict[str, int],
        meta_carreras: dict[str, int],
        meta_fc: dict[str, dict[str, int]],
    ):
        self.s = s
        self.id_ejecucion = id_ejecucion
        self.meta_fuentes = {k: int(v) for k, v in (meta_fuentes or {}).items() if int(v or 0) > 0}
        self.meta_carreras = {k: int(v) for k, v in (meta_carreras or {}).items() if int(v or 0) > 0}
        self.meta_fc = {
            f: {c: int(v) for c, v in carreras.items() if int(v or 0) > 0}
            for f, carreras in (meta_fc or {}).items()
        }
        self._fuente = Counter()
        self._carrera = Counter()
        self._fc = Counter()
        for f in self.meta_fuentes:
            self._fuente[f] = contar_guardadas_fuente(s, id_ejecucion, f)
        for c in self.meta_carreras:
            self._carrera[c] = contar_guardadas_carrera(s, id_ejecucion, c)
        for f, carreras in self.meta_fc.items():
            for c in carreras:
                self._fc[(f, c)] = contar_guardadas_fuente_carrera(s, id_ejecucion, f, c)

    def activo(self) -> bool:
        return bool(self.meta_fc or self.meta_fuentes or self.meta_carreras)

    def puede_guardar(self, fuente_display: str, carrera_principal: str) -> tuple[bool, str]:
        if not self.activo():
            return True, ""
        fk = _clave_fuente(fuente_display)
        cp = (carrera_principal or "").strip()
        if not cp:
            return False, "sin_carrera"
        meta_cell = (self.meta_fc.get(fk) or {}).get(cp)
        if meta_cell and self._fc[(fk, cp)] >= meta_cell:
            return False, "excedente_cupo_fuente_carrera"
        meta_f = self.meta_fuentes.get(fk, 0)
        if meta_f and self._fuente[fk] >= meta_f:
            return False, "excedente_cupo_fuente"
        meta_c = self.meta_carreras.get(cp, 0)
        if meta_c and self._carrera[cp] >= meta_c:
            return False, "excedente_cupo_carrera"
        return True, ""

    def registrar(self, fuente_display: str, carrera_principal: str) -> None:
        fk = _clave_fuente(fuente_display)
        cp = (carrera_principal or "").strip()
        self._fuente[fk] += 1
        self._carrera[cp] += 1
        self._fc[(fk, cp)] += 1


def construir_presupuestos_preparar(cfg: dict, meta_guardadas: int, fuentes: list[str]) -> dict:
    """Presupuestos congelados: metas de guardadas + extracción escalada."""
    if meta_guardadas <= 0 or not fuentes:
        return {}
    presu_g_f = presupuesto_por_fuente(meta_guardadas, fuentes, cfg)
    presu_g_c = presupuesto_por_carrera(meta_guardadas, cfg)
    presu_g_fc = presupuesto_fuente_carrera(presu_g_f, cfg)
    factor = float(cfg.get("factor_extraccion_crudas", 1.4))
    ext_f, ext_c, ext_fc, objetivo_ext = escalar_presupuestos_crudas(presu_g_f, presu_g_c, presu_g_fc, factor)
    return {
        "meta_ofertas_guardadas": meta_guardadas,
        "presupuesto_guardadas_fuentes": presu_g_f,
        "presupuesto_guardadas_carreras": presu_g_c,
        "presupuesto_guardadas_fuente_carrera": presu_g_fc,
        "objetivo_ofertas_corrida": objetivo_ext,
        "presupuesto_fuentes": ext_f,
        "presupuesto_carreras": ext_c,
        "presupuesto_fuente_carrera": ext_fc,
        "factor_extraccion_crudas": factor,
    }


def contar_crudas_fc(s: Session, id_ejecucion: str, fuente_key: str, carrera: str) -> int:
    from observatorio.db.modelos import OfertaCruda

    nombre = NOMBRES_FUENTE.get(fuente_key, fuente_key)
    return int(
        s.scalar(
            select(func.count())
            .select_from(OfertaCruda)
            .where(
                OfertaCruda.id_ejecucion == id_ejecucion,
                OfertaCruda.fuente == nombre,
                OfertaCruda.carrera_termino == carrera,
            )
        )
        or 0
    )


def estimar_rendimiento_fc(s: Session, id_ejecucion: str, presu_fc: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    rend: dict[str, dict[str, float]] = {}
    for fuente, carreras in (presu_fc or {}).items():
        rend[fuente] = {}
        for carrera in carreras:
            crudas = contar_crudas_fc(s, id_ejecucion, fuente, carrera)
            guardadas = contar_guardadas_fuente_carrera(s, id_ejecucion, fuente, carrera)
            rend[fuente][carrera] = guardadas / max(1, crudas)
    return rend


def ajustar_factor_extraccion(
    rendimiento: dict[str, dict[str, float]],
    factor_actual: float,
    meta_fc: dict[str, dict[str, int]],
    logro_fc: dict[str, dict[str, int]],
) -> float:
    """Sube el factor si muchas celdas guardadas quedaron cortas con rendimiento bajo."""
    import math

    ratios: list[float] = []
    for fuente, carreras in meta_fc.items():
        for carrera, meta in carreras.items():
            meta_i = int(meta or 0)
            if meta_i <= 0:
                continue
            hecho = (logro_fc.get(NOMBRES_FUENTE.get(fuente, fuente)) or {}).get(carrera, 0)
            if hecho >= meta_i:
                continue
            r = (rendimiento.get(fuente) or {}).get(carrera, 0.35)
            r = max(0.15, min(r, 0.85))
            ratios.append(meta_i / max(hecho, 1) / r)
    if not ratios:
        return factor_actual
    necesario = max(ratios)
    return min(2.5, max(factor_actual, math.ceil(necesario * 10) / 10))