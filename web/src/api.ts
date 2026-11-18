// Cliente de la API: añade la sesión (JWT) y traduce errores a mensajes en español.

const CLAVE_SESION = "observatorio_sesion";

export type Usuario = { id: number; email: string; nombre?: string; rol: "admin" | "usuario"; estado: string };
export type Sesion = { token: string; usuario: Usuario };

export function leerSesion(): Sesion | null {
  try {
    const s = localStorage.getItem(CLAVE_SESION);
    return s ? (JSON.parse(s) as Sesion) : null;
  } catch {
    return null;
  }
}

export function guardarSesion(s: Sesion | null) {
  if (s) localStorage.setItem(CLAVE_SESION, JSON.stringify(s));
  else localStorage.removeItem(CLAVE_SESION);
}

export class ErrorApi extends Error {
  estado: number;
  constructor(mensaje: string, estado: number) {
    super(mensaje);
    this.estado = estado;
  }
}

import { cacheEnVuelo, guardarCache, leerCache, registrarEnVuelo } from "./cacheApi";

async function pedir<T>(metodo: string, ruta: string, cuerpo?: unknown): Promise<T> {
  const sesion = leerSesion();
  const r = await fetch(`/api${ruta}`, {
    method: metodo,
    headers: {
      "Content-Type": "application/json",
      ...(sesion ? { Authorization: `Bearer ${sesion.token}` } : {}),
    },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  if (r.status === 401 && sesion) {
    guardarSesion(null);
    window.location.href = "/login";
  }
  if (!r.ok) {
    let mensaje = `Error ${r.status}`;
    try {
      const d = await r.json();
      mensaje = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ErrorApi(mensaje, r.status);
  }
  const tipo = r.headers.get("content-type") || "";
  return (tipo.includes("application/json") ? r.json() : r.text()) as Promise<T>;
}

export const api = {
  get: <T>(ruta: string, opts?: { cache?: boolean }) => {
    const rutaNorm = ruta;
    if (opts?.cache) {
      const hit = leerCache<T>(rutaNorm);
      if (hit !== null) return Promise.resolve(hit);
      const inflight = cacheEnVuelo<T>(rutaNorm);
      if (inflight) return inflight;
      const prom = pedir<T>("GET", rutaNorm).then((d) => {
        guardarCache(rutaNorm, d);
        return d;
      });
      registrarEnVuelo(rutaNorm, prom);
      return prom;
    }
    return pedir<T>("GET", ruta);
  },
  post: <T>(ruta: string, cuerpo?: unknown) => pedir<T>("POST", ruta, cuerpo ?? {}),
  put: <T>(ruta: string, cuerpo?: unknown) => pedir<T>("PUT", ruta, cuerpo ?? {}),
  del: <T>(ruta: string) => pedir<T>("DELETE", ruta),
};

async function mensajeErrorDescarga(r: Response): Promise<string> {
  let detalle = "";
  const tipo = r.headers.get("content-type") || "";
  if (tipo.includes("application/json")) {
    try {
      const d = (await r.clone().json()) as { detail?: string };
      if (typeof d.detail === "string") detalle = d.detail;
    } catch {
      /* sin JSON */
    }
  }
  if (detalle) return detalle;
  if (r.status === 413) {
    return "El archivo es demasiado grande para descargarlo desde el servidor. Pruebe filtrar semestre/corte o use CSV.";
  }
  if (r.status === 504 || r.status === 408) {
    return "La descarga tardó demasiado (tiempo agotado). Filtre semestre y corte o use CSV.";
  }
  return `No se pudo descargar el archivo (error ${r.status}).`;
}

/** Descarga un archivo protegido (CSV/Excel) usando la sesión. */
export async function descargar(ruta: string, nombre: string) {
  const sesion = leerSesion();
  let r: Response;
  try {
    r = await fetch(`/api${ruta}`, { headers: sesion ? { Authorization: `Bearer ${sesion.token}` } : {} });
  } catch {
    throw new Error("No se pudo conectar con el servidor para descargar el archivo.");
  }
  if (!r.ok) throw new ErrorApi(await mensajeErrorDescarga(r), r.status);
  const blob = await r.blob();
  if (blob.size === 0) {
    throw new Error("El servidor devolvió un archivo vacío.");
  }
  if (nombre.endsWith(".xlsx")) {
    const cab = new Uint8Array(await blob.slice(0, 2).arrayBuffer());
    if (cab[0] !== 0x50 || cab[1] !== 0x4b) {
      throw new Error(
        "La respuesta no es un Excel válido (posible error del servidor). Si pide descripciones completas, use CSV.",
      );
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}
