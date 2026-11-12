import { ReactNode, useCallback, useEffect, useState } from "react";
import { api } from "../api";

export function Titulo({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-niebla pb-3">
      <h1 className="titulo-seccion">{children}</h1>
      {extra}
    </div>
  );
}

export function Aviso({ tipo = "info", children }: { tipo?: "info" | "error" | "ok" | "alerta"; children: ReactNode }) {
  const colores = {
    info: "border-institucional bg-niebla/25 text-marina",
    error: "border-marina/30 bg-crema text-marina",
    ok: "border-acento/60 bg-acento/15 text-marina",
    alerta: "border-destacado bg-destacado/20 text-marina",
  }[tipo];
  return <div className={`mb-4 rounded-bloque border px-4 py-3 text-sm text-texto-suave ${colores}`}>{children}</div>;
}

export function Cargando() {
  return <p className="text-sm text-texto-suave">Cargando…</p>;
}

export function Kpi({ etiqueta, valor, nota }: { etiqueta: string; valor: ReactNode; nota?: string }) {
  return (
    <div className="tarjeta">
      <div className="font-titulo text-xs font-bold uppercase tracking-wide text-texto-suave">{etiqueta}</div>
      <div className="mt-1 font-titulo text-2xl font-extrabold text-marina">{valor}</div>
      {nota && <div className="mt-1 text-xs text-texto-suave">{nota}</div>}
    </div>
  );
}

/** Barras horizontales simples (sin librerías de gráficos). */
export function Barras({ datos, sufijo = "" }: { datos: { etiqueta: string; valor: number }[]; sufijo?: string }) {
  const max = Math.max(1, ...datos.map((d) => d.valor));
  return (
    <div className="space-y-2">
      {datos.map((d) => (
        <div key={d.etiqueta} className="flex items-center gap-2 text-sm">
          <div className="w-44 shrink-0 truncate text-marina" title={d.etiqueta}>
            {d.etiqueta}
          </div>
          <div className="h-3 flex-1 rounded-full bg-niebla/40">
            <div className="h-3 rounded-full bg-institucional" style={{ width: `${(100 * d.valor) / max}%` }} />
          </div>
          <div className="w-16 text-right tabular-nums text-texto-suave">
            {d.valor.toLocaleString("es-CO")}
            {sufijo}
          </div>
        </div>
      ))}
    </div>
  );
}

export function EstadoChip({ estado }: { estado: string }) {
  const c: Record<string, string> = {
    completada: "bg-acento/30 text-marina border-acento/50",
    incompleta: "bg-destacado/30 text-marina border-destacado/60",
    fallida: "bg-crema text-marina border-marina/30",
    en_curso: "bg-institucional/20 text-marina border-institucional",
    en_cola: "bg-niebla/40 text-texto-suave border-niebla",
  };
  const t: Record<string, string> = { en_curso: "en curso", en_cola: "en cola" };
  return (
    <span className={`rounded-boton border px-2.5 py-0.5 text-xs font-bold uppercase ${c[estado] || "bg-niebla/40"}`}>
      {t[estado] || estado}
    </span>
  );
}

/** Hook mínimo para cargar datos de la API con estado de carga y error. */
export function useDatos<T>(ruta: string | null, deps: unknown[] = []) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const recargar = useCallback(async () => {
    if (!ruta) return;
    setCargando(true);
    setError(null);
    try {
      setDatos(await api.get<T>(ruta));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCargando(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ruta, ...deps]);
  useEffect(() => {
    recargar();
  }, [recargar]);
  return { datos, error, cargando, recargar, setDatos };
}

export const CORTES = ["Inicio", "Mitad", "Final"];

export function semestreActual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() < 6 ? "I" : "II"}`;
}

export function SelectorCorte({ cortes, valor, onCambio }: {
  cortes: { semestre: string; corte: string; ofertas: number }[];
  valor: string;
  onCambio: (v: string) => void;
}) {
  return (
    <select className="campo" value={valor} onChange={(e) => onCambio(e.target.value)}>
      {cortes.length === 0 && <option value="">Sin datos</option>}
      {cortes.map((c) => (
        <option key={`${c.semestre}|${c.corte}`} value={`${c.semestre}|${c.corte}`}>
          {c.semestre} · {c.corte} ({c.ofertas.toLocaleString("es-CO")} ofertas)
        </option>
      ))}
    </select>
  );
}
