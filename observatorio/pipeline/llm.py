"""Clasificación de ofertas dudosas con modelos gratuitos de OpenRouter.

- Solo se usa para ofertas que las reglas no resuelven.
- Lotes de ~20 ofertas por solicitud, respuesta en JSON.
- Caché por hash de la oferta (tabla `llm_cache`): una oferta ya clasificada no
  se vuelve a enviar.
- Respeta el tope diario (contador en la tabla `config`, clave `llm_uso`) y un
  ritmo por minuto; ante 429 espera y prueba el siguiente modelo de la lista.
- Si no hay API key, se agotó el cupo o todos los modelos fallan, devuelve
  None y el pipeline aplica la regla de respaldo.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date

import requests
from sqlalchemy.orm import Session

from observatorio.config import ajustes
from observatorio.pipeline.openrouter_modelos import resolver_modelos
from observatorio.texto import hash_texto

log = logging.getLogger("observatorio.llm")

URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT_SISTEMA = """Eres un clasificador de ofertas laborales de Colombia para el Observatorio de la Facultad de Ciencias Económicas.
Para cada oferta decide si es relevante para profesionales o estudiantes de estas carreras: {carreras}.
Una oferta es relevante si el cargo lo puede ocupar alguien formado en alguna de esas carreras (contabilidad, auditoría, impuestos,
finanzas, economía, análisis económico o de datos de negocio, riesgo, administración, gestión, procesos, proyectos, comercial, talento humano, etc.).
No es relevante si es de salud, ingeniería de software, oficios operativos, docencia de otras áreas, etc.
Responde SOLO con JSON con esta forma exacta:
{{"resultados": [{{"id": "<id>", "relevante": true, "carreras": ["<carrera principal>", "..."], "herramientas_no_catalogadas": ["..."]}}]}}
"carreras" debe usar exactamente los nombres dados, la principal primero, máximo 5; vacía si no es relevante.
"herramientas_no_catalogadas": programas o herramientas de software mencionados (máximo 5), puede ir vacía."""


class ClienteLLM:
    def __init__(self, s: Session, cfg_llm: dict, carreras: list[str], id_corrida: str | None = None):
        a = ajustes()
        self.s = s
        self.api_key = a.openrouter_api_key
        cfg_lista = cfg_llm.get("modelos")
        preferidos = [m for m in cfg_lista if m] if isinstance(cfg_lista, list) and cfg_lista else a.openrouter_modelos
        self.modelos = resolver_modelos(preferidos=preferidos, api_key=self.api_key, id_corrida=id_corrida)
        self.modelos_preferidos = preferidos
        self.tamano_lote = int(cfg_llm.get("tamano_lote", 20))
        self.max_dia = int(cfg_llm.get("max_solicitudes_dia", 1000))
        self.max_corrida = int(cfg_llm.get("max_solicitudes_corrida", 600))
        self.intervalo = 60.0 / max(1, int(cfg_llm.get("solicitudes_por_minuto", 16)))
        base_habilitado = bool(cfg_llm.get("habilitado", True)) and bool(self.api_key)
        self.habilitado = base_habilitado and bool(self.modelos)
        self.carreras = carreras
        self.solicitudes = 0
        self.errores = 0
        self.desde_cache = 0
        self._ultima = 0.0
        if not self.api_key:
            self.motivo_inactivo = "sin OPENROUTER_API_KEY"
        elif not base_habilitado:
            self.motivo_inactivo = "desactivado en configuración"
        elif not self.modelos:
            self.motivo_inactivo = "ningún modelo gratuito disponible en OpenRouter"
        else:
            self.motivo_inactivo = ""

    # ------------------------------------------------------------------ cupo
    def _uso_hoy(self) -> int:
        from observatorio.db.modelos import Config

        fila = self.s.get(Config, "llm_uso")
        if fila and isinstance(fila.valor, dict) and fila.valor.get("fecha") == date.today().isoformat():
            return int(fila.valor.get("solicitudes", 0))
        return 0

    def _sumar_uso(self) -> None:
        from observatorio.db.modelos import Config

        fila = self.s.get(Config, "llm_uso")
        hoy = date.today().isoformat()
        n = self._uso_hoy() + 1
        if fila is None:
            self.s.add(Config(clave="llm_uso", valor={"fecha": hoy, "solicitudes": n},
                              descripcion="Contador interno de solicitudes diarias a OpenRouter"))
        else:
            fila.valor = {"fecha": hoy, "solicitudes": n}
        self.s.flush()

    def hay_cupo(self) -> bool:
        return self.habilitado and self.solicitudes < self.max_corrida and self._uso_hoy() < self.max_dia

    # ------------------------------------------------------------------ caché
    @staticmethod
    def clave(oferta: dict) -> str:
        return hash_texto(oferta.get("cargo", ""), oferta.get("empresa", ""), (oferta.get("descripcion") or "")[:1500])

    def _cache(self, h: str):
        from observatorio.db.modelos import LlmCache

        fila = self.s.get(LlmCache, h)
        return fila.resultado if fila else None

    def _guardar_cache(self, h: str, resultado: dict, modelo: str) -> None:
        from observatorio.db.modelos import LlmCache

        if self.s.get(LlmCache, h) is None:
            self.s.add(LlmCache(hash=h, resultado=resultado, modelo=modelo))

    # ------------------------------------------------------------------ API
    def _llamar(self, mensajes: list[dict]) -> tuple[dict | None, str]:
        if not self.modelos:
            return None, ""
        for modelo in self.modelos:
            for intento in range(3):
                espera = self.intervalo - (time.time() - self._ultima)
                if espera > 0:
                    time.sleep(espera)
                self._ultima = time.time()
                try:
                    r = requests.post(URL, timeout=90, headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/its-camilo/observatorio-empleo-fce",
                        "X-Title": "Observatorio de Empleo FCE",
                    }, json={"model": modelo, "messages": mensajes, "temperature": 0,
                             "response_format": {"type": "json_object"}})
                except requests.RequestException as e:
                    log.warning("OpenRouter no respondió (%s): %s", modelo, e)
                    time.sleep(5 * (intento + 1))
                    continue
                self.solicitudes += 1
                self._sumar_uso()
                if r.status_code == 429:
                    espera = float(r.headers.get("Retry-After") or 20 * (intento + 1))
                    log.info("OpenRouter pidió esperar (429) con %s; espera %.0fs", modelo, espera)
                    time.sleep(min(espera, 120))
                    continue
                if r.status_code in (400, 402, 404):
                    log.info("Modelo %s no disponible (%s); se prueba el siguiente", modelo, r.status_code)
                    break
                if r.status_code >= 500:
                    time.sleep(10 * (intento + 1))
                    continue
                try:
                    contenido = r.json()["choices"][0]["message"]["content"]
                    return _parsear_json(contenido), modelo
                except Exception as e:  # respuesta mal formada
                    log.info("Respuesta no válida de %s: %s", modelo, e)
                    self.errores += 1
                    break
            if not self.hay_cupo():
                break
        return None, ""

    def clasificar(self, ofertas: list[dict]) -> dict[str, dict]:
        """Recibe dicts con id, cargo, empresa, termino_busqueda, descripcion.

        Devuelve {id: {"relevante": bool, "carreras": [...], "herramientas_no_catalogadas": [...]}}
        solo para las ofertas que se pudieron clasificar.
        """
        salida: dict[str, dict] = {}
        pendientes = []
        for o in ofertas:
            h = self.clave(o)
            c = self._cache(h)
            if c is not None:
                salida[o["id"]] = c
                self.desde_cache += 1
            else:
                pendientes.append((h, o))
        if not self.habilitado:
            return salida
        sistema = PROMPT_SISTEMA.format(carreras=", ".join(self.carreras))
        for i in range(0, len(pendientes), self.tamano_lote):
            if not self.hay_cupo():
                log.info("Cupo de OpenRouter agotado para esta corrida; el resto usa reglas de respaldo")
                break
            lote = pendientes[i:i + self.tamano_lote]
            cuerpo = [{"id": o["id"], "cargo": o.get("cargo", ""), "empresa": o.get("empresa", ""),
                       "termino": o.get("termino_busqueda", ""), "descripcion": (o.get("descripcion") or "")[:1200]}
                      for _, o in lote]
            datos, modelo = self._llamar([
                {"role": "system", "content": sistema},
                {"role": "user", "content": json.dumps({"ofertas": cuerpo}, ensure_ascii=False)},
            ])
            if not datos:
                continue
            por_id = {str(x.get("id")): x for x in datos.get("resultados", []) if isinstance(x, dict)}
            for h, o in lote:
                x = por_id.get(str(o["id"]))
                if x is None:
                    continue
                res = {
                    "relevante": bool(x.get("relevante")),
                    "carreras": [c for c in (x.get("carreras") or []) if c in self.carreras][:5],
                    "herramientas_no_catalogadas": [str(t)[:60] for t in (x.get("herramientas_no_catalogadas") or [])][:5],
                }
                if res["relevante"] and not res["carreras"]:
                    continue  # respuesta incoherente: se deja a las reglas
                salida[o["id"]] = res
                self._guardar_cache(h, res, modelo)
            self.s.flush()
        return salida

    def resumen(self) -> dict:
        return {
            "habilitado": self.habilitado,
            "motivo_inactivo": self.motivo_inactivo,
            "solicitudes": self.solicitudes,
            "desde_cache": self.desde_cache,
            "errores": self.errores,
            "uso_hoy": self._uso_hoy() if self.api_key else 0,
            "modelos": self.modelos[:10],
            "modelos_total": len(self.modelos),
        }


def _parsear_json(texto: str) -> dict:
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if not m:
            raise
        return json.loads(m.group(0))
