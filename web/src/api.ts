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
  get: <T>(ruta: string) => pedir<T>("GET", ruta),
  post: <T>(ruta: string, cuerpo?: unknown) => pedir<T>("POST", ruta, cuerpo ?? {}),
  put: <T>(ruta: string, cuerpo?: unknown) => pedir<T>("PUT", ruta, cuerpo ?? {}),
  del: <T>(ruta: string) => pedir<T>("DELETE", ruta),
};

/** Descarga un archivo protegido (CSV/Excel) usando la sesión. */
export async function descargar(ruta: string, nombre: string) {
  const sesion = leerSesion();
  const r = await fetch(`/api${ruta}`, { headers: sesion ? { Authorization: `Bearer ${sesion.token}` } : {} });
  if (!r.ok) throw new ErrorApi(`No se pudo descargar (error ${r.status})`, r.status);
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  a.click();
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
