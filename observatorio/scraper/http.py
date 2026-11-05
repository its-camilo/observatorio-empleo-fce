"""Cliente HTTP educado: pausas, reintentos con espera creciente y proxies rotativos."""
from __future__ import annotations

import itertools
import logging
import random
import time

import requests

from observatorio.config import ajustes

log = logging.getLogger("observatorio.http")

AGENTES = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
]


class FuenteBloqueada(Exception):
    """La fuente respondió repetidamente con bloqueo (429/999/403)."""


class ClienteHttp:
    def __init__(self, fuente: str, retraso: tuple[float, float] = (2.0, 4.0), proxies: list[str] | None = None,
                 reintentos: int = 4, espera_base: float = 20.0, idioma: str = "es-CO,es;q=0.9,en;q=0.7"):
        self.fuente = fuente
        self.retraso = retraso
        self.reintentos = reintentos
        self.espera_base = espera_base
        self.proxies = proxies if proxies is not None else ajustes().proxies
        self._ciclo = itertools.cycle(self.proxies) if self.proxies else None
        self.sesion = requests.Session()
        self.sesion.headers.update({"Accept-Language": idioma,
                                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
        self.limitado = False
        self.bloqueos_seguidos = 0
        self.peticiones = 0

    def _proxy(self) -> dict | None:
        if not self._ciclo:
            return None
        p = next(self._ciclo)
        return {"http": p, "https": p}

    def pausa(self) -> None:
        lo, hi = self.retraso
        extra = 8.0 if self.limitado else 0.0
        time.sleep(random.uniform(lo, hi) + extra)

    def get(self, url: str, *, pausar: bool = True, **kwargs) -> requests.Response | None:
        return self.pedir("GET", url, pausar=pausar, **kwargs)

    def post(self, url: str, *, pausar: bool = True, **kwargs) -> requests.Response | None:
        return self.pedir("POST", url, pausar=pausar, **kwargs)

    def pedir(self, metodo: str, url: str, *, pausar: bool = True, **kwargs) -> requests.Response | None:
        """Devuelve la respuesta 200, None si es 404/410, o lanza FuenteBloqueada."""
        if pausar:
            self.pausa()
        kwargs.setdefault("timeout", 30)
        for intento in range(self.reintentos + 1):
            headers = {"User-Agent": random.choice(AGENTES), **kwargs.pop("headers", {})}
            try:
                r = self.sesion.request(metodo, url, headers=headers, proxies=self._proxy(), **kwargs)
                self.peticiones += 1
            except requests.RequestException as e:
                espera = min(self.espera_base * (2 ** intento), 300) * random.uniform(0.6, 1.2)
                log.info("[%s] Error de conexión (%s); reintento en %.0fs", self.fuente, type(e).__name__, espera)
                time.sleep(espera if intento < self.reintentos else 0)
                continue
            if r.status_code == 200:
                self.bloqueos_seguidos = 0
                return r
            if r.status_code in (404, 410):
                return None
            if r.status_code in (429, 999, 403, 503) or r.status_code >= 500:
                self.limitado = True
                ra = r.headers.get("Retry-After")
                espera = float(ra) if ra and ra.isdigit() else min(self.espera_base * (2 ** intento), 300)
                espera *= random.uniform(0.8, 1.3)
                if intento < self.reintentos:
                    log.info("[%s] La fuente pidió bajar el ritmo (HTTP %s); espera %.0fs y reintenta",
                             self.fuente, r.status_code, espera)
                    time.sleep(espera)
                continue
            log.info("[%s] Respuesta inesperada HTTP %s en %s", self.fuente, r.status_code, url[:120])
            return None
        self.bloqueos_seguidos += 1
        if self.bloqueos_seguidos >= 3:
            raise FuenteBloqueada(f"{self.fuente} bloqueó varias consultas seguidas")
        return None


def explicar_error(fuente: str, e: Exception) -> str:
    """Mensaje en lenguaje sencillo para el reporte de ejecución (RF-16)."""
    nombre = {"linkedin": "LinkedIn", "indeed": "Indeed", "google": "Google Jobs", "computrabajo": "Computrabajo",
              "coursera": "Coursera", "edx": "edX", "platzi": "Platzi"}.get(fuente, fuente)
    texto = str(e)
    if isinstance(e, FuenteBloqueada) or "429" in texto or "999" in texto or "blocked" in texto.lower():
        return (f"{nombre} está limitando o bloqueando las consultas. Se guardó lo que ya se había extraído. "
                f"Reintente más tarde (la corrida se puede reanudar), baje el ritmo o configure proxies.")
    if isinstance(e, (requests.ConnectionError, requests.Timeout)) or "timed out" in texto.lower():
        return f"No hubo conexión estable con {nombre}. Se guardó lo extraído; reintente más tarde."
    if isinstance(e, (KeyError, AttributeError, IndexError, ValueError)):
        return (f"La página de {nombre} parece haber cambiado y no se pudo leer ({type(e).__name__}). "
                f"Las demás fuentes siguieron. Avise a Desarrollo (ver documentación técnica, 'Si una página cambia').")
    return f"Error en {nombre}: {texto[:300]}"
