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
from sqlalchemy.orm import Session

from observatorio.db.crudas import asegurar_sesion_activa, commit_extraccion, insertar_cruda, ids_crudas_ejecucion_fuente
from observatorio.db.modelos import Curso, Ejecucion, Oferta, OfertaCruda, Particion, TerminoBusqueda, ahora
from observatorio.db.semilla import sembrar_todo
from observatorio.parametros import leer_config
from observatorio.plan_extraccion import (
    fuentes_para_corrida,
    max_particiones_fuente,
    objetivo_ofertas_corrida,
    ordenar_fuentes,
    presupuesto_fuente_carrera,
    presupuesto_por_carrera,
    presupuesto_por_fuente,
)
from observatorio.scraper.base import Consulta
from observatorio.scraper.http import FuenteBloqueada, explicar_error

from observatorio.normas_corrida import NOMBRES_FUENTE, normalizar_corte, normalizar_semestre

log = logging.getLogger("observatorio.corrida")


def contar_crudas_ejecucion(s: Session, id_ejecucion: str) -> int:
    return s.scalar(select(func.count()).select_from(OfertaCruda).where(OfertaCruda.id_ejecucion == id_ejecucion)) or 0


def limite_extraccion_corrida(cfg: dict, ejec: Ejecucion) -> int:
    """Alias histórico: objetivo de ofertas crudas por corrida (congelado en ejec.parametros al preparar)."""
    return objetivo_ofertas_corrida(cfg, ejec.parametros)


def contar_crudas_fuente(s: Session, id_ejecucion: str, fuente: str) -> int:
    nombre = NOMBRES_FUENTE.get(fuente, fuente)
    return int(
        s.scalar(
            select(func.count())
            .select_from(OfertaCruda)
            .where(OfertaCruda.id_ejecucion == id_ejecucion, OfertaCruda.fuente == nombre)
        )
        or 0
    )


def contar_crudas_carrera(s: Session, id_ejecucion: str, carrera: str) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(OfertaCruda)
            .where(OfertaCruda.id_ejecucion == id_ejecucion, OfertaCruda.carrera_termino == carrera)
        )
        or 0
    )


def contar_crudas_fuente_carrera(s: Session, id_ejecucion: str, fuente: str, carrera: str) -> int:
    nombre = NOMBRES_FUENTE.get(fuente, fuente)
    return int(
        s.scalar(
            select(func.count())
            .select_from(OfertaCruda)
            .where(OfertaCruda.id_ejecucion == id_ejecucion, OfertaCruda.fuente == nombre,
                   OfertaCruda.carrera_termino == carrera)
        )
        or 0
    )


def crear_extractor(fuente: str, cfg_fuente: dict):
    retraso = tuple(cfg_fuente.get("retraso_segundos") or (2.0, 4.0))
    if fuente == "linkedin":
        from observatorio.scraper.linkedin import LinkedIn
        return LinkedIn(retraso=retraso)
    if fuente == "indeed":
        from observatorio.scraper.jobspy_fuentes import Indeed
        return Indeed(retraso=retraso)
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
    objetivo = objetivo_ofertas_corrida(cfg, ejec.parametros)
    ejec.meta_ofertas = objetivo
    if os.getenv("GITHUB_RUN_ID"):
        ejec.github_run_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"

    activas = fuentes_para_corrida(cfg, fuentes)
    presupuesto = presupuesto_por_fuente(objetivo, activas, cfg) if objetivo > 0 else {}
    presupuesto_carreras = presupuesto_por_carrera(objetivo, cfg) if objetivo > 0 else {}
    ejec.parametros = {
        **(ejec.parametros or {}),
        "objetivo_ofertas_corrida": objetivo,
        "presupuesto_fuentes": presupuesto,
        "presupuesto_carreras": presupuesto_carreras,
        "presupuesto_fuente_carrera": presupuesto_fuente_carrera(presupuesto, cfg),
    }
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


FACTOR_CONSULTAS = 4  # consultas planeadas por cada consulta "llena" que cabría en el cupo
MIN_CONSULTAS_CARRERA = 4  # mínimo de consultas por fuente y carrera
RONDAS_RELLENO = 3  # rondas extra si la corrida no llega al objetivo
CONSULTAS_RELLENO = 6  # consultas nuevas por fuente y carrera en cada ronda


def crear_particiones(s: Session, ejec: Ejecucion, fuentes: list[str], terminos, ubicaciones: list[dict], cfg: dict,
                      mini: bool, max_por_particion: int | None = None, extra_por_carrera: int | None = None,
                      carreras: set[str] | None = None) -> int:
    """Crea las consultas (término × ciudad) por fuente.

    Las consultas se reparten entre carreras según el cupo fuente×carrera y se intercalan
    (Administración, Contaduría, Economía, Administración, ...), y dentro de cada carrera se
    rotan los términos antes de repetir ciudad. Así un tope bajo no deja todo en la primera
    carrera ni en el primer término.
    """
    existentes = {(p.fuente, p.termino, p.ubicacion) for p in s.scalars(select(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion))}
    params = ejec.parametros or {}
    presupuesto = params.get("presupuesto_fuentes") or {}
    cupo_fc = params.get("presupuesto_fuente_carrera") or presupuesto_fuente_carrera(presupuesto, cfg)
    fuentes_orden = ordenar_fuentes(fuentes)
    por_carrera: dict[str, list] = {}
    for t in terminos:
        por_carrera.setdefault(t.carrera, []).append(t)
    n = 0
    for f in fuentes_orden:
        max_part_f = int(max_por_particion or cfg["fuentes"].get(f, {}).get("max_por_particion", 100))
        cupo = presupuesto.get(f)
        con_tope = not mini and not extra_por_carrera and cupo is not None and int(cupo) > 0
        factor = max(1, int(cfg.get("factor_consultas", FACTOR_CONSULTAS)))
        colas: dict[str, list] = {}
        for carrera, ts in por_carrera.items():
            if carreras is not None and carrera not in carreras:
                continue
            ts_f = [t for t in ts if not [x for x in (t.fuentes or "").split(",") if x.strip()]
                    or f in [x.strip() for x in (t.fuentes or "").split(",")]]
            pares = []
            for u in ubicaciones:  # primero todos los términos en la ciudad principal, luego la siguiente
                lugar = u.get(f)
                if lugar is None or (lugar == "" and f in ("linkedin", "indeed")):
                    continue
                clave_u = f"{u['nombre']}|{lugar}|{'remoto' if u.get('remoto') else ''}"
                for t in ts_f:
                    if (f, t.termino, clave_u) not in existentes:
                        pares.append((t, clave_u))
            if con_tope:
                cupo_c = int((cupo_fc.get(f) or {}).get(carrera) or 0)
                if cupo_c <= 0:
                    continue
                # Una consulta casi nunca trae max_por_particion ofertas nuevas (repetidas, ventana de 30 días,
                # pocas vacantes en ciudades pequeñas): se planean varias de más; el cupo corta la extracción.
                pares = pares[: max(MIN_CONSULTAS_CARRERA, max_particiones_fuente(cupo_c, max_part_f) * factor)]
            elif extra_por_carrera:
                pares = pares[:extra_por_carrera]
            colas[carrera] = pares
        i = 0
        while any(i < len(v) for v in colas.values()):
            for pares in colas.values():
                if i < len(pares):
                    t, clave_u = pares[i]
                    if (f, t.termino, clave_u) in existentes:
                        continue
                    s.add(Particion(id_ejecucion=ejec.id_ejecucion, fuente=f, termino=t.termino, carrera=t.carrera,
                                    ubicacion=clave_u, mini=mini, ofertas=0))
                    existentes.add((f, t.termino, clave_u))
                    n += 1
            i += 1
    if max_por_particion:
        ejec.parametros = {**(ejec.parametros or {}), "max_por_particion": max_por_particion}
    s.flush()
    return n


def matriz(s: Session, id_ejecucion: str) -> list[dict]:
    """Trabajos paralelos para GitHub Actions: un elemento por fuente × fragmento (LinkedIn primero)."""
    cfg = leer_config(s)
    fuentes = ordenar_fuentes(
        [f for (f,) in s.execute(select(Particion.fuente).where(Particion.id_ejecucion == id_ejecucion).distinct())]
    )
    salida = []
    for f in fuentes:
        n = max(1, int(cfg["fuentes"].get(f, {}).get("fragmentos", 1)))
        salida.extend({"fuente": f, "fragmento": i, "fragmentos": n} for i in range(n))
    return salida


# ---------------------------------------------------------------------------
# 2. Extraer
# ---------------------------------------------------------------------------
def extraer(s: Session, id_ejecucion: str, fuente: str, fragmento: int = 0, fragmentos: int = 1,
            max_minutos: float | None = None, solo_mini: bool = False, relleno: bool = False) -> dict:
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
    objetivo = objetivo_ofertas_corrida(cfg, ejec.parametros)
    cupo_fuente = int((ejec.parametros or {}).get("presupuesto_fuentes", {}).get(fuente) or 0)
    presupuesto_carreras = (ejec.parametros or {}).get("presupuesto_carreras") or {}
    cupos_fc = ((ejec.parametros or {}).get("presupuesto_fuente_carrera") or {}).get(fuente)
    if cupos_fc is None and cupo_fuente:
        cupos_fc = presupuesto_fuente_carrera({fuente: cupo_fuente}, cfg).get(fuente, {})
    cupos_fc = cupos_fc or {}

    def crudas_carrera(c: str) -> int:
        if relleno:
            return _contar_sin_autoflush(s, lambda: contar_crudas_carrera(s, id_ejecucion, c))
        return _contar_sin_autoflush(s, lambda: contar_crudas_fuente_carrera(s, id_ejecucion, fuente, c))

    if relleno:
        # Relleno: lo que otra fuente no alcanzó lo puede cubrir esta; sólo se respeta el cupo total por carrera
        cupo_fuente = 0
        cupos_fc = {c: int(v) for c, v in presupuesto_carreras.items()}

    resumen = {"fuente": nombre, "particiones": len(particiones), "hechas": 0, "ofertas": 0, "errores": 0, "bloqueada": False,
               "objetivo_corrida": objetivo or None, "cupo_fuente": cupo_fuente or None,
               "presupuesto_carreras": presupuesto_carreras or None}
    log.info("[%s] Fragmento %d/%d: %d consultas pendientes%s", nombre, fragmento + 1, fragmentos, len(particiones),
             f" (objetivo {objetivo} crudas, cupo fuente {cupo_fuente})" if objetivo else "")
    detenido_por_tope = False
    for p in particiones:
        asegurar_sesion_activa(s)
        cupo_carrera = int(cupos_fc.get(p.carrera) or 0)
        if solo_mini:
            cupo_carrera = 0
        if cupo_carrera and crudas_carrera(p.carrera) >= cupo_carrera:
            # La carrera ya llenó su cupo en esta fuente: la consulta no se hace (no es un error ni queda pendiente)
            p.estado = "omitida"
            p.error = None
            resumen["omitidas_por_cupo"] = resumen.get("omitidas_por_cupo", 0) + 1
            commit_extraccion(s)
            continue
        if objetivo and _contar_sin_autoflush(s, lambda: contar_crudas_ejecucion(s, id_ejecucion)) >= objetivo:
            log.info("[%s] Objetivo de corrida alcanzado (%d ofertas crudas)", nombre, objetivo)
            resumen["tope_alcanzado"] = True
            detenido_por_tope = True
            break
        if cupo_fuente and _contar_sin_autoflush(s, lambda: contar_crudas_fuente(s, id_ejecucion, fuente)) >= cupo_fuente:
            log.info("[%s] Cupo de fuente alcanzado (%d ofertas crudas)", nombre, cupo_fuente)
            resumen["cupo_fuente_alcanzado"] = True
            detenido_por_tope = True
            break
        if max_minutos and (time.time() - inicio) / 60 > max_minutos:
            log.info("[%s] Se alcanzó el tiempo máximo; lo pendiente queda para la próxima reanudación", nombre)
            break
        nombre_u, lugar, remoto = p.ubicacion.split("|")
        restante_global = (
            objetivo - _contar_sin_autoflush(s, lambda: contar_crudas_ejecucion(s, id_ejecucion))
        ) if objetivo else max_part
        restante_fuente = (
            cupo_fuente - _contar_sin_autoflush(s, lambda: contar_crudas_fuente(s, id_ejecucion, fuente))
        ) if cupo_fuente else max_part
        restante_carrera = (cupo_carrera - crudas_carrera(p.carrera)) if cupo_carrera else max_part
        max_res = max(1, min(max_part, restante_global, restante_fuente, restante_carrera))
        c = Consulta(fuente=fuente, termino=p.termino, ubicacion=lugar, nombre_ubicacion=nombre_u, carrera=p.carrera,
                     remoto=bool(remoto), max_resultados=max_res, ventana_dias=int(cfg.get("ventana_dias", 30)))
        p.intentos += 1
        conocidos |= ids_crudas_ejecucion_fuente(s, id_ejecucion, nombre)
        n = 0
        try:
            for o in extractor.extraer(c, lambda idf: idf in conocidos):
                asegurar_sesion_activa(s)
                if objetivo and _contar_sin_autoflush(s, lambda: contar_crudas_ejecucion(s, id_ejecucion)) >= objetivo:
                    detenido_por_tope = True
                    resumen["tope_alcanzado"] = True
                    break
                if cupo_fuente and _contar_sin_autoflush(s, lambda: contar_crudas_fuente(s, id_ejecucion, fuente)) >= cupo_fuente:
                    detenido_por_tope = True
                    resumen["cupo_fuente_alcanzado"] = True
                    break
                if cupo_carrera and crudas_carrera(p.carrera) >= cupo_carrera:
                    resumen["cupo_carrera_alcanzado"] = True
                    break  # sólo esta carrera llenó su cupo: se sigue con las demás consultas
                if o.id_fuente in conocidos:
                    continue
                if insertar_cruda(
                    s,
                    id_ejecucion=id_ejecucion,
                    fuente=o.fuente,
                    id_fuente=o.id_fuente,
                    termino=p.termino,
                    carrera_termino=p.carrera,
                    ubicacion=nombre_u,
                    datos=o.a_dict(),
                ):
                    conocidos.add(o.id_fuente)
                    n += 1
                    if n % 25 == 0:
                        commit_extraccion(s)  # guardar lo ya extraído (RF-16)
                else:
                    conocidos.add(o.id_fuente)
            if detenido_por_tope:
                p.estado = "hecha"
                p.error = None
                resumen["hechas"] += 1
            else:
                p.estado = "hecha"
                p.error = None
                resumen["hechas"] += 1
        except FuenteBloqueada as e:
            asegurar_sesion_activa(s)
            p.estado = "error"
            p.error = explicar_error(fuente, e)
            resumen["bloqueada"] = True
            resumen["errores"] += 1
            log.warning("[%s] %s", nombre, p.error)
        except Exception as e:  # noqa: BLE001 - una consulta fallida no detiene las demás
            asegurar_sesion_activa(s)
            p.estado = "error"
            p.error = explicar_error(fuente, e)
            resumen["errores"] += 1
            log.warning("[%s] '%s' en %s: %s", nombre, p.termino, nombre_u, p.error)
        p.ofertas += n
        p.omitidas = (p.omitidas or 0) + int(c.opciones.get("stats", {}).get("omitidas", 0))
        resumen["ofertas"] += n
        commit_extraccion(s)
        log.info("[%s] '%s' en %s: %d ofertas nuevas", nombre, p.termino, nombre_u, n)
        if detenido_por_tope:
            log.info("[%s] Objetivo de corrida alcanzado (%d ofertas crudas)", nombre, objetivo)
            break
        if resumen["bloqueada"]:
            log.warning("[%s] Se detiene este fragmento para no insistir; se puede reanudar más tarde", nombre)
            break
    return resumen


def _contar_sin_autoflush(s: Session, fn):
    with s.no_autoflush:
        return fn()


# ---------------------------------------------------------------------------
# 3. Consolidar
# ---------------------------------------------------------------------------
def total_corte(s: Session, semestre: str, corte: str) -> int:
    return s.scalar(select(func.count()).select_from(Oferta).where(Oferta.semestre == semestre, Oferta.corte == corte)) or 0


def cerrar_corrida_workflow(
    s: Session,
    id_ejecucion: str,
    mensaje: str,
    *,
    conclusion_github: str | None = None,
) -> Ejecucion:
    """Cierra en BD una corrida cuyo workflow de GitHub falló o se interrumpió."""
    from observatorio.corridas_cierre import cerrar_ejecucion_error

    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ValueError(f"No existe la ejecución {id_ejecucion}")
    if cerrar_ejecucion_error(s, ejec, mensaje, conclusion_github=conclusion_github):
        s.commit()
    return ejec


def _procesar_con_reintento(s: Session, proc, intentos: int = 3) -> None:
    """Procesa las crudas; si se cae la conexión con la BD (Neon cierra el SSL), reconecta y sigue.

    Cada bloque se confirma al terminar, así que un reintento retoma desde el bloque que se perdió.
    """
    from sqlalchemy.exc import OperationalError

    for i in range(intentos):
        try:
            proc.procesar_pendientes()
            return
        except OperationalError as e:
            try:
                s.rollback()  # descarta la conexión rota; la siguiente consulta abre otra (pool_pre_ping)
            except Exception:  # noqa: BLE001
                pass
            if i == intentos - 1:
                raise
            log.warning("Se perdió la conexión con la base al procesar (intento %d/%d); se reintenta: %s",
                        i + 1, intentos, str(e).splitlines()[0][:200])
            time.sleep(5 * (i + 1))


def consolidar(s: Session, id_ejecucion: str, usar_llm: bool = True, permitir_mini: bool = True) -> Ejecucion:
    from observatorio.pipeline.procesar import Procesador

    cfg = leer_config(s)
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ValueError(f"No existe la ejecución {id_ejecucion}")
    ejec.fase = "procesando"
    commit_extraccion(s)
    proc = Procesador(s, ejec, cfg, usar_llm=usar_llm)
    try:
        _procesar_con_reintento(s, proc)

        # Mini corrida automática si no se llegó a la meta
        mini_cfg = cfg.get("mini_corrida") or {}
        total = total_corte(s, ejec.semestre, ejec.corte)
        objetivo = objetivo_ofertas_corrida(cfg, ejec.parametros)
        crudas = contar_crudas_ejecucion(s, id_ejecucion)
        puede_mini = objetivo <= 0 or crudas >= objetivo
        if permitir_mini and puede_mini and ejec.modo == "completa" and mini_cfg.get("habilitada") and not ejec.mini_corrida \
                and total < (ejec.meta_ofertas or 0):
            log.info("Hay %d ofertas relevantes en el corte (meta %s): se inicia la mini corrida con términos ampliados",
                     total, ejec.meta_ofertas)
            ejec.mini_corrida = True
            ejec.fase = "mini_corrida"
            terminos = list(s.scalars(select(TerminoBusqueda).where(TerminoBusqueda.activo.is_(True), TerminoBusqueda.tipo == "ampliado")))
            fuentes = fuentes_para_corrida(cfg, mini_cfg.get("fuentes", ["linkedin", "indeed", "computrabajo"]))
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
                    asegurar_sesion_activa(s)
            ejec.fase = "procesando"
            s.commit()
            _procesar_con_reintento(s, proc)

        proc.guardar_no_catalogados()
        finalizar(s, ejec, proc)
        s.commit()
        return ejec
    except Exception as e:
        asegurar_sesion_activa(s)
        cerrar_corrida_workflow(
            s,
            id_ejecucion,
            f"Consolidación interrumpida: {explicar_error('consolidar', e)}",
            conclusion_github="failure",
        )
        raise


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
        if p.estado == "omitida":
            d["consultas_omitidas_cupo"] = d.get("consultas_omitidas_cupo", 0) + 1
            continue
        d["consultas"] += 1
        d["consultas_con_error"] += 1 if p.estado == "error" else 0
    for o in guardadas:
        por_fuente.setdefault(o.fuente, {"encontradas": 0, "guardadas": 0, "consultas": 0, "consultas_con_error": 0})["guardadas"] += 1
    hechas_por_fuente = Counter(NOMBRES_FUENTE.get(p.fuente, p.fuente) for p in parts if p.estado == "hecha" and (p.intentos or 0) > 0)
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
        if hechas_por_fuente.get(nombre) and d["encontradas"] == 0 and d["consultas_con_error"] == 0:
            errores.append(
                f"{nombre} no devolvió ofertas en ninguna consulta. Puede ser un bloqueo silencioso de la fuente o un cambio en la página."
            )
    pendientes = sum(1 for p in parts if p.estado == "pendiente")
    if pendientes:
        errores.append(f"Quedaron {pendientes} consultas sin hacer (tiempo agotado o fuente bloqueada). "
                       f"Puede reanudar la corrida con el mismo id: {ejec.id_ejecucion}.")
    objetivo = objetivo_ofertas_corrida(leer_config(s), ejec.parametros)
    if objetivo > 0 and crudas >= objetivo:
        pass  # parada esperada por objetivo de extracción
    elif ejec.total_corte < (ejec.meta_ofertas or 0) and ejec.modo == "completa" and crudas < objetivo:
        errores.append(f"El corte tiene {ejec.total_corte} ofertas relevantes; no alcanzó la meta de {ejec.meta_ofertas}.")
    logro_fuentes = {NOMBRES_FUENTE.get(f, f): contar_crudas_fuente(s, ejec.id_ejecucion, f) for f in ordenar_fuentes(
        [k for k in (ejec.parametros or {}).get("presupuesto_fuentes", {})]
    )}
    logro_carreras = {
        c: contar_crudas_carrera(s, ejec.id_ejecucion, c) for c in (ejec.parametros or {}).get("presupuesto_carreras", {})
    }
    ejec.parametros = {
        **(ejec.parametros or {}),
        "logro_extraccion": {
            "objetivo": objetivo_ofertas_corrida(leer_config(s), ejec.parametros),
            "por_fuente": logro_fuentes,
            "por_carrera": logro_carreras,
        },
    }
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
def extraer_secuencial(s: Session, id_ejecucion: str, max_minutos: float | None = None) -> list[dict]:
    """Extrae fuente por fuente (LinkedIn primero), respetando el objetivo y cupos por fuente."""
    cfg = leer_config(s)
    ejec = s.get(Ejecucion, id_ejecucion)
    if ejec is None:
        raise ValueError(f"No existe la ejecución {id_ejecucion}")
    fuentes = ordenar_fuentes(
        [f for (f,) in s.execute(select(Particion.fuente).where(Particion.id_ejecucion == id_ejecucion).distinct())]
    )
    objetivo = objetivo_ofertas_corrida(cfg, ejec.parametros)
    t0 = time.time()
    resumenes: list[dict] = []
    for f in fuentes:
        if objetivo and contar_crudas_ejecucion(s, id_ejecucion) >= objetivo:
            log.info("Objetivo de corrida alcanzado antes de %s", f)
            break
        restante = None
        if max_minutos is not None:
            restante = max_minutos - (time.time() - t0) / 60
            if restante <= 0:
                log.info("Tiempo máximo agotado antes de %s", f)
                break
        n_frag = max(1, int(cfg["fuentes"].get(f, {}).get("fragmentos", 1)))
        detenido = False
        for frag in range(n_frag):
            r = extraer(s, id_ejecucion, f, frag, n_frag, max_minutos=restante)
            resumenes.append(r)
            if r.get("tope_alcanzado") or r.get("cupo_fuente_alcanzado") or r.get("bloqueada"):
                detenido = True
                break
        if detenido and (r.get("tope_alcanzado") or r.get("bloqueada")):
            if r.get("tope_alcanzado"):
                break
            continue
        if objetivo and contar_crudas_ejecucion(s, id_ejecucion) >= objetivo:
            break

    # Relleno: si no se llegó al objetivo, más consultas (términos/ciudades siguientes) para las carreras que faltan
    if objetivo:
        presupuesto_carreras = (ejec.parametros or {}).get("presupuesto_carreras") or {}
        terminos = list(s.scalars(select(TerminoBusqueda).where(TerminoBusqueda.activo.is_(True), TerminoBusqueda.tipo == "principal")
                                  .order_by(TerminoBusqueda.carrera, TerminoBusqueda.id)))
        for ronda in range(1, RONDAS_RELLENO + 1):
            if contar_crudas_ejecucion(s, id_ejecucion) >= objetivo:
                break
            if max_minutos is not None and max_minutos - (time.time() - t0) / 60 <= 1:
                break
            faltan = {c for c, cupo in presupuesto_carreras.items() if contar_crudas_carrera(s, id_ejecucion, c) < int(cupo)}
            if not faltan:
                break
            nuevas = crear_particiones(s, ejec, fuentes, terminos, cfg["ubicaciones"], cfg, mini=False,
                                       extra_por_carrera=CONSULTAS_RELLENO, carreras=faltan)
            commit_extraccion(s)
            log.info("Relleno %d: faltan %d crudas para el objetivo; %d consultas nuevas (%s)", ronda,
                     objetivo - contar_crudas_ejecucion(s, id_ejecucion), nuevas, ", ".join(sorted(faltan)))
            for f in fuentes:
                if contar_crudas_ejecucion(s, id_ejecucion) >= objetivo:
                    break
                restante = None if max_minutos is None else max_minutos - (time.time() - t0) / 60
                if restante is not None and restante <= 1:
                    break
                r = extraer(s, id_ejecucion, f, 0, 1, max_minutos=restante, relleno=True)
                r["relleno"] = ronda
                resumenes.append(r)
    return resumenes


def correr_completa(s: Session, semestre: str, corte: str, id_ejecucion: str | None = None, ejecutado_por: str | None = None,
                    modo: str = "completa", fuentes: list[str] | None = None, limite_terminos: int | None = None,
                    limite_ubicaciones: int | None = None, max_por_particion: int | None = None, usar_llm: bool = True,
                    cursos: bool = True, ejecutor: str = "local", paralelo: bool = True) -> Ejecucion:
    """Prepara, extrae todas las fuentes (LinkedIn primero; hebras solo entre fragmentos de una fuente) y consolida."""
    from observatorio.db.sesion import fabrica_sesiones

    ejec = preparar(s, semestre, corte, id_ejecucion, ejecutado_por, modo, fuentes, limite_terminos, limite_ubicaciones,
                    max_por_particion, ejecutor=ejecutor)
    ejec.fase = "extrayendo"
    s.commit()
    idx = ejec.id_ejecucion
    lista = ordenar_fuentes(
        [f for (f,) in s.execute(select(Particion.fuente).where(Particion.id_ejecucion == idx).distinct())]
    )
    url = str(s.get_bind().url.render_as_string(hide_password=False))

    def una_fuente(f: str) -> dict:
        with fabrica_sesiones(url)() as s2:
            try:
                cfg_f = leer_config(s2)["fuentes"].get(f, {})
                fragmentos = max(1, int(cfg_f.get("fragmentos", 1)))
                acum = {"fuente": NOMBRES_FUENTE[f], "particiones": 0, "hechas": 0, "ofertas": 0, "errores": 0}
                for frag in range(fragmentos):
                    r = extraer(s2, idx, f, frag, fragmentos)
                    for k in ("particiones", "hechas", "ofertas", "errores"):
                        acum[k] += r.get(k, 0)
                    if r.get("tope_alcanzado") or r.get("cupo_fuente_alcanzado") or r.get("bloqueada"):
                        acum.update({k: r[k] for k in ("tope_alcanzado", "cupo_fuente_alcanzado", "bloqueada") if k in r})
                        break
                return acum
            except Exception as e:  # noqa: BLE001 - cada fuente es independiente (RF-16)
                log.error("[%s] falló: %s", f, e)
                return {"fuente": f, "error": explicar_error(f, e)}

    if paralelo and len(lista) > 1:
        resumenes = []
        for f in lista:
            if objetivo_ofertas_corrida(leer_config(s), ejec.parametros) and contar_crudas_ejecucion(s, idx) >= objetivo_ofertas_corrida(
                    leer_config(s), ejec.parametros):
                break
            resumenes.append(una_fuente(f))
            s.expire_all()
    else:
        resumenes = []
        for f in lista:
            resumenes.append(una_fuente(f))
            s.expire_all()
            if objetivo_ofertas_corrida(leer_config(s), ejec.parametros) and contar_crudas_ejecucion(s, idx) >= objetivo_ofertas_corrida(
                    leer_config(s), ejec.parametros):
                break
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
