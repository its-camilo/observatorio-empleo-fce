"""Procesamiento de ofertas crudas: limpieza, duplicados, clasificación,
detección de softwares, idiomas/habilidades y guardado (RF-05..RF-08, RF-17, RF-18)."""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatorio.db.modelos import Ejecucion, NoCatalogado, Oferta, OfertaCruda, OfertaSoftware, ahora
from observatorio.pipeline.clasificacion import ClasificadorReglas, Clasificacion
from observatorio.pipeline.dedup import _cerca, deduplicar
from observatorio.pipeline.habilidades import detectar_blandas, detectar_idiomas
from observatorio.pipeline.limpieza import normalizar_cruda
from observatorio.pipeline.llm import ClienteLLM
from observatorio.pipeline.no_catalogados import contar_no_catalogados
from observatorio.pipeline.software import DetectorSoftware
from observatorio.pipeline.valor_formativo import oferta_tiene_valor_formativo, tiene_descripcion_util
from observatorio.capitales import es_capital_departamental
from observatorio.texto import es_colombia, normalizar_clave

log = logging.getLogger("observatorio.procesar")

TAMANO_BLOQUE = 1500


@dataclass
class ResultadoProceso:
    crudas: int = 0
    fuera_de_colombia: int = 0
    fuera_de_capital: int = 0
    fuera_de_ventana: int = 0
    filtradas_tipo: int = 0
    duplicados: int = 0
    actualizadas: int = 0
    no_relevantes: int = 0
    guardadas: int = 0
    por_llm: int = 0
    por_respaldo: int = 0
    no_catalogados: Counter = field(default_factory=Counter)
    originales_nc: dict = field(default_factory=dict)
    ejemplo_nc: dict = field(default_factory=dict)

    def sumar(self, otro: "ResultadoProceso") -> None:
        for k in ("crudas", "fuera_de_colombia", "fuera_de_capital", "fuera_de_ventana", "filtradas_tipo", "duplicados",
                  "actualizadas", "no_relevantes", "guardadas", "por_llm", "por_respaldo"):
            setattr(self, k, getattr(self, k) + getattr(otro, k))


class Procesador:
    def __init__(self, s: Session, ejec: Ejecucion, cfg: dict, usar_llm: bool = True):
        self.s = s
        self.ejec = ejec
        self.cfg = cfg
        self.detector = DetectorSoftware.desde_bd(s)
        self.clasificador = ClasificadorReglas(
            cfg["reglas_carrera"],
            cfg["exclusion_titulo"],
            cfg["carreras"],
            cfg.get("exclusion_operativa_titulo") or [],
        )
        llm_cfg = dict(cfg.get("llm") or {})
        if not usar_llm:
            llm_cfg["habilitado"] = False
        self.llm = ClienteLLM(s, llm_cfg, cfg["carreras"], id_corrida=ejec.id_ejecucion)
        self.dedup_dias = int(cfg["dedup"].get("dias", 7))
        self.alcance = cfg["dedup"].get("alcance", "global")
        self.sufijo = "" if self.alcance == "global" else f"@{ejec.semestre}-{ejec.corte}"
        self.ventana = int(cfg.get("ventana_dias", 30))
        self.tipo = (cfg.get("tipo_oferta") or "ambas").lower()
        self.requiere_formativo = bool(cfg.get("requiere_software_o_habilidad", True))
        self.solo_capitales = bool(cfg.get("solo_capitales_departamento", True))
        self.total = ResultadoProceso()

    # ------------------------------------------------------------------
    def _existentes(self, claves: set[str], ids: set[str]) -> tuple[dict[str, list[Oferta]], dict[str, Oferta]]:
        por_clave: dict[str, list[Oferta]] = {}
        por_id: dict[str, Oferta] = {}
        claves_l, ids_l = list(claves), list(ids)
        for i in range(0, len(claves_l), 400):
            q = select(Oferta).where(Oferta.clave_dedup.in_(claves_l[i:i + 400]))
            if self.alcance != "global":
                q = q.where(Oferta.semestre == self.ejec.semestre, Oferta.corte == self.ejec.corte)
            for o in self.s.scalars(q):
                por_clave.setdefault(o.clave_dedup, []).append(o)
        for i in range(0, len(ids_l), 400):
            for o in self.s.scalars(select(Oferta).where(Oferta.id_oferta.in_(ids_l[i:i + 400]))):
                por_id[o.id_oferta] = o
        return por_clave, por_id

    def _aplicar_software(self, o: Oferta) -> None:
        dets = self.detector.detectar(o.cargo, o.descripcion or "", o.empresa or "")
        if o.softwares:  # oferta ya guardada: borrar primero para no chocar con la restricción única
            for x in list(o.softwares):
                self.s.delete(x)
            o.softwares = []
            self.s.flush()
        o.softwares = [OfertaSoftware(software=d.software, grupo_software=d.grupo, texto_encontrado=d.texto_encontrado[:255],
                                      carrera=o.carrera, semestre=o.semestre, corte=o.corte) for d in dets]
        o.num_softwares = len(dets)
        texto = f"{o.cargo}\n{o.descripcion or ''}"
        o.idiomas = detectar_idiomas(texto)[:255] or None
        o.habilidades_blandas = detectar_blandas(texto) or None

    # ------------------------------------------------------------------
    def procesar_bloque(self, crudas: list[OfertaCruda]) -> ResultadoProceso:
        r = ResultadoProceso(crudas=len(crudas))
        hoy = self.ejec.fecha or date.today()
        limite = hoy - timedelta(days=self.ventana + 2)
        filas = []
        for c in crudas:
            try:
                f = normalizar_cruda(c.datos, termino=c.termino, carrera_termino=c.carrera_termino, semestre=self.ejec.semestre,
                                     corte=self.ejec.corte, fecha_extraccion=hoy, id_ejecucion=self.ejec.id_ejecucion,
                                     sufijo_id=self.sufijo)
            except Exception as e:  # noqa: BLE001 - una oferta mal formada no detiene el resto
                log.warning("Oferta cruda %s no se pudo limpiar: %s", c.id, e)
                continue
            if not f["cargo"]:
                continue
            if not es_colombia(f["ubicacion_original"]):
                r.fuera_de_colombia += 1
                continue
            if self.solo_capitales and not es_capital_departamental(f["ciudad"], f["ubicacion_original"]):
                r.fuera_de_capital += 1
                continue
            if f["fecha_publicacion"] and f["fecha_publicacion"] < limite:
                r.fuera_de_ventana += 1
                continue
            if self.tipo == "practica" and not f["tipo_oferta"].startswith("Práctica") or \
                    self.tipo == "empleo" and f["tipo_oferta"].startswith("Práctica"):
                r.filtradas_tipo += 1
                continue
            filas.append(f)

        # 1) duplicados dentro del bloque
        unicas, dup = deduplicar(filas, self.dedup_dias)
        r.duplicados += dup

        # 2) duplicados contra el historial
        por_clave, por_id = self._existentes({u["clave_dedup"] for u in unicas}, {u["id_oferta"] for u in unicas})
        nuevas = []
        for u in unicas:
            previa = por_id.get(u["id_oferta"])
            if previa is None:
                previa = next((e for e in por_clave.get(u["clave_dedup"], [])
                               if _cerca(e.fecha_publicacion, u.get("fecha_publicacion"), self.dedup_dias)), None)
            if previa is None:
                nuevas.append(u)
                continue
            r.duplicados += 1
            if len(u["descripcion"] or "") > len(previa.descripcion or ""):
                previa.descripcion = u["descripcion"]
                previa.url = u["url"] or previa.url
                previa.sector = previa.sector or u.get("sector")
                self._aplicar_software(previa)
                r.actualizadas += 1

        # 3) clasificación: reglas, luego LLM para dudosas
        clasif: dict[str, Clasificacion] = {}
        dudosas = []
        for u in nuevas:
            c = self.clasificador.clasificar(u["cargo"], u["descripcion"], u.get("carrera_termino"))
            clasif[u["id_oferta"]] = c
            if c.estado == "dudosa":
                dudosas.append(u)
        if dudosas:
            respuestas = self.llm.clasificar([{"id": u["id_oferta"], **u} for u in dudosas]) if self.llm.habilitado else {}
            for u in dudosas:
                c = clasif[u["id_oferta"]]
                res = respuestas.get(u["id_oferta"])
                if res is not None:
                    r.por_llm += 1
                    relevante_llm = res["relevante"]
                    if relevante_llm and self.requiere_formativo:
                        ok, motivo_vf = oferta_tiene_valor_formativo(
                            u["cargo"],
                            u.get("descripcion") or "",
                            self.detector,
                            empresa=u.get("empresa") or "",
                            habilidades_llm=res.get("habilidades_tecnicas"),
                            herramientas_llm=res.get("herramientas_no_catalogadas"),
                            tiene_habilidad_cursable_llm=res.get("tiene_habilidad_cursable"),
                        )
                        if not ok:
                            relevante_llm = False
                            motivo_llm = f"LLM relevante pero sin valor formativo ({motivo_vf})"
                        else:
                            motivo_llm = "LLM"
                    else:
                        motivo_llm = "LLM"
                    clasif[u["id_oferta"]] = Clasificacion(
                        "relevante" if relevante_llm else "no_relevante",
                        res["carreras"] if relevante_llm else [],
                        c.puntajes,
                        motivo_llm,
                        "llm",
                    )
                    for h in res.get("herramientas_no_catalogadas") or []:
                        if not self.detector.coincide_algun_sinonimo(h):
                            k = normalizar_clave(h)
                            if k:
                                r.no_catalogados[k] += 1
                                r.originales_nc.setdefault(k, h)
                                r.ejemplo_nc.setdefault(k, u["id_oferta"])
                else:
                    r.por_respaldo += 1
                    clasif[u["id_oferta"]] = ClasificadorReglas.respaldo(c)

        # 4) guardar relevantes
        guardadas_dicts = []
        for u in nuevas:
            c = clasif[u["id_oferta"]]
            if c.estado != "relevante" or not c.carreras:
                r.no_relevantes += 1
                continue
            if self.requiere_formativo and c.clasificado_por != "llm" and tiene_descripcion_util(u.get("descripcion")):
                ok, _ = oferta_tiene_valor_formativo(
                    u["cargo"],
                    u.get("descripcion") or "",
                    self.detector,
                    empresa=u.get("empresa") or "",
                )
                if not ok:
                    r.no_relevantes += 1
                    continue
            o = Oferta(
                id_oferta=u["id_oferta"], fuente=u["fuente"], url=u["url"], fecha_publicacion=u["fecha_publicacion"],
                fecha_extraccion=u["fecha_extraccion"], semestre=u["semestre"], corte=u["corte"], cargo=u["cargo"],
                empresa=u["empresa"] or None, sector=u.get("sector"), ciudad=u["ciudad"], modalidad=u["modalidad"],
                tipo_oferta=u["tipo_oferta"], nivel_experiencia=u["nivel_experiencia"], carrera=c.carrera_texto[:255],
                termino_busqueda=(u["termino_busqueda"] or "")[:255], descripcion=u["descripcion"],
                carrera_principal=c.carreras[0], id_ejecucion=u["id_ejecucion"], id_fuente=u["id_fuente"],
                clave_dedup=u["clave_dedup"][:600], clasificado_por=c.clasificado_por,
            )
            self._aplicar_software(o)
            self.s.add(o)
            r.guardadas += 1
            guardadas_dicts.append({"id_oferta": o.id_oferta, "descripcion": o.descripcion, "empresa": o.empresa})

        # 5) términos no catalogados (RF-17), acumulados
        for x in contar_no_catalogados(guardadas_dicts, self.detector, min_frecuencia=1, max_terminos=100000):
            r.no_catalogados[x["termino"]] += x["frecuencia"]
            r.originales_nc.setdefault(x["termino"], x["termino_original"])
            r.ejemplo_nc.setdefault(x["termino"], x["ejemplo_id_oferta"])

        for c in crudas:
            c.procesada = True
        self.s.flush()
        return r

    def procesar_pendientes(self) -> ResultadoProceso:
        """Procesa todas las crudas no procesadas de la ejecución, por bloques."""
        while True:
            bloque = list(self.s.scalars(
                select(OfertaCruda).where(OfertaCruda.id_ejecucion == self.ejec.id_ejecucion, OfertaCruda.procesada.is_(False))
                .order_by(OfertaCruda.id).limit(TAMANO_BLOQUE)))
            if not bloque:
                break
            r = self.procesar_bloque(bloque)
            self.total.sumar(r)
            self.total.no_catalogados.update(r.no_catalogados)
            for k, v in r.originales_nc.items():
                self.total.originales_nc.setdefault(k, v)
            for k, v in r.ejemplo_nc.items():
                self.total.ejemplo_nc.setdefault(k, v)
            self.s.commit()
            log.info("Procesadas %d ofertas crudas: %d guardadas, %d duplicadas, %d no relevantes",
                     r.crudas, r.guardadas, r.duplicados, r.no_relevantes)
        return self.total

    def guardar_no_catalogados(self) -> int:
        cfg = self.cfg.get("no_catalogados") or {}
        minimo = int(cfg.get("min_frecuencia", 3))
        maximo = int(cfg.get("max_terminos", 300))
        n = 0
        for termino, freq in self.total.no_catalogados.most_common(maximo):
            if freq < minimo:
                break
            fila = self.s.scalars(select(NoCatalogado).where(NoCatalogado.termino == termino)).one_or_none()
            if fila is None:
                fila = NoCatalogado(termino=termino, termino_original=self.total.originales_nc.get(termino, termino)[:160],
                                    ejemplo_id_oferta=self.total.ejemplo_nc.get(termino))
                self.s.add(fila)
            fila.frecuencia_total = (fila.frecuencia_total or 0) + freq
            fila.frecuencia_ultima = freq
            fila.semestre, fila.corte = self.ejec.semestre, self.ejec.corte
            fila.ultima_vez = ahora()
            n += 1
        self.s.flush()
        return n
