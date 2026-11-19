import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import EditorDistribucion from "../componentes/EditorDistribucion";
import EditorNivelesExperiencia from "../componentes/EditorNivelesExperiencia";
import { Aviso } from "../componentes/ui";
import EditorChips from "./EditorChips";

export type ParamConfig = {
  clave: string;
  valor: unknown;
  descripcion: string;
  defecto: unknown;
};

const FUENTES_ETIQUETA: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  computrabajo: "Computrabajo",
  google: "Google (legacy)",
};

const ORDEN_PARAMS = [
  "distribucion_fuentes",
  "distribucion_carreras",
  "carreras",
  "fuentes",
  "ubicaciones",
  "solo_capitales_departamento",
  "ventana_dias",
  "tipo_oferta",
  "niveles_experiencia",
  "objetivo_ofertas_corrida",
  "factor_extraccion_crudas",
  "mini_corrida",
  "ronda_extra_cupos",
  "ajuste_proporcion_final",
  "dedup",
  "requiere_software_o_habilidad",
  "cursos",
  "no_catalogados",
  "reglas_carrera",
  "exclusion_titulo",
  "exclusion_operativa_titulo",
] as const;

const TITULOS: Record<string, string> = {
  carreras: "Carreras",
  fuentes: "Fuentes de ofertas",
  ubicaciones: "Ubicaciones de búsqueda",
  solo_capitales_departamento: "Solo capitales departamentales",
  ventana_dias: "Ventana de días",
  tipo_oferta: "Tipo de oferta",
  objetivo_ofertas_corrida: "Objetivo de ofertas por corrida",
  factor_extraccion_crudas: "Factor de extracción (crudas)",
  mini_corrida: "Mini corrida",
  ronda_extra_cupos: "Ronda extra de cupos",
  ajuste_proporcion_final: "Ajuste de proporción final",
  dedup: "Duplicados",
  requiere_software_o_habilidad: "Valor formativo",
  cursos: "Cursos en tendencia",
  no_catalogados: "No catalogados",
  reglas_carrera: "Reglas por carrera",
  exclusion_titulo: "Exclusiones en el título",
  exclusion_operativa_titulo: "Exclusiones operativas en el título",
};

function TarjetaForm({
  titulo,
  descripcion,
  admin,
  guardarDisabled,
  onGuardar,
  onRestablecer,
  msg,
  children,
  abierto,
}: {
  titulo: string;
  descripcion: string;
  admin: boolean;
  guardarDisabled: boolean;
  onGuardar: () => void;
  onRestablecer: () => void;
  msg: { tipo: "ok" | "error"; t: string } | null;
  children: React.ReactNode;
  abierto?: boolean;
}) {
  return (
    <details className="tarjeta" open={abierto}>
      <summary className="cursor-pointer">
        <b>{titulo}</b> <span className="text-sm text-texto-suave">— {descripcion}</span>
      </summary>
      <div className="mt-3 space-y-3">{children}</div>
      {msg && <Aviso tipo={msg.tipo}>{msg.t}</Aviso>}
      {admin && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="btn" disabled={guardarDisabled} onClick={onGuardar}>
            Guardar
          </button>
          <button type="button" className="btn-sec" onClick={onRestablecer}>
            Restablecer valores por defecto
          </button>
        </div>
      )}
    </details>
  );
}

function useGuardarConfig(clave: string, alGuardar: () => void) {
  const [msg, setMsg] = useState<{ tipo: "ok" | "error"; t: string } | null>(null);
  const guardar = useCallback(
    async (valor: unknown) => {
      setMsg(null);
      try {
        await api.put(`/config/${clave}`, { valor });
        setMsg({ tipo: "ok", t: "Guardado. Aplica desde la próxima ejecución." });
        alGuardar();
      } catch (e) {
        setMsg({ tipo: "error", t: (e as Error).message });
      }
    },
    [clave, alGuardar],
  );
  return { msg, guardar, setMsg };
}

function EditorCarreras({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  const [items, setItems] = useState<string[]>((p.valor as string[]) || []);
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setItems((p.valor as string[]) || []), [p.valor]);
  const invalido = items.length === 0;
  return (
    <TarjetaForm
      titulo={TITULOS.carreras}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(items)}
      onRestablecer={() => setItems((p.defecto as string[]) || [])}
    >
      <EditorChips etiqueta="Carreras configuradas" items={items} onChange={setItems} disabled={!admin} />
      {invalido && <p className="text-sm text-red-700">Debe haber al menos una carrera.</p>}
    </TarjetaForm>
  );
}

type FuenteCfg = {
  activa?: boolean;
  max_por_particion?: number;
  retraso_segundos?: [number, number];
  fragmentos?: number;
  max_paginas?: number;
};

function EditorFuentes({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  const [mapa, setMapa] = useState<Record<string, FuenteCfg>>({});
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setMapa((p.valor as Record<string, FuenteCfg>) || {}), [p.valor]);

  const claves = useMemo(() => Object.keys(mapa).sort(), [mapa]);
  const invalido = claves.some((k) => {
    const f = mapa[k];
    const r = f.retraso_segundos;
    return !f.max_por_particion || f.max_por_particion < 1 || !r || r[1] < r[0];
  });

  const actualizar = (k: string, patch: Partial<FuenteCfg>) => {
    setMapa({ ...mapa, [k]: { ...mapa[k], ...patch } });
  };

  return (
    <TarjetaForm
      titulo={TITULOS.fuentes}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(mapa)}
      onRestablecer={() => setMapa((p.defecto as Record<string, FuenteCfg>) || {})}
    >
      {claves.map((k) => {
        const f = mapa[k];
        return (
          <fieldset key={k} className="rounded-bloque border border-niebla p-3" disabled={!admin}>
            <legend className="px-1 text-sm font-bold text-marina">{FUENTES_ETIQUETA[k] || k}</legend>
            <label className="mb-2 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={Boolean(f.activa)} onChange={(e) => actualizar(k, { activa: e.target.checked })} />
              Fuente activa
            </label>
            <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-4">
              <label className="block">
                <span className="etiqueta">Máx. por partición</span>
                <input
                  type="number"
                  min={1}
                  max={500}
                  className="campo"
                  value={f.max_por_particion ?? ""}
                  onChange={(e) => actualizar(k, { max_por_particion: Number(e.target.value) })}
                />
              </label>
              <label className="block">
                <span className="etiqueta">Fragmentos</span>
                <input
                  type="number"
                  min={1}
                  max={12}
                  className="campo"
                  value={f.fragmentos ?? ""}
                  onChange={(e) => actualizar(k, { fragmentos: Number(e.target.value) })}
                />
              </label>
              <label className="block">
                <span className="etiqueta">Retraso mín. (s)</span>
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  className="campo"
                  value={f.retraso_segundos?.[0] ?? ""}
                  onChange={(e) =>
                    actualizar(k, { retraso_segundos: [Number(e.target.value), f.retraso_segundos?.[1] ?? 0] })
                  }
                />
              </label>
              <label className="block">
                <span className="etiqueta">Retraso máx. (s)</span>
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  className="campo"
                  value={f.retraso_segundos?.[1] ?? ""}
                  onChange={(e) =>
                    actualizar(k, { retraso_segundos: [f.retraso_segundos?.[0] ?? 0, Number(e.target.value)] })
                  }
                />
              </label>
              {f.max_paginas !== undefined && (
                <label className="block">
                  <span className="etiqueta">Máx. páginas</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    className="campo"
                    value={f.max_paginas}
                    onChange={(e) => actualizar(k, { max_paginas: Number(e.target.value) })}
                  />
                </label>
              )}
            </div>
          </fieldset>
        );
      })}
    </TarjetaForm>
  );
}

type Ubicacion = { nombre: string; linkedin?: string; indeed?: string; computrabajo?: string };

function EditorUbicaciones({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  const [filas, setFilas] = useState<Ubicacion[]>([]);
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setFilas((p.valor as Ubicacion[]) || []), [p.valor]);

  return (
    <TarjetaForm
      titulo={TITULOS.ubicaciones}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={filas.length === 0}
      msg={msg}
      onGuardar={() => guardar(filas)}
      onRestablecer={() => setFilas((p.defecto as Ubicacion[]) || [])}
    >
      <p className="text-sm text-texto-suave">{filas.length} ubicaciones. Vacío en Computrabajo = no consultar en esa ciudad.</p>
      <div className="tabla-contenedor max-h-96 overflow-y-auto">
        <table className="tabla text-xs">
          <thead>
            <tr>
              <th>Ciudad</th>
              <th>LinkedIn</th>
              <th>Indeed</th>
              <th>Computrabajo</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((u, i) => (
              <tr key={u.nombre}>
                <td className="font-medium">{u.nombre}</td>
                <td>
                  <input
                    className="campo"
                    disabled={!admin}
                    value={u.linkedin || ""}
                    onChange={(e) => {
                      const next = [...filas];
                      next[i] = { ...u, linkedin: e.target.value };
                      setFilas(next);
                    }}
                  />
                </td>
                <td>
                  <input
                    className="campo"
                    disabled={!admin}
                    value={u.indeed || ""}
                    onChange={(e) => {
                      const next = [...filas];
                      next[i] = { ...u, indeed: e.target.value };
                      setFilas(next);
                    }}
                  />
                </td>
                <td>
                  <input
                    className="campo"
                    disabled={!admin}
                    value={u.computrabajo || ""}
                    onChange={(e) => {
                      const next = [...filas];
                      next[i] = { ...u, computrabajo: e.target.value };
                      setFilas(next);
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TarjetaForm>
  );
}

function EditorBooleano({
  p,
  admin,
  alGuardar,
  titulo,
}: {
  p: ParamConfig;
  admin: boolean;
  alGuardar: () => void;
  titulo: string;
}) {
  const [valor, setValor] = useState(Boolean(p.valor));
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setValor(Boolean(p.valor)), [p.valor]);
  return (
    <TarjetaForm
      titulo={titulo}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={false}
      msg={msg}
      onGuardar={() => guardar(valor)}
      onRestablecer={() => setValor(Boolean(p.defecto))}
    >
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input type="checkbox" checked={valor} disabled={!admin} onChange={(e) => setValor(e.target.checked)} />
        {valor ? "Activo" : "Inactivo"}
      </label>
    </TarjetaForm>
  );
}

function EditorNumero({
  p,
  admin,
  alGuardar,
  titulo,
  min,
  max,
  step,
}: {
  p: ParamConfig;
  admin: boolean;
  alGuardar: () => void;
  titulo: string;
  min: number;
  max: number;
  step?: number;
}) {
  const [valor, setValor] = useState(String(p.valor ?? ""));
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setValor(String(p.valor ?? "")), [p.valor]);
  const n = Number(valor);
  const invalido = Number.isNaN(n) || n < min || n > max;
  return (
    <TarjetaForm
      titulo={titulo}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(step ? n : Math.round(n))}
      onRestablecer={() => setValor(String(p.defecto ?? ""))}
    >
      <input
        type="number"
        className="campo max-w-xs"
        min={min}
        max={max}
        step={step ?? 1}
        disabled={!admin}
        value={valor}
        onChange={(e) => setValor(e.target.value)}
      />
      {invalido && (
        <p className="text-sm text-red-700">
          Valor entre {min} y {max}.
        </p>
      )}
    </TarjetaForm>
  );
}

function EditorTipoOferta({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  const [valor, setValor] = useState(String(p.valor || "ambas"));
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setValor(String(p.valor || "ambas")), [p.valor]);
  return (
    <TarjetaForm
      titulo={TITULOS.tipo_oferta}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={!["practica", "empleo", "ambas"].includes(valor)}
      msg={msg}
      onGuardar={() => guardar(valor)}
      onRestablecer={() => setValor(String(p.defecto || "ambas"))}
    >
      <select className="campo max-w-xs" disabled={!admin} value={valor} onChange={(e) => setValor(e.target.value)}>
        <option value="ambas">Práctica y empleo</option>
        <option value="practica">Solo práctica</option>
        <option value="empleo">Solo empleo</option>
      </select>
    </TarjetaForm>
  );
}

function EditorMiniCorrida({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type V = { habilitada: boolean; max_minutos: number; fuentes: string[] };
  const defectoMini: V = { habilitada: true, max_minutos: 240, fuentes: [] };
  const [v, setV] = useState<V>({ ...defectoMini, ...((p.valor as V) || {}) });
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setV({ ...defectoMini, ...((p.valor as V) || {}) }), [p.valor]);
  const opciones = ["linkedin", "indeed", "computrabajo"];
  const invalido = v.habilitada && (v.fuentes.length === 0 || v.max_minutos < 5);
  const toggleFuente = (f: string) => {
    setV({ ...v, fuentes: v.fuentes.includes(f) ? v.fuentes.filter((x) => x !== f) : [...v.fuentes, f] });
  };
  return (
    <TarjetaForm
      titulo={TITULOS.mini_corrida}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(v)}
      onRestablecer={() => setV((p.defecto as V) || v)}
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={v.habilitada} disabled={!admin} onChange={(e) => setV({ ...v, habilitada: e.target.checked })} />
        Habilitar mini corrida
      </label>
      <label className="mt-2 block max-w-xs">
        <span className="etiqueta">Máximo de minutos</span>
        <input
          type="number"
          min={5}
          max={720}
          className="campo"
          disabled={!admin}
          value={v.max_minutos}
          onChange={(e) => setV({ ...v, max_minutos: Number(e.target.value) })}
        />
      </label>
      <div className="mt-2">
        <span className="etiqueta">Fuentes</span>
        {opciones.map((f) => (
          <label key={f} className="mr-4 inline-flex items-center gap-1 text-sm">
            <input type="checkbox" checked={v.fuentes.includes(f)} disabled={!admin} onChange={() => toggleFuente(f)} />
            {FUENTES_ETIQUETA[f] || f}
          </label>
        ))}
      </div>
    </TarjetaForm>
  );
}

function EditorAjusteProporcion({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type V = { habilitado: boolean; tolerancia_proporcion_pp: number };
  const [v, setV] = useState<V>((p.valor as V) || { habilitado: true, tolerancia_proporcion_pp: 5 });
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setV((p.valor as V) || { habilitado: true, tolerancia_proporcion_pp: 5 }), [p.valor]);
  const invalido = v.tolerancia_proporcion_pp < 0 || v.tolerancia_proporcion_pp > 50;
  return (
    <TarjetaForm
      titulo={TITULOS.ajuste_proporcion_final}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(v)}
      onRestablecer={() => setV(p.defecto as V)}
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={v.habilitado} disabled={!admin} onChange={(e) => setV({ ...v, habilitado: e.target.checked })} />
        Ajuste habilitado
      </label>
      <label className="mt-2 block max-w-xs">
        <span className="etiqueta">Tolerancia (pp)</span>
        <input
          type="number"
          min={0}
          max={50}
          className="campo"
          disabled={!admin}
          value={v.tolerancia_proporcion_pp}
          onChange={(e) => setV({ ...v, tolerancia_proporcion_pp: Number(e.target.value) })}
        />
      </label>
    </TarjetaForm>
  );
}

function EditorRondaExtra({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type V = { habilitada: boolean; max_rondas: number; consultas_por_celda: number; max_minutos_fuente: number };
  const [v, setV] = useState<V>((p.valor as V) || { habilitada: true, max_rondas: 2, consultas_por_celda: 8, max_minutos_fuente: 60 });
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setV((p.valor as V) || v), [p.valor]);
  const invalido = v.max_rondas < 0 || v.consultas_por_celda < 1 || v.max_minutos_fuente < 1;
  return (
    <TarjetaForm
      titulo={TITULOS.ronda_extra_cupos}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(v)}
      onRestablecer={() => setV(p.defecto as V)}
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={v.habilitada} disabled={!admin} onChange={(e) => setV({ ...v, habilitada: e.target.checked })} />
        Habilitada
      </label>
      <div className="grid gap-2 sm:grid-cols-3">
        <label>
          <span className="etiqueta">Máx. rondas</span>
          <input type="number" min={0} max={10} className="campo" disabled={!admin} value={v.max_rondas} onChange={(e) => setV({ ...v, max_rondas: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Consultas por celda</span>
          <input type="number" min={1} max={50} className="campo" disabled={!admin} value={v.consultas_por_celda} onChange={(e) => setV({ ...v, consultas_por_celda: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Máx. minutos por fuente</span>
          <input type="number" min={1} max={240} className="campo" disabled={!admin} value={v.max_minutos_fuente} onChange={(e) => setV({ ...v, max_minutos_fuente: Number(e.target.value) })} />
        </label>
      </div>
    </TarjetaForm>
  );
}

function EditorDedup({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type V = { alcance: "global" | "corte"; dias: number };
  const [v, setV] = useState<V>((p.valor as V) || { alcance: "global", dias: 7 });
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setV((p.valor as V) || { alcance: "global", dias: 7 }), [p.valor]);
  const invalido = v.dias < 1 || v.dias > 60;
  return (
    <TarjetaForm
      titulo={TITULOS.dedup}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(v)}
      onRestablecer={() => setV(p.defecto as V)}
    >
      <label className="block max-w-xs">
        <span className="etiqueta">Alcance</span>
        <select className="campo" disabled={!admin} value={v.alcance} onChange={(e) => setV({ ...v, alcance: e.target.value as V["alcance"] })}>
          <option value="global">Historial completo</option>
          <option value="corte">Solo el corte</option>
        </select>
      </label>
      <label className="mt-2 block max-w-xs">
        <span className="etiqueta">Días máximos entre fechas</span>
        <input type="number" min={1} max={60} className="campo" disabled={!admin} value={v.dias} onChange={(e) => setV({ ...v, dias: Number(e.target.value) })} />
      </label>
    </TarjetaForm>
  );
}

function EditorCursos({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type V = {
    activo: boolean;
    plataformas: string[];
    max_por_termino: number;
    max_terminos_demanda: number;
    min_ofertas_habilidad: number;
    min_terminos: number;
    peso_demanda_puntaje: number;
    terminos_respaldo: string[];
  };
  const [v, setV] = useState<V>(p.valor as V);
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setV(p.valor as V), [p.valor]);
  const plataformas = ["coursera", "edx", "platzi"];
  const invalido = v.terminos_respaldo.length === 0 || v.peso_demanda_puntaje < 0 || v.peso_demanda_puntaje > 1;
  return (
    <TarjetaForm
      titulo={TITULOS.cursos}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(v)}
      onRestablecer={() => setV(p.defecto as V)}
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={v.activo} disabled={!admin} onChange={(e) => setV({ ...v, activo: e.target.checked })} />
        Extracción de cursos activa
      </label>
      <span className="etiqueta mt-2 block">Plataformas</span>
      {plataformas.map((pl) => (
        <label key={pl} className="mr-3 inline-flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={v.plataformas.includes(pl)}
            disabled={!admin}
            onChange={() =>
              setV({
                ...v,
                plataformas: v.plataformas.includes(pl) ? v.plataformas.filter((x) => x !== pl) : [...v.plataformas, pl],
              })
            }
          />
          {pl}
        </label>
      ))}
      <div className="mt-2 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
        <label>
          <span className="etiqueta">Máx. por término</span>
          <input type="number" min={1} max={100} className="campo" disabled={!admin} value={v.max_por_termino} onChange={(e) => setV({ ...v, max_por_termino: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Máx. términos demanda</span>
          <input type="number" min={1} max={200} className="campo" disabled={!admin} value={v.max_terminos_demanda} onChange={(e) => setV({ ...v, max_terminos_demanda: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Peso demanda (0–1)</span>
          <input type="number" min={0} max={1} step={0.05} className="campo" disabled={!admin} value={v.peso_demanda_puntaje} onChange={(e) => setV({ ...v, peso_demanda_puntaje: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Mín. ofertas/habilidad</span>
          <input type="number" min={1} max={100} className="campo" disabled={!admin} value={v.min_ofertas_habilidad} onChange={(e) => setV({ ...v, min_ofertas_habilidad: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Mín. términos</span>
          <input type="number" min={1} max={100} className="campo" disabled={!admin} value={v.min_terminos} onChange={(e) => setV({ ...v, min_terminos: Number(e.target.value) })} />
        </label>
      </div>
      <EditorChips
        etiqueta="Términos de respaldo"
        items={v.terminos_respaldo}
        onChange={(items) => setV({ ...v, terminos_respaldo: items })}
        disabled={!admin}
      />
    </TarjetaForm>
  );
}

function EditorNoCatalogados({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type V = { min_frecuencia: number; max_terminos: number };
  const [v, setV] = useState<V>(p.valor as V);
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setV(p.valor as V), [p.valor]);
  const invalido = v.min_frecuencia < 1 || v.max_terminos < 10;
  return (
    <TarjetaForm
      titulo={TITULOS.no_catalogados}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={invalido}
      msg={msg}
      onGuardar={() => guardar(v)}
      onRestablecer={() => setV(p.defecto as V)}
    >
      <div className="grid gap-2 sm:grid-cols-2">
        <label>
          <span className="etiqueta">Frecuencia mínima</span>
          <input type="number" min={1} max={1000} className="campo" disabled={!admin} value={v.min_frecuencia} onChange={(e) => setV({ ...v, min_frecuencia: Number(e.target.value) })} />
        </label>
        <label>
          <span className="etiqueta">Máx. términos</span>
          <input type="number" min={10} max={5000} className="campo" disabled={!admin} value={v.max_terminos} onChange={(e) => setV({ ...v, max_terminos: Number(e.target.value) })} />
        </label>
      </div>
    </TarjetaForm>
  );
}

function EditorReglasCarrera({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  type Regla = { titulo: string[]; descripcion: string[] };
  const [mapa, setMapa] = useState<Record<string, Regla>>({});
  const [carrera, setCarrera] = useState("");
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => {
    const m = (p.valor as Record<string, Regla>) || {};
    setMapa(m);
    const keys = Object.keys(m);
    if (!carrera && keys.length) setCarrera(keys[0]);
  }, [p.valor, carrera]);
  const claves = Object.keys(mapa);
  const regla = mapa[carrera] || { titulo: [], descripcion: [] };
  return (
    <TarjetaForm
      titulo={TITULOS.reglas_carrera}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={claves.length === 0}
      msg={msg}
      onGuardar={() => guardar(mapa)}
      onRestablecer={() => setMapa((p.defecto as Record<string, Regla>) || {})}
    >
      <label className="block max-w-md">
        <span className="etiqueta">Carrera</span>
        <select className="campo" value={carrera} onChange={(e) => setCarrera(e.target.value)}>
          {claves.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <EditorChips
        etiqueta="Palabras en el título"
        items={regla.titulo}
        onChange={(items) => setMapa({ ...mapa, [carrera]: { ...regla, titulo: items } })}
        disabled={!admin}
      />
      <EditorChips
        etiqueta="Palabras en la descripción"
        items={regla.descripcion}
        onChange={(items) => setMapa({ ...mapa, [carrera]: { ...regla, descripcion: items } })}
        disabled={!admin}
      />
    </TarjetaForm>
  );
}

function EditorListaExclusion({ p, admin, alGuardar }: { p: ParamConfig; admin: boolean; alGuardar: () => void }) {
  const [items, setItems] = useState<string[]>((p.valor as string[]) || []);
  const { msg, guardar } = useGuardarConfig(p.clave, alGuardar);
  useEffect(() => setItems((p.valor as string[]) || []), [p.valor]);
  return (
    <TarjetaForm
      titulo={TITULOS[p.clave] || p.clave}
      descripcion={p.descripcion}
      admin={admin}
      guardarDisabled={false}
      msg={msg}
      onGuardar={() => guardar(items)}
      onRestablecer={() => setItems((p.defecto as string[]) || [])}
    >
      <EditorChips etiqueta="Términos" items={items} onChange={setItems} disabled={!admin} />
    </TarjetaForm>
  );
}

function EditorJsonAvanzado({
  clave,
  valor,
  descripcion,
  admin,
  alGuardar,
}: {
  clave: string;
  valor: unknown;
  descripcion: string;
  admin: boolean;
  alGuardar: () => void;
}) {
  const [texto, setTexto] = useState(JSON.stringify(valor, null, 2));
  const [parseOk, setParseOk] = useState(true);
  const { msg, guardar } = useGuardarConfig(clave, alGuardar);
  useEffect(() => setTexto(JSON.stringify(valor, null, 2)), [valor]);
  const validar = (t: string) => {
    try {
      JSON.parse(t);
      setParseOk(true);
    } catch {
      setParseOk(false);
    }
  };
  return (
    <TarjetaForm
      titulo={`Avanzado: ${clave}`}
      descripcion={descripcion || "Clave heredada; edite solo si sabe el formato."}
      admin={admin}
      guardarDisabled={!parseOk}
      msg={msg}
      onGuardar={() => guardar(JSON.parse(texto))}
      onRestablecer={() => {
        setTexto(JSON.stringify(valor, null, 2));
        validar(JSON.stringify(valor, null, 2));
      }}
    >
      <textarea
        className="campo h-48 w-full font-mono text-xs"
        disabled={!admin}
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          validar(e.target.value);
        }}
      />
      {!parseOk && <p className="text-sm text-red-700">JSON inválido; corrija antes de guardar.</p>}
    </TarjetaForm>
  );
}

export function EditorParametro({
  p,
  admin,
  alGuardar,
  carreras,
  distFuentes,
  distCarreras,
}: {
  p: ParamConfig;
  admin: boolean;
  alGuardar: () => void;
  carreras: string[];
  distFuentes: Record<string, number>;
  distCarreras: Record<string, number>;
}) {
  if (p.clave === "distribucion_fuentes") {
    return (
      <EditorDistribucion
        clave="distribucion_fuentes"
        titulo="Reparto entre fuentes"
        descripcion={p.descripcion}
        claves={["linkedin", "indeed", "computrabajo"]}
        valores={distFuentes}
        defecto={(p.defecto as Record<string, number>) || undefined}
        admin={admin}
        alGuardar={alGuardar}
      />
    );
  }
  if (p.clave === "distribucion_carreras") {
    return (
      <EditorDistribucion
        clave="distribucion_carreras"
        titulo="Reparto entre carreras"
        descripcion={p.descripcion}
        claves={carreras}
        valores={distCarreras}
        defecto={(p.defecto as Record<string, number>) || undefined}
        admin={admin}
        alGuardar={alGuardar}
      />
    );
  }
  if (p.clave === "niveles_experiencia") {
    return (
      <EditorNivelesExperiencia
        descripcion={p.descripcion}
        valorInicial={p.valor}
        defecto={p.defecto}
        admin={admin}
        alGuardar={alGuardar}
      />
    );
  }
  switch (p.clave) {
    case "carreras":
      return <EditorCarreras p={p} admin={admin} alGuardar={alGuardar} />;
    case "fuentes":
      return <EditorFuentes p={p} admin={admin} alGuardar={alGuardar} />;
    case "ubicaciones":
      return <EditorUbicaciones p={p} admin={admin} alGuardar={alGuardar} />;
    case "solo_capitales_departamento":
      return <EditorBooleano p={p} admin={admin} alGuardar={alGuardar} titulo={TITULOS.solo_capitales_departamento} />;
    case "ventana_dias":
      return <EditorNumero p={p} admin={admin} alGuardar={alGuardar} titulo={TITULOS.ventana_dias} min={1} max={365} />;
    case "tipo_oferta":
      return <EditorTipoOferta p={p} admin={admin} alGuardar={alGuardar} />;
    case "objetivo_ofertas_corrida":
      return <EditorNumero p={p} admin={admin} alGuardar={alGuardar} titulo={TITULOS.objetivo_ofertas_corrida} min={100} max={500000} />;
    case "factor_extraccion_crudas":
      return <EditorNumero p={p} admin={admin} alGuardar={alGuardar} titulo={TITULOS.factor_extraccion_crudas} min={1} max={5} step={0.05} />;
    case "mini_corrida":
      return <EditorMiniCorrida p={p} admin={admin} alGuardar={alGuardar} />;
    case "ronda_extra_cupos":
      return <EditorRondaExtra p={p} admin={admin} alGuardar={alGuardar} />;
    case "ajuste_proporcion_final":
      return <EditorAjusteProporcion p={p} admin={admin} alGuardar={alGuardar} />;
    case "dedup":
      return <EditorDedup p={p} admin={admin} alGuardar={alGuardar} />;
    case "requiere_software_o_habilidad":
      return <EditorBooleano p={p} admin={admin} alGuardar={alGuardar} titulo={TITULOS.requiere_software_o_habilidad} />;
    case "cursos":
      return <EditorCursos p={p} admin={admin} alGuardar={alGuardar} />;
    case "no_catalogados":
      return <EditorNoCatalogados p={p} admin={admin} alGuardar={alGuardar} />;
    case "reglas_carrera":
      return <EditorReglasCarrera p={p} admin={admin} alGuardar={alGuardar} />;
    case "exclusion_titulo":
    case "exclusion_operativa_titulo":
      return <EditorListaExclusion p={p} admin={admin} alGuardar={alGuardar} />;
    default:
      return null;
  }
}

export function ordenarParams(lista: ParamConfig[]): ParamConfig[] {
  const idx = (c: string) => {
    const i = ORDEN_PARAMS.indexOf(c as (typeof ORDEN_PARAMS)[number]);
    return i >= 0 ? i : 999;
  };
  return [...lista].sort((a, b) => idx(a.clave) - idx(b.clave));
}

export { EditorJsonAvanzado, ORDEN_PARAMS };