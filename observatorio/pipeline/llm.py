"""Clasificación de ofertas dudosas con OpenRouter (endpoint gratuito único).

- Modelo fijo: ``openrouter/free`` (https://openrouter.ai/openrouter/free).
- Solo ofertas que las reglas no resuelven; lotes JSON; caché por hash en ``llm_cache``.
- Tier gratuito OpenRouter (referencia): ~20 solicitudes/minuto; cupo diario según
  créditos de la cuenta (p. ej. 50 o 1000/día). Por defecto ~12 solicitudes/minuto
  y tope diario conservador en configuración.
- Ante HTTP 429: reintentos con ``Retry-After`` o backoff exponencial (hasta 4 intentos).
- Si persisten 429, 401, 402 o 403: circuit breaker (sin más llamadas en la corrida;
  respaldo por reglas) y ``motivo_inactivo`` explícito en el reporte.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date

import requests
from sqlalchemy.orm import Session

from observatorio.config import MODELO_OPENROUTER_GRATIS, ajustes
from observatorio.texto import hash_texto

log = logging.getLogger("observatorio.llm")

URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_REINTENTOS = 4

PROMPT_SISTEMA = """Eres un clasificador de ofertas laborales de Colombia para el Observatorio de la Facultad de Ciencias Económicas.
Para cada oferta decide si es relevante para profesionales o estudiantes de estas carreras: {carreras}.
Una oferta es relevante si el cargo lo puede ocupar alguien formado en alguna de esas carreras (contabilidad, auditoría, impuestos,
finanzas, economía, análisis económico o de datos de negocio, riesgo, administración, gestión, procesos, proyectos, comercial, talento humano, etc.).
No es relevante si es de salud, ingeniería de software, oficios operativos, docencia de otras áreas, etc.
Responde SOLO con JSON con esta forma exacta:
{{"resultados": [{{"id": "<id>", "relevante": true, "carreras": ["<carrera principal>", "..."], "herramientas_no_catalogadas": ["..."],
"habilidades_tecnicas": ["..."], "tiene_habilidad_cursable": true}}]}}
"carreras" debe usar exactamente los nombres dados, la principal primero, máximo 5; vacía si no es relevante.
"herramientas_no_catalogadas": programas o herramientas de software mencionados (máximo 5), puede ir vacía.
"habilidades_tecnicas": habilidades técnicas o de dominio que justificarían un curso (p. ej. SAP, NIIF, SQL, Excel avanzado, análisis de datos); máximo 5.
"tiene_habilidad_cursable": true si hay al menos una herramienta del catálogo, una herramienta_no_catalogada seria, o una habilidad_tecnica relevante.
No cuentan habilidades blandas (trabajo en equipo, comunicación) ni «manejo básico de Office/Excel» sin nivel avanzado."""


def _detalle_error_http(r: requests.Response) -> str:
    try:
        cuerpo = r.json()
        err = cuerpo.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        if err:
            return str(err)[:300]
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    return (r.text or "")[:300]


def _espera_429(r: requests.Response, intento: int) -> float:
    raw = r.headers.get("Retry-After")
    if raw is not None:
        try:
            return min(float(raw), 180.0)
        except ValueError:
            pass
    return min(180.0, 4.0 * (2**intento))


class ClienteLLM:
    def __init__(self, s: Session, cfg_llm: dict, carreras: list[str], id_corrida: str | None = None):
        del id_corrida  # reservado; el modelo ya no depende de la corrida
        a = ajustes()
        self.s = s
        self.api_key = a.openrouter_api_key
        self.modelo = MODELO_OPENROUTER_GRATIS
        self.tamano_lote = int(cfg_llm.get("tamano_lote", 20))
        self.max_dia = int(cfg_llm.get("max_solicitudes_dia", 50))
        self.max_corrida = int(cfg_llm.get("max_solicitudes_corrida", 600))
        self.intervalo = 60.0 / max(1, int(cfg_llm.get("solicitudes_por_minuto", 12)))
        self.habilitado = bool(cfg_llm.get("habilitado", True)) and bool(self.api_key)
        self.carreras = carreras
        self.solicitudes = 0
        self.errores = 0
        self.desde_cache = 0
        self._ultima = 0.0
        self.motivo_inactivo = "" if self.habilitado else (
            "sin OPENROUTER_API_KEY" if not self.api_key else "desactivado en configuración"
        )

    def _abrir_circuito(self, codigo: int, detalle: str) -> None:
        self.habilitado = False
        detalle_limpio = " ".join((detalle or "sin detalle").split())
        self.motivo_inactivo = f"error de API key / cuota OpenRouter (HTTP {codigo}): {detalle_limpio}"
        log.warning("OpenRouter desactivado en esta corrida: %s", self.motivo_inactivo)

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
        if not self.habilitado:
            return None, ""
        for intento in range(MAX_REINTENTOS):
            espera = self.intervalo - (time.time() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            self._ultima = time.time()
            try:
                r = requests.post(
                    URL,
                    timeout=90,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/its-camilo/observatorio-empleo-fce",
                        "X-Title": "Observatorio de Empleo FCE",
                    },
                    json={
                        "model": self.modelo,
                        "messages": mensajes,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                    },
                )
            except requests.RequestException as e:
                log.warning("OpenRouter no respondió: %s", e)
                if intento >= MAX_REINTENTOS - 1:
                    self._abrir_circuito(0, str(e))
                    return None, ""
                time.sleep(min(120.0, 4.0 * (2**intento)))
                continue

            if r.status_code == 200:
                try:
                    contenido = r.json()["choices"][0]["message"]["content"]
                    self.solicitudes += 1
                    self._sumar_uso()
                    return _parsear_json(contenido), self.modelo
                except Exception as e:  # respuesta mal formada
                    log.info("Respuesta no válida de OpenRouter: %s", e)
                    self.errores += 1
                    return None, ""

            if r.status_code == 429:
                detalle = _detalle_error_http(r)
                if intento >= MAX_REINTENTOS - 1:
                    self._abrir_circuito(429, detalle)
                    return None, ""
                espera_429 = _espera_429(r, intento)
                log.info("OpenRouter 429 (intento %d/%d); espera %.0fs — %s", intento + 1, MAX_REINTENTOS, espera_429, detalle[:120])
                time.sleep(espera_429)
                continue

            if r.status_code in (401, 402, 403):
                self._abrir_circuito(r.status_code, _detalle_error_http(r))
                return None, ""

            if r.status_code >= 500:
                if intento >= MAX_REINTENTOS - 1:
                    self._abrir_circuito(r.status_code, _detalle_error_http(r))
                    return None, ""
                time.sleep(min(120.0, 10.0 * (intento + 1)))
                continue

            log.info("OpenRouter respondió %s: %s", r.status_code, _detalle_error_http(r)[:200])
            self.errores += 1
            return None, ""

        return None, ""

    def clasificar(self, ofertas: list[dict]) -> dict[str, dict]:
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
            lote = pendientes[i : i + self.tamano_lote]
            cuerpo = [
                {
                    "id": o["id"],
                    "cargo": o.get("cargo", ""),
                    "empresa": o.get("empresa", ""),
                    "termino": o.get("termino_busqueda", ""),
                    "descripcion": (o.get("descripcion") or "")[:1200],
                }
                for _, o in lote
            ]
            datos, modelo = self._llamar(
                [
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": json.dumps({"ofertas": cuerpo}, ensure_ascii=False)},
                ]
            )
            if not datos:
                if not self.habilitado:
                    break
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
                    "habilidades_tecnicas": [str(t)[:80] for t in (x.get("habilidades_tecnicas") or [])][:5],
                    "tiene_habilidad_cursable": bool(x.get("tiene_habilidad_cursable")),
                }
                if res["relevante"] and not res["carreras"]:
                    continue
                salida[o["id"]] = res
                self._guardar_cache(h, res, modelo)
            self.s.flush()
        return salida

    def resumen(self) -> dict:
        return {
            "habilitado": self.habilitado,
            "motivo_inactivo": self.motivo_inactivo,
            "modelo": self.modelo,
            "solicitudes": self.solicitudes,
            "desde_cache": self.desde_cache,
            "errores": self.errores,
            "uso_hoy": self._uso_hoy() if self.api_key else 0,
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
