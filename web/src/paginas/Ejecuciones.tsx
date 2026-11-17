import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Aviso, Cargando, EstadoChip, Titulo, useDatos } from "../componentes/ui";

export type Progreso = {
  estado: string; fase: string; porcentaje: number; ofertas_crudas: number; procesadas: number;
  consultas: { total: number; hechas: number; error: number; pendientes: number };
  por_fuente: Record<string, { total: number; hechas: number; error: number; pendientes: number; ofertas: number }>;
  github_run_url?: string; aviso?: string; github?: { estado: string; conclusion: string | null; url: string };
};

export type Ejecucion = {
  id_ejecucion: string; fecha: string; semestre: string; corte: string; ejecutado_por: string; fuentes: string;
  ofertas_encontradas: number; duplicados_eliminados: number; errores: string | null; estado: string; modo: string;
  ejecutor: string; ofertas_guardadas: number; no_relevantes: number; total_corte: number; meta_ofertas: number;
  mini_corrida: boolean; conteo_por_fuente: Record<string, { encontradas: number; guardadas: number; consultas: number; consultas_con_error: number }> | null;
  conteo_por_carrera: Record<string, number> | null; errores_detalle: string[] | null; terminos_usados: string[] | null;
  uso_llm: Record<string, unknown> | null; duracion_segundos: number; fase: string; github_run_url: string | null;
  presupuesto_fuentes?: Record<string, number> | null;
  presupuesto_carreras?: Record<string, number> | null;
  logro_extraccion?: { objetivo?: number; por_fuente?: Record<string, number>; por_carrera?: Record<string, number> } | null;
  progreso?: Progreso;
  acciones?: AccionesCorrida;
};

export type AccionesCorrida = {
  consultas_pendientes: number;
  en_marcha: boolean;
  bloqueado_por_otra: boolean;
  id_corrida_activa?: string | null;
  puede_reanudar: boolean;
  puede_reintentar_consolidacion: boolean;
  puede_terminar: boolean;
};

export function AccionesCorridaPanel({
  id,
  acciones,
  onActualizado,
}: {
  id: string;
  acciones?: AccionesCorrida;
  onActualizado: () => void;
}) {
  const [cargando, setCargando] = useState<"reanudar" | "consolidar" | "terminar" | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  if (!acciones) return null;
  if (acciones.en_marcha) {
    return (
      <p className="text-sm text-texto-suave">Esta corrida está en marcha; las acciones de reintento aparecerán al terminar.</p>
    );
  }
  if (acciones.bloqueado_por_otra) {
    return (
      <Aviso tipo="alerta">
        Hay otra corrida en marcha ({acciones.id_corrida_activa}). Espere a que termine antes de reanudar esta.
      </Aviso>
    );
  }
  if (!acciones.puede_reanudar && !acciones.puede_reintentar_consolidacion && !acciones.puede_terminar) return null;

  const reanudar = async () => {
    const n = acciones.consultas_pendientes;
    const msg = n
      ? `¿Reanudar la corrida ${id}? Quedan ${n} consultas pendientes; se usará el mismo id y no se repetirán las ya hechas.`
      : `¿Reanudar la corrida ${id} con el mismo id?`;
    if (!confirm(msg)) return;
    setCargando("reanudar");
    setAviso(null);
    try {
      await api.post(`/corridas/${id}/reanudar`, {});
      setAviso({ tipo: "ok", texto: "La corrida se envió a GitHub Actions. El progreso se actualizará en unos segundos." });
      onActualizado();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as Error).message });
    } finally {
      setCargando(null);
    }
  };

  const terminar = async () => {
    const n = acciones.consultas_pendientes;
    const msg =
      n > 0
        ? `¿Terminar la corrida ${id} omitiendo ${n} consulta(s) pendiente(s)? ` +
          "No podrá deshacer esta acción ni recuperar esas consultas; se consolidará lo ya extraído si corresponde."
        : `¿Terminar la corrida ${id} sin volver a extraer? Consolidará los datos ya recolectados si aún no se había hecho.`;
    if (!confirm(msg)) return;
    setCargando("terminar");
    setAviso(null);
    try {
      await api.post(`/corridas/${id}/terminar`, {});
      setAviso({
        tipo: "ok",
        texto:
          n > 0
            ? `Se omitieron ${n} consultas pendientes. La corrida quedó cerrada o en consolidación final.`
            : "La corrida se envió a consolidación final o quedó marcada como finalizada.",
      });
      onActualizado();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as Error).message });
    } finally {
      setCargando(null);
    }
  };

  const consolidar = async () => {
    if (
      !confirm(
        `¿Reintentar solo la consolidación de ${id}? No volverá a extraer ofertas; procesará las crudas ya guardadas.`
      )
    ) {
      return;
    }
    setCargando("consolidar");
    setAviso(null);
    try {
      await api.post(`/corridas/${id}/reintentar-consolidacion`, {});
      setAviso({ tipo: "ok", texto: "La consolidación se envió a GitHub Actions." });
      onActualizado();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as Error).message });
    } finally {
      setCargando(null);
    }
  };

  return (
    <div className="tarjeta space-y-3">
      <h2 className="font-semibold">Continuar o reintentar</h2>
      {acciones.consultas_pendientes > 0 && (
        <p className="text-sm text-texto-suave">
          Consultas pendientes: <strong>{acciones.consultas_pendientes}</strong>
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {acciones.puede_reanudar && (
          <button type="button" className="btn" disabled={!!cargando} onClick={reanudar}>
            {cargando === "reanudar" ? "Enviando…" : "Reanudar corrida"}
          </button>
        )}
        {acciones.puede_reintentar_consolidacion && (
          <button type="button" className="btn-sec" disabled={!!cargando} onClick={consolidar}>
            {cargando === "consolidar" ? "Enviando…" : "Reintentar consolidación"}
          </button>
        )}
        {acciones.puede_terminar && (
          <button type="button" className="btn-peligro" disabled={!!cargando} onClick={terminar}>
            {cargando === "terminar" ? "Procesando…" : "Terminar corrida"}
          </button>
        )}
      </div>
      {aviso && <Aviso tipo={aviso.tipo === "ok" ? "ok" : "error"}>{aviso.texto}</Aviso>}
    </div>
  );
}

export function duracion(seg: number) {
  const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min ${seg % 60} s`;
}

export function PanelProgreso({ p }: { p: Progreso }) {
  return (
    <div className="tarjeta">
      <div className="mb-2 flex items-center justify-between">
        <div className="font-semibold">Progreso · fase: {p.fase || "—"}</div>
        <EstadoChip estado={p.estado} />
      </div>
      <div className="h-3 w-full rounded bg-niebla/30"><div className="h-3 rounded bg-institucional" style={{ width: `${p.porcentaje}%` }} /></div>
      <div className="mt-1 text-xs text-texto-suave">
        {p.porcentaje} % · consultas {p.consultas.hechas + p.consultas.error}/{p.consultas.total} ({p.consultas.error} con error) ·
        ofertas extraídas {p.ofertas_crudas} · procesadas {p.procesadas}
      </div>
      {p.aviso && <div className="mt-2"><Aviso tipo="alerta">{p.aviso}</Aviso></div>}
      <table className="tabla mt-3">
        <thead><tr><th>Fuente</th><th>Consultas hechas</th><th>Con error</th><th>Pendientes</th><th>Ofertas</th></tr></thead>
        <tbody>
          {Object.entries(p.por_fuente).map(([f, d]) => (
            <tr key={f}><td>{f}</td><td>{d.hechas}/{d.total}</td><td>{d.error}</td><td>{d.pendientes}</td><td>{d.ofertas}</td></tr>
          ))}
        </tbody>
      </table>
      {(p.github_run_url || p.github?.url) && (
        <a className="mt-2 inline-block text-sm text-institucional font-semibold underline" href={p.github_run_url || p.github?.url} target="_blank" rel="noreferrer">
          Ver en GitHub Actions
        </a>
      )}
    </div>
  );
}

export function Reporte({ e }: { e: Ejecucion }) {
  return (
    <div className="tarjeta">
      <h2 className="mb-2 font-semibold">Reporte de ejecución</h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-3">
        <div><dt className="text-texto-suave">Semestre · corte</dt><dd>{e.semestre} · {e.corte}</dd></div>
        <div><dt className="text-texto-suave">Lanzada por</dt><dd>{e.ejecutado_por} ({e.ejecutor === "github" ? "GitHub Actions" : "CLI local"})</dd></div>
        <div><dt className="text-texto-suave">Fuentes</dt><dd>{e.fuentes}</dd></div>
        <div><dt className="text-texto-suave">Ofertas encontradas</dt><dd>{e.ofertas_encontradas}</dd></div>
        <div><dt className="text-texto-suave">Guardadas (nuevas y relevantes)</dt><dd>{e.ofertas_guardadas}</dd></div>
        <div><dt className="text-texto-suave">Duplicados eliminados</dt><dd>{e.duplicados_eliminados}</dd></div>
        <div><dt className="text-texto-suave">No relevantes descartadas</dt><dd>{e.no_relevantes}</dd></div>
        <div><dt className="text-texto-suave">Total del corte / meta</dt><dd>{e.total_corte} / {e.meta_ofertas}</dd></div>
        <div><dt className="text-texto-suave">Mini corrida</dt><dd>{e.mini_corrida ? "sí" : "no"}</dd></div>
        <div><dt className="text-texto-suave">Duración</dt><dd>{duracion(e.duracion_segundos || 0)}</dd></div>
        <div><dt className="text-texto-suave">Modo</dt><dd>{e.modo}</dd></div>
      </dl>
      {e.presupuesto_fuentes && e.logro_extraccion && (
        <div className="mt-3 text-sm">
          <h3 className="font-semibold">Extracción (crudas): objetivo vs logrado</h3>
          {e.logro_extraccion.objetivo != null && <p className="text-texto-suave">Objetivo global: {e.logro_extraccion.objetivo}</p>}
          <ul className="mt-1 list-disc pl-5">
            {Object.entries(e.presupuesto_fuentes).map(([f, meta]) => {
              const etiqueta = { linkedin: "LinkedIn", indeed: "Indeed", computrabajo: "Computrabajo" }[f] || f;
              const hecho = e.logro_extraccion?.por_fuente?.[etiqueta] ?? e.logro_extraccion?.por_fuente?.[f] ?? 0;
              return (
                <li key={f}>
                  {etiqueta}: meta {meta}, logrado {hecho}
                </li>
              );
            })}
          </ul>
          {e.presupuesto_carreras && (
            <ul className="mt-1 list-disc pl-5">
              {Object.entries(e.presupuesto_carreras).map(([c, meta]) => (
                <li key={c}>
                  {c}: meta {meta}, logrado {e.logro_extraccion?.por_carrera?.[c] ?? 0}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {e.conteo_por_fuente && (
        <table className="tabla mt-3">
          <thead><tr><th>Fuente</th><th>Encontradas</th><th>Guardadas</th><th>Consultas</th><th>Con error</th></tr></thead>
          <tbody>{Object.entries(e.conteo_por_fuente).map(([f, d]) => (
            <tr key={f}><td>{f}</td><td>{d.encontradas}</td><td>{d.guardadas}</td><td>{d.consultas}</td><td>{d.consultas_con_error}</td></tr>
          ))}</tbody>
        </table>
      )}
      {e.conteo_por_carrera && (
        <div className="mt-3 text-sm">Por carrera: {Object.entries(e.conteo_por_carrera).map(([c, n]) => <span key={c} className="chip">{c}: {n}</span>)}</div>
      )}
      {e.errores_detalle && e.errores_detalle.length > 0 && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold">Avisos y errores</h3>
          <ul className="list-disc pl-5 text-sm text-amber-800">{e.errores_detalle.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
      )}
      {e.uso_llm && <p className="mt-2 text-xs text-texto-suave">Clasificación: {JSON.stringify(e.uso_llm)}</p>}
    </div>
  );
}

function Detalle({ id }: { id: string }) {
  const { datos, error, recargar } = useDatos<Ejecucion>(`/corridas/${id}`);
  useEffect(() => {
    if (!datos || !["en_cola", "en_curso"].includes(datos.estado)) return;
    const t = setInterval(recargar, 15000);
    return () => clearInterval(t);
  }, [datos, recargar]);
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;
  return (
    <div className="space-y-4">
      <Titulo extra={<Link className="btn-sec" to="/ejecuciones">Volver</Link>}>Ejecución {datos.id_ejecucion}</Titulo>
      <AccionesCorridaPanel id={datos.id_ejecucion} acciones={datos.acciones} onActualizado={recargar} />
      {datos.progreso && <PanelProgreso p={datos.progreso} />}
      <Reporte e={datos} />
    </div>
  );
}

export default function Ejecuciones() {
  const { id } = useParams();
  const { datos, error } = useDatos<Ejecucion[]>(id ? null : "/corridas");
  if (id) return <Detalle id={id} />;
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;
  return (
    <div>
      <Titulo>Ejecuciones y reportes</Titulo>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Ejecución</th><th>Fecha</th><th>Corte</th><th>Estado</th><th>Pend.</th><th>Encontradas</th><th>Guardadas</th><th>Duplicados</th><th>Total corte</th><th>Duración</th></tr></thead>
          <tbody>
            {datos.map((e) => (
              <tr key={e.id_ejecucion}>
                <td>
                  <Link className="text-institucional font-semibold underline" to={`/ejecuciones/${e.id_ejecucion}`}>{e.id_ejecucion}</Link>
                  {e.acciones?.puede_reanudar && !e.acciones.en_marcha && (
                    <span className="ml-1 text-xs text-institucional">· reanudar</span>
                  )}
                  {e.acciones?.puede_reintentar_consolidacion && !e.acciones.en_marcha && (
                    <span className="ml-1 text-xs text-texto-suave">· consolidar</span>
                  )}
                  {e.acciones?.puede_terminar && !e.acciones.en_marcha && (
                    <span className="ml-1 text-xs text-marina/70">· terminar</span>
                  )}
                </td>
                <td>{e.fecha}</td><td>{e.semestre} · {e.corte}</td><td><EstadoChip estado={e.estado} /></td>
                <td>{e.acciones?.consultas_pendientes ?? "—"}</td>
                <td>{e.ofertas_encontradas}</td><td>{e.ofertas_guardadas}</td><td>{e.duplicados_eliminados}</td><td>{e.total_corte}</td>
                <td>{duracion(e.duracion_segundos || 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {datos.length === 0 && <p className="p-2 text-sm text-texto-suave">Todavía no hay ejecuciones.</p>}
      </div>
    </div>
  );
}
