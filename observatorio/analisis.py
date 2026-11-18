"""Rankings por carrera (RF-12), comparación entre cortes (RF-13) y resúmenes.

Lo usan la API, el servidor MCP y la exportación a Excel.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Ejecucion, Oferta, OfertaHabilidad, OfertaIdioma, OfertaSoftware
from observatorio.filtro_ofertas import oferta_incluida_en_resultados

ORDEN_CORTE = {"Inicio": 1, "Mitad": 2, "Final": 3}
UMBRAL_IGUAL_PP = 0.5  # variación menor a 0,5 puntos porcentuales = "igual"
ETIQUETA_SIN_DATO = "No especificado"


def clave_corte(semestre: str, corte: str) -> tuple:
    m = re.match(r"(\d{4})-(I{1,2})", semestre or "")
    anio, per = (int(m.group(1)), len(m.group(2))) if m else (0, 0)
    return (anio, per, ORDEN_CORTE.get(corte, 0))


def cortes_disponibles(s: Session) -> list[dict]:
    filas = s.execute(
        select(Oferta.semestre, Oferta.corte, func.count())
        .where(oferta_incluida_en_resultados())
        .group_by(Oferta.semestre, Oferta.corte)
    ).all()
    salida = [{"semestre": a, "corte": b, "ofertas": n} for a, b, n in filas]
    return sorted(salida, key=lambda x: clave_corte(x["semestre"], x["corte"]))


def corte_anterior(s: Session, semestre: str, corte: str) -> tuple[str, str] | None:
    lista = cortes_disponibles(s)
    k = clave_corte(semestre, corte)
    previos = [x for x in lista if clave_corte(x["semestre"], x["corte"]) < k]
    return (previos[-1]["semestre"], previos[-1]["corte"]) if previos else None


def _ofertas_por_carrera(s: Session, semestre: str, corte: str) -> Counter:
    c: Counter = Counter()
    for (carrera,) in s.execute(
        select(Oferta.carrera).where(
            Oferta.semestre == semestre,
            Oferta.corte == corte,
            oferta_incluida_en_resultados(),
        )
    ):
        for x in (carrera or "").split("; "):
            if x:
                c[x] += 1
    c["Todas"] = (
        s.scalar(
            select(func.count())
            .select_from(Oferta)
            .where(Oferta.semestre == semestre, Oferta.corte == corte, oferta_incluida_en_resultados())
        )
        or 0
    )
    return c


def _software_por_carrera(s: Session, semestre: str, corte: str) -> tuple[dict, dict]:
    conteo: dict[str, Counter] = defaultdict(Counter)
    grupos: dict[str, str] = {}
    q = select(OfertaSoftware.software, OfertaSoftware.grupo_software, OfertaSoftware.carrera).where(
        OfertaSoftware.semestre == semestre, OfertaSoftware.corte == corte)
    for sw, grupo, carrera in s.execute(q):
        grupos[sw] = grupo or ""
        conteo["Todas"][sw] += 1
        for x in (carrera or "").split("; "):
            if x:
                conteo[x][sw] += 1
    return conteo, grupos


def ranking(s: Session, semestre: str, corte: str, carrera: str | None = None, con_variacion: bool = True) -> list[dict]:
    """Posición, software, grupo, n.º de ofertas, % sobre las ofertas de la carrera y variación vs. corte anterior."""
    carrera = carrera or "Todas"
    totales = _ofertas_por_carrera(s, semestre, corte)
    conteo, grupos = _software_por_carrera(s, semestre, corte)
    total = totales.get(carrera, 0)
    prev = corte_anterior(s, semestre, corte) if con_variacion else None
    pct_prev: dict[str, float] = {}
    if prev:
        tp = _ofertas_por_carrera(s, *prev)
        cp, _ = _software_por_carrera(s, *prev)
        if tp.get(carrera):
            pct_prev = {k: 100 * v / tp[carrera] for k, v in cp.get(carrera, {}).items()}
    salida = []
    for i, (sw, n) in enumerate(conteo.get(carrera, Counter()).most_common(), 1):
        pct = round(100 * n / total, 2) if total else 0.0
        fila = {"posicion": i, "software": sw, "grupo": grupos.get(sw, ""), "ofertas": n, "porcentaje": pct,
                "carrera": carrera, "semestre": semestre, "corte": corte, "total_ofertas_carrera": total}
        if prev:
            fila["corte_anterior"] = f"{prev[0]} {prev[1]}"
            fila["variacion_pp"] = round(pct - pct_prev[sw], 2) if sw in pct_prev else None
        salida.append(fila)
    return salida


def ranking_por_grupo(s: Session, semestre: str, corte: str, carrera: str | None = None) -> list[dict]:
    carrera = carrera or "Todas"
    conteo, grupos = _software_por_carrera(s, semestre, corte)
    g: Counter = Counter()
    for sw, n in conteo.get(carrera, Counter()).items():
        g[grupos.get(sw, "")] += n
    return [{"grupo": k, "menciones": v} for k, v in g.most_common()]


def comparar(s: Session, sem_a: str, corte_a: str, sem_b: str, corte_b: str, carrera: str | None = None) -> dict:
    """Variación de cada software entre el corte A (anterior) y el B (posterior): subió, bajó, igual, nuevo, desapareció."""
    carrera = carrera or "Todas"
    ra = {x["software"]: x for x in ranking(s, sem_a, corte_a, carrera, con_variacion=False)}
    rb = {x["software"]: x for x in ranking(s, sem_b, corte_b, carrera, con_variacion=False)}
    filas = []
    for sw in sorted(set(ra) | set(rb)):
        a, b = ra.get(sw), rb.get(sw)
        pa, pb = (a or {}).get("porcentaje", 0.0), (b or {}).get("porcentaje", 0.0)
        if a is None:
            estado = "nuevo"
        elif b is None:
            estado = "desapareció"
        elif pb - pa >= UMBRAL_IGUAL_PP:
            estado = "subió"
        elif pa - pb >= UMBRAL_IGUAL_PP:
            estado = "bajó"
        else:
            estado = "igual"
        filas.append({"software": sw, "grupo": (a or b)["grupo"], "ofertas_a": (a or {}).get("ofertas", 0),
                      "porcentaje_a": pa, "ofertas_b": (b or {}).get("ofertas", 0), "porcentaje_b": pb,
                      "variacion_pp": round(pb - pa, 2), "estado": estado})
    filas.sort(key=lambda x: -abs(x["variacion_pp"]))
    tipos = _comparar_distribucion_campo(s, sem_a, corte_a, sem_b, corte_b, carrera, Oferta.tipo_oferta, "tipo_oferta")
    sectores = _comparar_distribucion_campo(s, sem_a, corte_a, sem_b, corte_b, carrera, Oferta.sector, "sector")
    return {
        "carrera": carrera,
        "corte_a": {"semestre": sem_a, "corte": corte_a, **_meta_corte(s, sem_a, corte_a)},
        "corte_b": {"semestre": sem_b, "corte": corte_b, **_meta_corte(s, sem_b, corte_b)},
        "softwares": filas,
        "tipos_oferta": tipos,
        "sectores": sectores,
        "advertencias": _advertencias_comparabilidad(s, sem_a, corte_a, sem_b, corte_b),
    }


def _meta_corte(s: Session, semestre: str, corte: str) -> dict:
    tot = _ofertas_por_carrera(s, semestre, corte)
    ejs = list(s.scalars(select(Ejecucion).where(Ejecucion.semestre == semestre, Ejecucion.corte == corte)))
    fuentes = sorted({f.strip() for e in ejs for f in (e.fuentes or "").split(",") if f.strip()})
    return {"total_ofertas": tot.get("Todas", 0), "ofertas_por_carrera": {k: v for k, v in tot.items() if k != "Todas"},
            "fuentes": fuentes, "ejecuciones": [e.id_ejecucion for e in ejs]}


def _advertencias_comparabilidad(s: Session, sa: str, ca: str, sb: str, cb: str) -> list[str]:
    """Sección 10.4: indicar si cambiaron términos o fuentes entre cortes."""
    def terminos(sem, cor):
        t = set()
        for e in s.scalars(select(Ejecucion).where(Ejecucion.semestre == sem, Ejecucion.corte == cor)):
            t |= set(e.terminos_usados or [])
        return t
    ma, mb = _meta_corte(s, sa, ca), _meta_corte(s, sb, cb)
    av = []
    if ma["fuentes"] != mb["fuentes"]:
        av.append(f"Cambiaron las fuentes: {', '.join(ma['fuentes']) or '—'} → {', '.join(mb['fuentes']) or '—'}.")
    ta, tb = terminos(sa, ca), terminos(sb, cb)
    if ta != tb:
        av.append(f"Cambiaron los términos de búsqueda: {len(tb - ta)} nuevos y {len(ta - tb)} retirados.")
    if ma["total_ofertas"] and mb["total_ofertas"] and max(ma["total_ofertas"], mb["total_ofertas"]) > 2 * min(ma["total_ofertas"], mb["total_ofertas"]):
        av.append(f"El número de ofertas cambió mucho ({ma['total_ofertas']} → {mb['total_ofertas']}); compare porcentajes, no conteos.")
    return av


def top_softwares_corte(s: Session, semestre: str, corte: str, limite: int = 10) -> list[dict]:
    """Top softwares por SQL (más rápido que ranking completo para el dashboard)."""
    total = s.scalar(
        select(func.count()).select_from(Oferta).where(
            Oferta.semestre == semestre, Oferta.corte == corte, oferta_incluida_en_resultados()
        )
    ) or 0
    q = (
        select(OfertaSoftware.software, func.count())
        .where(OfertaSoftware.semestre == semestre, OfertaSoftware.corte == corte)
        .group_by(OfertaSoftware.software)
        .order_by(func.count().desc())
        .limit(limite)
    )
    return [
        {
            "software": sw,
            "ofertas": n,
            "porcentaje": round(100 * n / total, 2) if total else 0.0,
            "semestre": semestre,
            "corte": corte,
        }
        for sw, n in s.execute(q)
    ]


def resumen_corte(s: Session, semestre: str, corte: str, *, para_dashboard: bool = False) -> dict:
    def agrupar(col):
        q = (
            select(col, func.count())
            .where(Oferta.semestre == semestre, Oferta.corte == corte, oferta_incluida_en_resultados())
            .group_by(col)
            .order_by(func.count().desc())
        )
        return {str(k or "Sin dato"): n for k, n in s.execute(q)}

    total = (
        s.scalar(
            select(func.count())
            .select_from(Oferta)
            .where(Oferta.semestre == semestre, Oferta.corte == corte, oferta_incluida_en_resultados())
        )
        or 0
    )
    con_sw = (
        s.scalar(
            select(func.count())
            .select_from(Oferta)
            .where(
                Oferta.semestre == semestre,
                Oferta.corte == corte,
                Oferta.num_softwares > 0,
                oferta_incluida_en_resultados(),
            )
        )
        or 0
    )
    top = top_softwares_corte(s, semestre, corte, 10) if para_dashboard else ranking(s, semestre, corte, None, con_variacion=False)[:10]
    salida = {
        "semestre": semestre, "corte": corte, "total_ofertas": total, "ofertas_con_software": con_sw,
        "por_fuente": agrupar(Oferta.fuente), "por_carrera": {k: v for k, v in _ofertas_por_carrera(s, semestre, corte).items() if k != "Todas"},
        "por_tipo_oferta": agrupar(Oferta.tipo_oferta),
        "por_modalidad": agrupar(Oferta.modalidad),
        "top_softwares": top,
    }
    if not para_dashboard:
        salida["por_ciudad"] = dict(list(agrupar(Oferta.ciudad).items())[:15])
        salida["por_nivel"] = agrupar(Oferta.nivel_experiencia)
    return salida


def _etiqueta_distribucion(valor: object | None) -> str:
    t = (str(valor).strip() if valor is not None else "")
    return t if t else ETIQUETA_SIN_DATO


def _conteo_oferta_campo(s: Session, semestre: str, corte: str, columna) -> dict[str, Counter]:
    conteo: dict[str, Counter] = defaultdict(Counter)
    q = select(columna, Oferta.carrera).where(
        Oferta.semestre == semestre,
        Oferta.corte == corte,
        oferta_incluida_en_resultados(),
    )
    for valor, carrera in s.execute(q):
        etiqueta = _etiqueta_distribucion(valor)
        conteo["Todas"][etiqueta] += 1
        for x in (carrera or "").split("; "):
            if x:
                conteo[x][etiqueta] += 1
    return conteo


def _ordenar_distribucion(conteo: Counter) -> list[tuple[str, int]]:
    items = [(k, v) for k, v in conteo.items() if k != ETIQUETA_SIN_DATO]
    items.sort(key=lambda x: (-x[1], x[0]))
    if ETIQUETA_SIN_DATO in conteo:
        items.append((ETIQUETA_SIN_DATO, conteo[ETIQUETA_SIN_DATO]))
    return items


def _pct_distribucion(conteo: Counter, carrera: str, total: int) -> dict[str, float]:
    if not total:
        return {}
    return {k: round(100 * v / total, 2) for k, v in conteo.get(carrera, Counter()).items()}


def ranking_tipo_oferta(
    s: Session, semestre: str, corte: str, carrera: str | None = None, con_variacion: bool = True
) -> list[dict]:
    """Distribución por `Oferta.tipo_oferta` (Empleo / Práctica·pasantía, etc.)."""
    return _ranking_distribucion_campo(
        s, semestre, corte, carrera, Oferta.tipo_oferta, "tipo_oferta", con_variacion=con_variacion
    )


def ranking_sector(
    s: Session, semestre: str, corte: str, carrera: str | None = None, con_variacion: bool = True
) -> list[dict]:
    """Distribución por `Oferta.sector` industrial."""
    return _ranking_distribucion_campo(
        s, semestre, corte, carrera, Oferta.sector, "sector", con_variacion=con_variacion
    )


def _ranking_distribucion_campo(
    s: Session,
    semestre: str,
    corte: str,
    carrera: str | None,
    columna,
    clave_respuesta: str,
    *,
    con_variacion: bool,
) -> list[dict]:
    carrera = carrera or "Todas"
    totales = _ofertas_por_carrera(s, semestre, corte)
    conteo = _conteo_oferta_campo(s, semestre, corte, columna)
    total = totales.get(carrera, 0)
    prev = corte_anterior(s, semestre, corte) if con_variacion else None
    pct_prev: dict[str, float] = {}
    if prev:
        tp = _ofertas_por_carrera(s, *prev)
        cp = _conteo_oferta_campo(s, *prev, columna)
        if tp.get(carrera):
            pct_prev = _pct_distribucion(cp, carrera, tp[carrera])
    salida = []
    for i, (etiq, n) in enumerate(_ordenar_distribucion(conteo.get(carrera, Counter())), 1):
        pct = round(100 * n / total, 2) if total else 0.0
        fila = {
            "posicion": i,
            clave_respuesta: etiq,
            "ofertas": n,
            "porcentaje": pct,
            "carrera": carrera,
            "semestre": semestre,
            "corte": corte,
            "total_ofertas_carrera": total,
        }
        if prev:
            fila["corte_anterior"] = f"{prev[0]} {prev[1]}"
            fila["variacion_pp"] = round(pct - pct_prev[etiq], 2) if etiq in pct_prev else None
        salida.append(fila)
    return salida


def _comparar_distribucion_campo(
    s: Session,
    sem_a: str,
    corte_a: str,
    sem_b: str,
    corte_b: str,
    carrera: str,
    columna,
    clave_respuesta: str,
) -> list[dict]:
    def mapa(sem: str, cor: str) -> dict[str, dict]:
        rows = _ranking_distribucion_campo(s, sem, cor, carrera, columna, clave_respuesta, con_variacion=False)
        return {r[clave_respuesta]: r for r in rows}

    ra, rb = mapa(sem_a, corte_a), mapa(sem_b, corte_b)
    filas = []
    for etiq in sorted(set(ra) | set(rb), key=lambda x: (x == ETIQUETA_SIN_DATO, x)):
        a, b = ra.get(etiq), rb.get(etiq)
        pa, pb = (a or {}).get("porcentaje", 0.0), (b or {}).get("porcentaje", 0.0)
        if a is None:
            estado = "nuevo"
        elif b is None:
            estado = "desapareció"
        elif pb - pa >= UMBRAL_IGUAL_PP:
            estado = "subió"
        elif pa - pb >= UMBRAL_IGUAL_PP:
            estado = "bajó"
        else:
            estado = "igual"
        filas.append(
            {
                clave_respuesta: etiq,
                "ofertas_a": (a or {}).get("ofertas", 0),
                "porcentaje_a": pa,
                "ofertas_b": (b or {}).get("ofertas", 0),
                "porcentaje_b": pb,
                "variacion_pp": round(pb - pa, 2),
                "estado": estado,
            }
        )
    filas.sort(key=lambda x: (-abs(x["variacion_pp"]), x[clave_respuesta] != ETIQUETA_SIN_DATO, x[clave_respuesta]))
    return filas


def _conteo_relacional(
    s: Session,
    semestre: str,
    corte: str,
    modelo,
    campo: str,
) -> dict[str, Counter]:
    conteo: dict[str, Counter] = defaultdict(Counter)
    q = select(getattr(modelo, campo), modelo.carrera).where(modelo.semestre == semestre, modelo.corte == corte)
    for valor, carrera in s.execute(q):
        if not valor:
            continue
        conteo["Todas"][valor] += 1
        for x in (carrera or "").split("; "):
            if x:
                conteo[x][valor] += 1
    return conteo


def ranking_habilidades(s: Session, semestre: str, corte: str, carrera: str | None = None) -> list[dict]:
    carrera = carrera or "Todas"
    totales = _ofertas_por_carrera(s, semestre, corte)
    conteo = _conteo_relacional(s, semestre, corte, OfertaHabilidad, "habilidad")
    total = totales.get(carrera, 0)
    salida = []
    for i, (hab, n) in enumerate(conteo.get(carrera, Counter()).most_common(), 1):
        pct = round(100 * n / total, 2) if total else 0.0
        salida.append(
            {
                "posicion": i,
                "habilidad": hab,
                "ofertas": n,
                "porcentaje": pct,
                "carrera": carrera,
                "semestre": semestre,
                "corte": corte,
                "total_ofertas_carrera": total,
            }
        )
    return salida


def ranking_idiomas(s: Session, semestre: str, corte: str, carrera: str | None = None) -> list[dict]:
    carrera = carrera or "Todas"
    totales = _ofertas_por_carrera(s, semestre, corte)
    conteo = _conteo_relacional(s, semestre, corte, OfertaIdioma, "idioma")
    total = totales.get(carrera, 0)
    salida = []
    for i, (idioma, n) in enumerate(conteo.get(carrera, Counter()).most_common(), 1):
        pct = round(100 * n / total, 2) if total else 0.0
        salida.append(
            {
                "posicion": i,
                "idioma": idioma,
                "ofertas": n,
                "porcentaje": pct,
                "carrera": carrera,
                "semestre": semestre,
                "corte": corte,
                "total_ofertas_carrera": total,
            }
        )
    return salida
