import { ReactNode, useCallback, useEffect, useState } from "react";
import { api } from "../api";

export function Titulo({ children, extra }: { children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-xl font-semibold text-tinta">{children}</h1>
      {extra}
    </div>
  );
}

export function Aviso({ tipo = "info", children }: { tipo?: "info" | "error" | "ok" | "alerta"; children: ReactNode }) {
  const colores = {
    info: "bg-sky-50 text-sky-800 border-sky-200",
    error: "bg-red-50 text-red-800 border-red-200",
    ok: "bg-green-50 text-green-800 border-green-200",
    alerta: "bg-amber-50 text-amber-800 border-amber-200",
  }[tipo];
  return <div className={`mb-3 rounded-lg border px-3 py-2 text-sm ${colores}`}>{children}</div>;
}

export function Cargando() {
  return <p className="text-sm text-slate-500">Cargando…</p>;
}

export function Kpi({ etiqueta, valor, nota }: { etiqueta: string; valor: ReactNode; nota?: string }) {
  return (
    <div className="tarjeta">
      <div className="text-xs uppercase tracking-wide text-slate-500">{etiqueta}</div>
      <div className="mt-1 text-2xl font-semibold text-tinta">{valor}</div>
      {nota && <div className="text-xs text-slate-500">{nota}</div>}
    </div>
  );
}

/** Barras horizontales simples (sin librerías de gráficos). */
export function Barras({ datos, sufijo = "" }: { datos: { etiqueta: string; valor: number }[]; sufijo?: string }) {
  const max = Math.max(1, ...datos.map((d) => d.valor));
  return (
    <div className="space-y-1">
      {datos.map((d) => (
        <div key={d.etiqueta} className="flex items-center gap-2 text-sm">
          <div className="w-44 shrink-0 truncate text-slate-700" title={d.etiqueta}>{d.etiqueta}</div>
          <div className="h-3 flex-1 rounded bg-slate-100">
            <div className="h-3 rounded bg-unal" style={{ width: `${(100 * d.valor) / max}%` }} />
          </div>
          <div className="w-16 text-right tabular-nums text-slate-600">{d.valor.toLocaleString("es-CO")}{sufijo}</div>
        </div>
      ))}
    </div>
  );
}

export function EstadoChip({ estado }: { estado: string }) {
  const c: Record<string, string> = {
    completada: "bg-green-100 text-green-800",
    incompleta: "bg-amber-100 text-amber-800",
    fallida: "bg-red-100 text-red-800",
    en_curso: "bg-sky-100 text-sky-800",
    en_cola: "bg-slate-100 text-slate-700",
  };
  const t: Record<string, string> = { en_curso: "en curso", en_cola: "en cola" };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${c[estado] || "bg-slate-100"}`}>{t[estado] || estado}</span>;
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
