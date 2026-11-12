import { useEffect, useState } from "react";
import { api } from "../api";
import { useEsAdmin } from "../main";
import { Aviso, Cargando, Kpi, SelectorCorte, Titulo, useDatos } from "../componentes/ui";

type Stats = { total: number; validados: number; correctos: number; precision: number | null; meta: number; cumple_meta: boolean };
type Muestra = { muestra_id: string; semestre: string; corte: string } & Stats;
type Item = {
  id: number; resultado: string | null; softwares_detectados: string; softwares_faltantes: string | null; softwares_sobrantes: string | null; comentario: string | null;
  oferta: { id_oferta: string; cargo: string; empresa: string; url: string; descripcion: string; detecciones: { software: string; texto_encontrado: string }[] } | null;
};

function Revision({ id, alCambiar, admin }: { id: string; alCambiar: () => void; admin: boolean }) {
  const { datos, recargar } = useDatos<{ estadisticas: Stats; items: Item[] }>(`/validacion/muestras/${id}`, [id]);
  const [i, setI] = useState(0);
  const [form, setForm] = useState({ softwares_faltantes: "", softwares_sobrantes: "", comentario: "" });
  const item = datos?.items[i];
  useEffect(() => {
    if (item) setForm({ softwares_faltantes: item.softwares_faltantes || "", softwares_sobrantes: item.softwares_sobrantes || "", comentario: item.comentario || "" });
  }, [item]);
  if (!datos) return <Cargando />;
  const e = datos.estadisticas;
  const marcar = async (resultado: string) => {
    if (!item) return;
    await api.put(`/validacion/items/${item.id}`, { resultado, ...form });
    await recargar();
    alCambiar();
    if (i < datos.items.length - 1) setI(i + 1);
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi etiqueta="Validadas" valor={`${e.validados}/${e.total}`} />
        <Kpi etiqueta="Correctas" valor={e.correctos} />
        <Kpi etiqueta="Precisión" valor={e.precision == null ? "—" : `${e.precision} %`} nota={`meta ${e.meta} %`} />
        <Kpi etiqueta="Resultado" valor={e.validados < e.total ? "en curso" : e.cumple_meta ? "cumple" : "no cumple"} />
      </div>
      {item?.oferta && (
        <div className="tarjeta">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div><b>{i + 1}/{datos.items.length}.</b> {item.oferta.cargo} · {item.oferta.empresa}{" "}
              <a className="text-sm text-institucional font-semibold underline" href={item.oferta.url} target="_blank" rel="noreferrer">original</a>
              {item.resultado && <span className="chip ml-2">marcada: {item.resultado}</span>}</div>
            <div className="flex gap-1">
              <button className="btn-sec" disabled={i === 0} onClick={() => setI(i - 1)}>Anterior</button>
              <button className="btn-sec" disabled={i >= datos.items.length - 1} onClick={() => setI(i + 1)}>Siguiente</button>
            </div>
          </div>
          <div className="text-sm"><b>Softwares detectados:</b> {item.oferta.detecciones.length ? item.oferta.detecciones.map((d) => <span key={d.software} className="chip">{d.software} ← “{d.texto_encontrado}”</span>) : "ninguno"}</div>
          <pre className="mt-2 max-h-80 overflow-y-auto whitespace-pre-wrap rounded bg-niebla/20 p-2 font-sans text-sm">{item.oferta.descripcion}</pre>
          {admin ? (
            <>
              <div className="mt-2 grid gap-2 md:grid-cols-3">
                <input className="campo" placeholder="Softwares que faltaron" value={form.softwares_faltantes} onChange={(e) => setForm({ ...form, softwares_faltantes: e.target.value })} />
                <input className="campo" placeholder="Softwares detectados por error" value={form.softwares_sobrantes} onChange={(e) => setForm({ ...form, softwares_sobrantes: e.target.value })} />
                <input className="campo" placeholder="Comentario" value={form.comentario} onChange={(e) => setForm({ ...form, comentario: e.target.value })} />
              </div>
              <div className="mt-2 flex gap-2">
                <button className="btn" onClick={() => marcar("correcto")}>Correcto</button>
                <button type="button" className="btn-sec" onClick={() => marcar("incorrecto")}>Incorrecto</button>
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm text-texto-suave">Solo los administradores pueden registrar revisiones. Puede consultar esta muestra en modo lectura.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function Validacion() {
  const admin = useEsAdmin();
  const { datos: cortes } = useDatos<{ semestre: string; corte: string; ofertas: number }[]>("/analisis/cortes");
  const { datos: muestras, recargar } = useDatos<Muestra[]>("/validacion/muestras");
  const [sel, setSel] = useState("");
  const [tamano, setTamano] = useState(30);
  const [activa, setActiva] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (cortes?.length && !sel) setSel(`${cortes[cortes.length - 1].semestre}|${cortes[cortes.length - 1].corte}`); }, [cortes, sel]);
  const crear = async () => {
    setErr(null);
    try {
      const [semestre, corte] = sel.split("|");
      const r = await api.post<{ muestra_id: string }>("/validacion/muestras", { semestre, corte, tamano });
      await recargar();
      setActiva(r.muestra_id);
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="space-y-4">
      <Titulo>Validación manual (meta 90 %)</Titulo>
      <Aviso>Se toma una muestra aleatoria de ofertas de un corte. Para cada una, revise si los softwares detectados coinciden con lo que pide la oferta y márquela como correcta o incorrecta.</Aviso>
      {err && <Aviso tipo="error">{err}</Aviso>}
      <div className="tarjeta flex flex-wrap items-end gap-2">
        <div><label className="etiqueta">Corte</label><SelectorCorte cortes={cortes || []} valor={sel} onCambio={setSel} /></div>
        <div><label className="etiqueta">Tamaño</label><input type="number" className="campo w-20" value={tamano} onChange={(e) => setTamano(Number(e.target.value))} /></div>
        {admin && <button className="btn" disabled={!sel} onClick={crear}>Nueva muestra</button>}
      </div>
      {muestras && muestras.length > 0 && (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Muestra</th><th>Corte</th><th>Validadas</th><th>Precisión</th><th /></tr></thead>
            <tbody>{muestras.map((m) => (
              <tr key={m.muestra_id}><td className="text-xs">{m.muestra_id}</td><td>{m.semestre} · {m.corte}</td><td>{m.validados}/{m.total}</td>
                <td className={m.precision == null ? "" : m.precision >= m.meta ? "text-institucional font-semibold" : "text-marina font-semibold"}>{m.precision == null ? "—" : `${m.precision} %`}</td>
                <td><button className="btn-sec" onClick={() => setActiva(m.muestra_id)}>Revisar</button></td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {activa && <Revision id={activa} alCambiar={recargar} admin={admin} />}
    </div>
  );
}
