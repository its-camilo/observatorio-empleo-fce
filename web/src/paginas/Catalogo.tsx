import { useState } from "react";
import { api } from "../api";
import { useEsAdmin } from "../main";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Sinonimo = { id: number; texto: string; sensible_mayusculas: boolean; requiere_contexto: boolean; patron_exclusion: string | null };
type Software = { id: number; software: string; grupo: string; activo: boolean; contexto: string | null; notas: string | null; sinonimos: Sinonimo[] };

function FilaSoftware({ sw, admin, recargar }: { sw: Software; admin: boolean; recargar: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [edit, setEdit] = useState(sw);
  const [nuevo, setNuevo] = useState({ texto: "", sensible_mayusculas: false, requiere_contexto: false, patron_exclusion: "" });
  const [error, setError] = useState<string | null>(null);
  const correr = async (f: () => Promise<unknown>) => {
    setError(null);
    try { await f(); recargar(); } catch (e) { setError((e as Error).message); }
  };
  return (
    <>
      <tr className={sw.activo ? "" : "opacity-50"}>
        <td className="font-medium">{sw.software}</td>
        <td className="text-xs">{sw.grupo}</td>
        <td>{sw.sinonimos.map((s) => <span key={s.id} className="chip" title={[s.sensible_mayusculas && "distingue mayúsculas", s.requiere_contexto && "exige contexto", s.patron_exclusion && `excluye: ${s.patron_exclusion}`].filter(Boolean).join(" · ")}>
          {s.texto}{s.sensible_mayusculas || s.requiere_contexto ? " *" : ""}</span>)}</td>
        <td>{sw.activo ? "sí" : "no"}</td>
        <td><button className="btn-sec" onClick={() => setAbierto(!abierto)}>{abierto ? "Cerrar" : admin ? "Editar" : "Ver"}</button></td>
      </tr>
      {abierto && (
        <tr><td colSpan={5} className="bg-slate-50">
          {error && <Aviso tipo="error">{error}</Aviso>}
          <div className="grid gap-2 md:grid-cols-4">
            <div><label className="etiqueta">Nombre estándar</label><input className="campo w-full" disabled={!admin} value={edit.software} onChange={(e) => setEdit({ ...edit, software: e.target.value })} /></div>
            <div><label className="etiqueta">Grupo</label><input className="campo w-full" disabled={!admin} value={edit.grupo} onChange={(e) => setEdit({ ...edit, grupo: e.target.value })} /></div>
            <div className="md:col-span-2"><label className="etiqueta">Palabras de contexto (para sinónimos ambiguos, separadas por coma)</label>
              <input className="campo w-full" disabled={!admin} value={edit.contexto || ""} onChange={(e) => setEdit({ ...edit, contexto: e.target.value })} /></div>
          </div>
          {admin && (
            <div className="mt-2 flex flex-wrap gap-2">
              <label className="text-sm"><input type="checkbox" checked={edit.activo} onChange={(e) => setEdit({ ...edit, activo: e.target.checked })} /> Activo</label>
              <button className="btn" onClick={() => correr(() => api.put(`/catalogo/${sw.id}`, edit))}>Guardar</button>
              <button className="btn-peligro" onClick={() => confirm(`¿Eliminar ${sw.software}?`) && correr(() => api.del(`/catalogo/${sw.id}`))}>Eliminar software</button>
            </div>
          )}
          <table className="tabla mt-3">
            <thead><tr><th>Sinónimo</th><th>Distingue mayúsculas</th><th>Exige contexto</th><th>Patrón de exclusión</th><th /></tr></thead>
            <tbody>
              {sw.sinonimos.map((s) => (
                <tr key={s.id}><td>{s.texto}</td><td>{s.sensible_mayusculas ? "sí" : ""}</td><td>{s.requiere_contexto ? "sí" : ""}</td>
                  <td className="font-mono text-xs">{s.patron_exclusion}</td>
                  <td>{admin && <button className="btn-peligro" onClick={() => correr(() => api.del(`/sinonimos/${s.id}`))}>Quitar</button>}</td></tr>
              ))}
              {admin && (
                <tr><td><input className="campo w-full" placeholder="nuevo sinónimo" value={nuevo.texto} onChange={(e) => setNuevo({ ...nuevo, texto: e.target.value })} /></td>
                  <td><input type="checkbox" checked={nuevo.sensible_mayusculas} onChange={(e) => setNuevo({ ...nuevo, sensible_mayusculas: e.target.checked })} /></td>
                  <td><input type="checkbox" checked={nuevo.requiere_contexto} onChange={(e) => setNuevo({ ...nuevo, requiere_contexto: e.target.checked })} /></td>
                  <td><input className="campo w-full font-mono" placeholder="(opcional) regex" value={nuevo.patron_exclusion} onChange={(e) => setNuevo({ ...nuevo, patron_exclusion: e.target.value })} /></td>
                  <td><button className="btn" disabled={!nuevo.texto.trim()} onClick={() => correr(async () => {
                    await api.post(`/catalogo/${sw.id}/sinonimos`, { ...nuevo, patron_exclusion: nuevo.patron_exclusion || null });
                    setNuevo({ texto: "", sensible_mayusculas: false, requiere_contexto: false, patron_exclusion: "" });
                  })}>Agregar</button></td></tr>
              )}
            </tbody>
          </table>
        </td></tr>
      )}
    </>
  );
}

export default function Catalogo() {
  const admin = useEsAdmin();
  const { datos, error, recargar } = useDatos<Software[]>("/catalogo");
  const [nuevo, setNuevo] = useState({ software: "", grupo: "", sinonimos: "" });
  const [texto, setTexto] = useState("");
  const [prueba, setPrueba] = useState<{ software: string; texto_encontrado: string }[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const grupos = Array.from(new Set((datos || []).map((d) => d.grupo)));

  const crear = async () => {
    setErr(null);
    try {
      const sin = nuevo.sinonimos.split(",").map((t) => t.trim()).filter(Boolean);
      await api.post("/catalogo", { software: nuevo.software, grupo: nuevo.grupo, sinonimos: (sin.length ? sin : [nuevo.software]).map((t) => ({ texto: t })) });
      setNuevo({ software: "", grupo: "", sinonimos: "" });
      recargar();
    } catch (e) { setErr((e as Error).message); }
  };

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;
  return (
    <div className="space-y-4">
      <Titulo>Catálogo de softwares y sinónimos</Titulo>
      <Aviso>Los cambios se aplican desde la próxima ejecución. Sinónimos con * tienen reglas especiales (mayúsculas o contexto) para evitar falsos positivos, por ejemplo “R” o “SAS”.</Aviso>
      {err && <Aviso tipo="error">{err}</Aviso>}
      {admin && (
        <div className="tarjeta flex flex-wrap items-end gap-2">
          <div><label className="etiqueta">Nuevo software</label><input className="campo" value={nuevo.software} onChange={(e) => setNuevo({ ...nuevo, software: e.target.value })} /></div>
          <div><label className="etiqueta">Grupo</label><input className="campo" list="grupos" value={nuevo.grupo} onChange={(e) => setNuevo({ ...nuevo, grupo: e.target.value })} />
            <datalist id="grupos">{grupos.map((g) => <option key={g} value={g} />)}</datalist></div>
          <div className="flex-1"><label className="etiqueta">Sinónimos (separados por coma)</label><input className="campo w-full" value={nuevo.sinonimos} onChange={(e) => setNuevo({ ...nuevo, sinonimos: e.target.value })} /></div>
          <button className="btn" disabled={!nuevo.software || !nuevo.grupo} onClick={crear}>Agregar</button>
        </div>
      )}
      <div className="tarjeta">
        <h2 className="mb-2 font-semibold">Probar detección</h2>
        <textarea className="campo h-20 w-full" placeholder="Pegue aquí el texto de una oferta…" value={texto} onChange={(e) => setTexto(e.target.value)} />
        <button className="btn mt-2" onClick={async () => setPrueba(await api.post("/catalogo/probar", { texto }))}>Probar</button>
        {prueba && <div className="mt-2 text-sm">{prueba.length ? prueba.map((p) => <span key={p.software} className="chip">{p.software} ← “{p.texto_encontrado}”</span>) : "No se detectó ningún software."}</div>}
      </div>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Software</th><th>Grupo</th><th>Sinónimos</th><th>Activo</th><th /></tr></thead>
          <tbody>{datos.map((sw) => <FilaSoftware key={sw.id} sw={sw} admin={admin} recargar={recargar} />)}</tbody>
        </table>
      </div>
    </div>
  );
}
