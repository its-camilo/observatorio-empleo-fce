import { api } from "./api";
import { precargarGet } from "./cacheApi";

const RUTA_API: Record<string, string> = {
  "/": "/dashboard",
  "/ofertas": "/ofertas/filtros",
  "/rankings": "/analisis/cortes",
  "/cursos": "/cursos",
  "/temas-recomendados": "/temas-recomendados",
  "/configuracion": "/config",
  "/validacion": "/validacion/muestras",
};

export function prefetchNav(rutaMenu: string) {
  const apiRuta = RUTA_API[rutaMenu];
  if (!apiRuta) return;
  void precargarGet(apiRuta, () => api.get(apiRuta));
}