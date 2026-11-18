/** Caché GET en memoria (sesión): deduplica y reutiliza respuestas breves. */
const TTL_MS = 90_000;

type Entrada = { expira: number; datos: unknown };
const tabla = new Map<string, Entrada>();
const enVuelo = new Map<string, Promise<unknown>>();

export function leerCache<T>(ruta: string): T | null {
  const e = tabla.get(ruta);
  if (!e || e.expira <= Date.now()) {
    if (e) tabla.delete(ruta);
    return null;
  }
  return e.datos as T;
}

export function guardarCache(ruta: string, datos: unknown, ttlMs = TTL_MS) {
  tabla.set(ruta, { expira: Date.now() + ttlMs, datos });
}

export function cacheEnVuelo<T>(ruta: string): Promise<T> | null {
  const p = enVuelo.get(ruta);
  return (p as Promise<T>) ?? null;
}

export function registrarEnVuelo(ruta: string, prom: Promise<unknown>) {
  enVuelo.set(ruta, prom);
  prom.finally(() => {
    if (enVuelo.get(ruta) === prom) enVuelo.delete(ruta);
  });
}

/** Precarga silenciosa (p. ej. al pasar el ratón por el menú). */
export async function precargarGet(ruta: string, obtener: () => Promise<unknown>) {
  if (leerCache(ruta) || enVuelo.has(ruta)) return;
  const prom = obtener().then((d) => {
    guardarCache(ruta, d);
    return d;
  });
  registrarEnVuelo(ruta, prom);
  await prom.catch(() => undefined);
}