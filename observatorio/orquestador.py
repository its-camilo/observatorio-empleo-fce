"""Orquestación de una corrida: preparar → extraer (por fragmentos) → consolidar.

Una corrida se puede interrumpir y retomar con el mismo `id_ejecucion`: las
particiones ya hechas no se repiten y las ofertas crudas ya procesadas no se
vuelven a procesar (requerimiento de la sección 11).
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from observatorio.db.modelos import Curso, Ejecucion, Oferta, OfertaCruda, Particion, TerminoBusqueda, ahora
from observatorio.db.semilla import sembrar_todo
from observatorio.parametros import leer_config
from observatorio.scraper.base import Consulta
from observatorio.scraper.http import FuenteBloqueada, explicar_error

log = logging.getLogger("observatorio.corrida")

NOMBRES_FUENTE = {"linkedin": "LinkedIn", "indeed": "Indeed", "google": "Google Jobs", "computrabajo": "Computrabajo"}
CORTES = {"inicio": "Inicio", "mitad": "Mitad", "final": "Final"}


def contar_crudas_ejecucion(s: Session, id_ejecucion: str) -> int:
    return s.scalar(select(func.count()).select_from(OfertaCruda).where(OfertaCruda.id_ejecucion == id_ejecucion)) or 0


def limite_extraccion_corrida(cfg: dict, ejec: Ejecucion) -> int:
    """Tope global de ofertas crudas por corrida (0 = sin tope). Se congela en ejec.parametros al preparar."""
    if ejec.parametros and "limite_extraccion_corrida" in ejec.parametros:
        return int(ejec.parametros["limite_extraccion_corrida"] or 0)
    return int(cfg.get("limite_extraccion_corrida") or 0)


def normalizar_corte(corte: str) -> str:
    c = (corte or "").strip().lower()
    if c not in CORTES:
        raise ValueError("El corte debe ser inicio, mitad o final")
    return CORTES[c]


def normalizar_semestre(semestre: str) -> str:
    import re

    s = (semestre or "").strip().upper().replace(" ", "")
    m = re.fullmatch(r"(\d{4})-?(I{1,2}|1|2)", s)
    if not m:
        raise ValueError("El semestre debe tener la forma 2026-I o 2026-II")
    return f"{m.group(1)}-{'I' if m.group(2) in ('I', '1') else 'II'}"


def crear_extractor(fuente: str, cfg_fuente: dict):
    retraso = tuple(cfg_fuente.get("retraso_segundos") or (2.0, 4.0))
    if fuente == "linkedin":
        from observatorio.scraper.linkedin import LinkedIn
        return LinkedIn(retraso=retraso)
    if fuente == "indeed":
        from observatorio.scraper.jobspy_fuentes import Indeed
        return Indeed(retraso=retraso)
    if fuente == "google":
        from observatorio.scraper.jobspy_fuentes import GoogleJobs
        return GoogleJobs(retraso=retraso)
    if fuente == "computrabajo":
        from observatorio.scraper.computrabajo import Computrabajo
        return Computrabajo(retraso=retraso, max_paginas=int(cfg_fuente.get("max_paginas", 3)))
    raise ValueError(f"Fuente desconocida: {fuente}")


# ---------------------------------------------------------------------------
# 1. Preparar
# ---------------------------------------------------------------------------
def preparar(s: Session, semestre: str, corte: str, id_ejecucion: str | None = None, ejecutado_por: str | None = None,
             modo: str = "completa", fuentes: list[str] | None = None, limite_terminos: int | None = None,
             limite_ubicaciones: int | None = None, max_por_particion: int | None = None,
             ejecutor: str | None = None) -> Ejecucion:
    sembrar_todo(s)
    cfg = leer_config(s)
    semestre, corte = normalizar_semestre(semestre), normalizar_corte(corte)
    id_ejecucion = id_ejecucion or f"{semestre}-{corte.lower()}-{uuid.uuid4().hex[:6]}"
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        ejec = Ejecucion(id_ejecucion=id_ejecucion, semestre=semestre, corte=corte)
        s.add(ejec)
    elif (ejec.semestre, ejec.corte) != (semestre, corte):
        raise ValueError("Ese id de ejecución ya existe con otro semestre/corte")
    ejec.ejecutado_por = ejecutado_por or ejec.ejecutado_por or os.getenv("GITHUB_ACTOR") or "local"
    ejec.modo = modo
    if ejecutor:
        ejec.ejecutor = ejecutor
    ejec.estado = "en_curso"
    ejec.fase = "preparada"
    ejec.inicio = ejec.inicio or ahora()
    ejec.meta_ofertas = int(cfg.get("meta_ofertas", 10000))
    limite_ext = int(cfg.get("limite_extraccion_corrida") or 0)
    if limite_ext > 0:
        ejec.parametros = {**(ejec.parametros or {}), "limite_extraccion_corrida": limite_ext}
    if os.getenv("GITHUB_RUN_ID"):
        ejec.github_run_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"

    activas = [f for f, c in cfg["fuentes"].items() if c.get("activa")]
    if fuentes:
        activas = [f for f in activas if f in fuentes] or [f for f in fuentes if f in NOMBRES_FUENTE]
    ejec.fuentes = ", ".join(NOMBRES_FUENTE[f] for f in activas)

    terminos = list(s.scalars(select(TerminoBusqueda).where(TerminoBusqueda.activo.is_(True), TerminoBusqueda.tipo == "principal")
                              .order_by(TerminoBusqueda.carrera, TerminoBusqueda.id)))
    if limite_terminos:
        # repartir el límite entre carreras para que haya de las tres
        por_carrera: dict[str, list] = {}
        for t in terminos:
            por_carrera.setdefault(t.carrera, []).append(t)
        terminos, i = [], 0
        while len(terminos) < limite_terminos and any(i < len(v) for v in por_carrera.values()):
            for v in por_carrera.values():
                if i < len(v) and len(terminos) < limite_terminos:
                    terminos.append(v[i])
            i += 1
    ejec.terminos_usados = sorted({f"{t.carrera}: {t.termino}" for t in terminos})
    ubicaciones = cfg["ubicaciones"][:limite_ubicaciones] if limite_ubicaciones else cfg["ubicaciones"]
    crear_particiones(s, ejec, activas, terminos, ubicaciones, cfg, mini=False, max_por_particion=max_por_particion)
    s.flush()
    return ejec


def crear_particiones(s: Session, ejec: Ejecucion, fuentes: list[str], terminos, ubicaciones: list[dict], cfg: dict,
                      mini: bool, max_por_particion: int | None = None) -> int:
    existentes = {(p.fuente, p.termino, p.ubicacion) for p in s.scalars(select(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion))}
    n = 0
    for f in fuentes:
        for t in terminos:
            permitidas = [x.strip() for x in (t.fuentes or "").split(",") if x.strip()]
            if permitidas and f not in permitidas:
                continue
            for u in ubicaciones:
                lugar = u.get(f)
                if lugar is None or (lugar == "" and f in ("linkedin", "indeed", "google")):
                    continue
                clave_u = f"{u['nombre']}|{lugar}|{'remoto' if u.get('remoto') else ''}"
                if (f, t.termino, clave_u) in existentes:
                    continue
                s.add(Particion(id_ejecucion=ejec.id_ejecucion, fuente=f, termino=t.termino, carrera=t.carrera,
                                ubicacion=clave_u, mini=mini, ofertas=0))
                existentes.add((f, t.termino, clave_u))
                n += 1
    if max_por_particion:
        ejec.parametros = {**(ejec.parametros or {}), "max_por_particion": max_por_particion}
    s.flush()
    return n


def matriz(s: Session, id_ejecucion: str) -> list[dict]:
    """Trabajos paralelos para GitHub Actions: un elemento por fuente × fragmento."""
    cfg = leer_config(s)
    fuentes = [f for (f,) in s.execute(select(Particion.fuente).where(Particion.id_ejecucion == id_ejecucion).distinct())]
    salida = []
    for f in fuentes:
        n = max(1, int(cfg["fuentes"].get(f, {}).get("fragmentos", 1)))
        salida.extend({"fuente": f, "fragmento": i, "fragmentos": n} for i in range(n))
    return salida


# ---------------------------------------------------------------------------
# 2. Extraer
# ---------------------------------------------------------------------------
def extraer(s: Session, id_ejecucion: str, fuente: str, fragmento: int = 0, fragmentos: int = 1,
            max_minutos: float | None = None, solo_mini: bool = False) -> dict:
    cfg = leer_config(s)
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ValueError(f"No existe la ejecución {id_ejecucion}")
    cfg_f = cfg["fuentes"].get(fuente, {})
    max_part = int((ejec.parametros or {}).get("max_por_particion") or cfg_f.get("max_por_particion", 100))
    extractor = crear_extractor(fuente, cfg_f)
    nombre = NOMBRES_FUENTE[fuente]
    q = select(Particion).where(Particion.id_ejecucion == id_ejecucion, Particion.fuente == fuente,
                                Particion.estado != "hecha").order_by(Particion.id)
    if solo_mini:
        q = q.where(Particion.mini.is_(True))
    particiones = [p for p in s.scalars(q) if p.id % fragmentos == fragmento]

    # Identificadores ya conocidos: no se vuelve a pedir su detalle (ahorra consultas)
    conocidos = set(s.scalars(select(OfertaCruda.id_fuente).where(OfertaCruda.id_ejecucion == id_ejecucion,
                                                                 OfertaCruda.fuente == nombre)))
    if cfg["dedup"].get("alcance", "global") == "global":
        conocidos |= set(s.scalars(select(Oferta.id_fuente).where(Oferta.fuente == nombre)))
    inicio = time.time()
    tope = limite_extraccion_corrida(cfg, ejec)
    resumen = {"fuente": nombre, "particiones": len(particiones), "hechas": 0, "ofertas": 0, "errores": 0, "bloqueada": False,
               "tope_extraccion": tope or None}
    log.info("[%s] Fragmento %d/%d: %d consultas pendientes%s", nombre, fragmento + 1, fragmentos, len(particiones),
             f" (tope global {tope} crudas)" if tope else "")
    detenido_por_tope = False
    for p in particiones:
        if tope and contar_crudas_ejecucion(s, id_ejecucion) >= tope:
            log.info("[%s] Tope global de extracción alcanzado (%d ofertas crudas)", nombre, tope)
            resumen["tope_alcanzado"] = True
            detenido_por_tope = True
            break
        if max_minutos and (time.time() - inicio) / 60 > max_minutos:
            log.info("[%s] Se alcanzó el tiempo máximo; lo pendiente queda para la próxima reanudación", nombre)
            break
        nombre_u, lugar, remoto = p.ubicacion.split("|")
        c = Consulta(fuente=fuente, termino=p.termino, ubicacion=lugar, nombre_ubicacion=nombre_u, carrera=p.carrera,
                     remoto=bool(remoto), max_resultados=max_part, ventana_dias=int(cfg.get("ventana_dias", 30)))
        p.intentos += 1
        n = 0
        try:
            for o in extractor.extraer(c, lambda idf: idf in conocidos):
                if tope and contar_crudas_ejecucion(s, id_ejecucion) >= tope:
                    detenido_por_tope = True
                    resumen["tope_alcanzado"] = True
                    break
                if o.id_fuente in conocidos:
                    continue
                conocidos.add(o.id_fuente)
                s.add(OfertaCruda(id_ejecucion=id_ejecucion, fuente=o.fuente, id_fuente=o.id_fuente, termino=p.termino,
                                  carrera_termino=p.carrera, ubicacion=nombre_u, datos=o.a_dict()))
                n += 1
                if n % 25 == 0:
                    s.commit()  # guardar lo ya extraído (RF-16)
            if detenido_por_tope:
                p.estado = "hecha"
                p.error = None
                resumen["hechas"] += 1
            else:
                p.estado = "hecha"
                p.error = None
                resumen["hechas"] += 1
        except FuenteBloqueada as e:
            p.estado = "error"
            p.error = explicar_error(fuente, e)
            resumen["bloqueada"] = True
            resumen["errores"] += 1
            log.warning("[%s] %s", nombre, p.error)
        except Exception as e:  # noqa: BLE001 - una consulta fallida no detiene las demás
            p.estado = "error"
            p.error = explicar_error(fuente, e)
            resumen["errores"] += 1
            log.warning("[%s] '%s' en %s: %s", nombre, p.termino, nombre_u, p.error)
        p.ofertas += n
        p.omitidas = (p.omitidas or 0) + int(c.opciones.get("stats", {}).get("omitidas", 0))
        resumen["ofertas"] += n
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
        log.info("[%s] '%s' en %s: %d ofertas nuevas", nombre, p.termino, nombre_u, n)
        if detenido_por_tope:
            log.info("[%s] Tope global de extracción alcanzado (%d ofertas crudas)", nombre, tope)
            break
        if resumen["bloqueada"]:
            log.warning("[%s] Se detiene este fragmento para no insistir; se puede reanudar más tarde", nombre)
            break
    return resumen


# ---------------------------------------------------------------------------
# 3. Consolidar
# ---------------------------------------------------------------------------
def total_corte(s: Session, semestre: str, corte: str) -> int:
    return s.scalar(select(func.count()).select_from(Oferta).where(Oferta.semestre == semestre, Oferta.corte == corte)) or 0


def consolidar(s: Session, id_ejecucion: str, usar_llm: bool = True, permitir_mini: bool = True) -> Ejecucion:
    from observatorio.pipeline.procesar import Procesador

    cfg = leer_config(s)
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ValueError(f"No existe la ejecución {id_ejecucion}")
    ejec.fase = "procesando"
    s.commit()
    proc = Procesador(s, ejec, cfg, usar_llm=usar_llm)
    proc.procesar_pendientes()

    # Mini corrida automática si no se llegó a la meta
    mini_cfg = cfg.get("mini_corrida") or {}
    total = total_corte(s, ejec.semestre, ejec.corte)
    sin_tope_extraccion = limite_extraccion_corrida(cfg, ejec) <= 0
    if permitir_mini and sin_tope_extraccion and ejec.modo == "completa" and mini_cfg.get("habilitada") and not ejec.mini_corrida \
            and total < int(cfg.get("meta_ofertas", 10000)):
        log.info("Hay %d ofertas relevantes en el corte (meta %s): se inicia la mini corrida con términos ampliados",
                 total, cfg.get("meta_ofertas"))
        ejec.mini_corrida = True
        ejec.fase = "mini_corrida"
        terminos = list(s.scalars(select(TerminoBusqueda).where(TerminoBusqueda.activo.is_(True), TerminoBusqueda.tipo == "ampliado")))
        fuentes = [f for f in mini_cfg.get("fuentes", ["linkedin", "indeed", "computrabajo"]) if cfg["fuentes"].get(f, {}).get("activa")]
        crear_particiones(s, ejec, fuentes, terminos, cfg["ubicaciones"], cfg, mini=True)
        ejec.terminos_usados = sorted(set(ejec.terminos_usados or []) | {f"{t.carrera}: {t.termino} (ampliado)" for t in terminos})
        s.commit()
        presupuesto = float(mini_cfg.get("max_minutos", 240))
        t0 = time.time()
        for f in fuentes:
            restante = presupuesto - (time.time() - t0) / 60
            if restante <= 1:
                break
            try:
                extraer(s, id_ejecucion, f, max_minutos=restante / max(1, len(fuentes) - fuentes.index(f)), solo_mini=True)
            except Exception as e:  # noqa: BLE001
                log.warning("Mini corrida en %s falló: %s", f, e)
        ejec.fase = "procesando"
        s.commit()
        proc.procesar_pendientes()

    proc.guardar_no_catalogados()
    finalizar(s, ejec, proc)
    s.commit()
    return ejec


def finalizar(s: Session, ejec: Ejecucion, proc=None) -> None:
    parts = list(s.scalars(select(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion)))
    crudas = s.scalar(select(func.count()).select_from(OfertaCruda).where(OfertaCruda.id_ejecucion == ejec.id_ejecucion)) or 0
    omitidas = sum(p.omitidas or 0 for p in parts)
    ejec.ofertas_encontradas = crudas + omitidas
    t = proc.total if proc else None
    if t is not None:
        ejec.duplicados_proceso = (ejec.duplicados_proceso or 0) + t.duplicados
        ejec.no_relevantes = (ejec.no_relevantes or 0) + t.no_relevantes
        previo = ejec.uso_llm or {}
        ejec.uso_llm = {**previo, **proc.llm.resumen(),
                        "clasificadas_llm": previo.get("clasificadas_llm", 0) + t.por_llm,
                        "respaldo_reglas": previo.get("respaldo_reglas", 0) + t.por_respaldo}
    # Duplicados = repetidas en el procesamiento + ya conocidas al extraer (no se pidió su detalle)
    ejec.duplicados_eliminados = (ejec.duplicados_proceso or 0) + omitidas
    guardadas = list(s.scalars(select(Oferta).where(Oferta.id_ejecucion == ejec.id_ejecucion)))
    ejec.ofertas_guardadas = len(guardadas)
    ejec.ofertas_relevantes = len(guardadas)
    por_fuente: dict[str, dict] = {}
    for p in parts:
        n = NOMBRES_FUENTE.get(p.fuente, p.fuente)
        d = por_fuente.setdefault(n, {"encontradas": 0, "guardadas": 0, "consultas": 0, "consultas_con_error": 0})
        d["encontradas"] += (p.ofertas or 0) + (p.omitidas or 0)
        d["consultas"] += 1
        d["consultas_con_error"] += 1 if p.estado == "error" else 0
    for o in guardadas:
        por_fuente.setdefault(o.fuente, {"encontradas": 0, "guardadas": 0, "consultas": 0, "consultas_con_error": 0})["guardadas"] += 1
    ejec.conteo_por_fuente = por_fuente
    por_carrera: Counter = Counter()
    for o in guardadas:
        for c in (o.carrera or "").split("; "):
            if c:
                por_carrera[c] += 1
    ejec.conteo_por_carrera = dict(por_carrera)
    ejec.total_corte = total_corte(s, ejec.semestre, ejec.corte)

    errores = []
    for p in parts:
        if p.error and p.error not in errores:
            errores.append(p.error)
    for nombre, d in por_fuente.items():
        if d["consultas"] and d["encontradas"] == 0 and d["consultas_con_error"] == 0:
            errores.append(f"{nombre} no devolvió ofertas en ninguna consulta. Puede ser un bloqueo silencioso de la fuente "
                           f"(frecuente en Google Jobs desde servidores en la nube) o un cambio en la página.")
    pendientes = sum(1 for p in parts if p.estado == "pendiente")
    if pendientes:
        errores.append(f"Quedaron {pendientes} consultas sin hacer (tiempo agotado o fuente bloqueada). "
                       f"Puede reanudar la corrida con el mismo id: {ejec.id_ejecucion}.")
    tope_ext = limite_extraccion_corrida(leer_config(s), ejec)
    if tope_ext > 0 and crudas >= tope_ext:
        errores.append(f"La extracción se detuvo al alcanzar el tope configurado de {tope_ext} ofertas crudas "
                       f"(Configuración → limite_extraccion_corrida).")
    elif ejec.total_corte < (ejec.meta_ofertas or 0) and ejec.modo == "completa" and tope_ext <= 0:
        errores.append(f"El corte tiene {ejec.total_corte} ofertas relevantes; no alcanzó la meta de {ejec.meta_ofertas}.")
    ejec.errores_detalle = errores
    ejec.errores = "\n".join(errores) or None
    ejec.fin = ahora()
    ejec.duracion_segundos = int((ejec.fin - (ejec.inicio or ejec.fin)).total_seconds())
    con_error = sum(1 for p in parts if p.estado == "error")
    if parts and con_error == len(parts):
        ejec.estado = "fallida"
    elif pendientes or con_error:
        ejec.estado = "incompleta"
    else:
        ejec.estado = "completada"
    ejec.fase = "terminada"


# ---------------------------------------------------------------------------
# Cursos (RF-19)
# ---------------------------------------------------------------------------
def extraer_cursos_corrida(s: Session, id_ejecucion: str, terminos: list[str] | None = None, max_por_termino: int | None = None) -> dict:
    from observatorio.scraper.cursos import extraer_cursos

    cfg = leer_config(s)
    ejec = s.get(Ejecucion, id_ejecucion)
    cc = cfg.get("cursos") or {}
    if not cc.get("activo", True):
        return {"cursos": 0, "errores": ["Módulo de cursos desactivado"]}
    cursos, errores = extraer_cursos(cc.get("plataformas", []), terminos or cc.get("terminos", []),
                                     max_por_termino or int(cc.get("max_por_termino", 15)))
    vistos = {u for (u,) in s.execute(select(Curso.url).where(Curso.id_ejecucion == id_ejecucion))}
    n = 0
    for c in cursos:
        if not c.get("url") or c["url"] in vistos:
            continue
        vistos.add(c["url"])
        s.add(Curso(id_ejecucion=id_ejecucion, semestre=ejec.semestre, corte=ejec.corte, fecha_extraccion=date.today(), **c))
        n += 1
    if errores:
        ejec.errores_detalle = list(ejec.errores_detalle or []) + errores
        ejec.errores = "\n".join(ejec.errores_detalle)
    s.commit()
    return {"cursos": n, "errores": errores}


# ---------------------------------------------------------------------------
# Corrida completa en un solo proceso (CLI local y worker de servidor)
# ---------------------------------------------------------------------------
def correr_completa(s: Session, semestre: str, corte: str, id_ejecucion: str | None = None, ejecutado_por: str | None = None,
                    modo: str = "completa", fuentes: list[str] | None = None, limite_terminos: int | None = None,
                    limite_ubicaciones: int | None = None, max_por_particion: int | None = None, usar_llm: bool = True,
                    cursos: bool = True, ejecutor: str = "local", paralelo: bool = True) -> Ejecucion:
    """Prepara, extrae todas las fuentes (en paralelo, una hebra por fuente) y consolida."""
    from concurrent.futures import ThreadPoolExecutor

    from observatorio.db.sesion import fabrica_sesiones

    ejec = preparar(s, semestre, corte, id_ejecucion, ejecutado_por, modo, fuentes, limite_terminos, limite_ubicaciones,
                    max_por_particion, ejecutor=ejecutor)
    ejec.fase = "extrayendo"
    s.commit()
    idx = ejec.id_ejecucion
    lista = [f for (f,) in s.execute(select(Particion.fuente).where(Particion.id_ejecucion == idx).distinct())]
    url = str(s.get_bind().url.render_as_string(hide_password=False))

    def una_fuente(f: str) -> dict:
        with fabrica_sesiones(url)() as s2:
            try:
                return extraer(s2, idx, f)
            except Exception as e:  # noqa: BLE001 - cada fuente es independiente (RF-16)
                log.error("[%s] falló: %s", f, e)
                return {"fuente": f, "error": explicar_error(f, e)}

    if paralelo and len(lista) > 1:
        with ThreadPoolExecutor(max_workers=len(lista)) as ex:
            resumenes = list(ex.map(una_fuente, lista))
    else:
        resumenes = [una_fuente(f) for f in lista]
    for r in resumenes:
        log.info("Resumen extracción: %s", r)
    s.expire_all()
    if cursos:
        ejec.fase = "cursos"
        s.commit()
        try:
            terminos = None
            if limite_terminos:
                terminos = (leer_config(s).get("cursos") or {}).get("terminos", [])[:max(1, limite_terminos)]
            extraer_cursos_corrida(s, idx, terminos=terminos, max_por_termino=max_por_particion)
        except Exception as e:  # noqa: BLE001
            log.warning("Cursos falló: %s", e)
    return consolidar(s, idx, usar_llm=usar_llm, permitir_mini=(modo == "completa"))
