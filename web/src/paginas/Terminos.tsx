import { useState } from "react";
import { api } from "../api";
import { useEsAdmin } from "../main";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Termino = { id: number; termino: string; carrera: string; tipo: string; fuentes: string | null; activo: boolean };
const CARRERAS = ["Administración de Empresas", "Contaduría Pública", "Economía"];

export default function Terminos() {
  const admin = useEsAdmin();
  const { datos, error, recargar } = useDatos<Termino[]>("/terminos");
  const [nuevo, setNuevo] = useState({ termino: "", carrera: CARRERAS[0], tipo: "principal", fuentes: "" });
  const [filtro, setFiltro] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const correr = async (f: () => Promise<unknown>) => {
    setErr(null);
    try { await f(); recargar(); } catch (e) { setErr((e as Error).message); }
  };
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;
  const visibles = datos.filter((t) => !filtro || t.carrera === filtro);
  return (
    <div className="space-y-4">
      <Titulo>Términos de búsqueda</Titulo>
      <Aviso>“Principal” se usa en cada corrida. “Ampliado” solo en la mini corrida automática cuando no se llega a la meta de ofertas.
        Fuentes vacías = todas. Cambiar los términos afecta la comparación entre cortes (queda anotado en el reporte).</Aviso>
      {err && <Aviso tipo="error">{err}</Aviso>}
      {admin && (
        <div className="tarjeta flex flex-wrap items-end gap-2">
          <div className="flex-1"><label className="etiqueta">Término</label><input className="campo w-full" value={nuevo.termino} onChange={(e) => setNuevo({ ...nuevo, termino: e.target.value })} /></div>
          <div><label className="etiqueta">Carrera</label><select className="campo" value={nuevo.carrera} onChange={(e) => setNuevo({ ...nuevo, carrera: e.target.value })}>{CARRERAS.map((c) => <option key={c}>{c}</option>)}</select></div>
          <div><label className="etiqueta">Tipo</label><select className="campo" value={nuevo.tipo} onChange={(e) => setNuevo({ ...nuevo, tipo: e.target.value })}><option>principal</option><option>ampliado</option></select></div>
          <div><label className="etiqueta">Fuentes (opcional)</label><input className="campo" placeholder="linkedin,indeed" value={nuevo.fuentes} onChange={(e) => setNuevo({ ...nuevo, fuentes: e.target.value })} /></div>
          <button className="btn" disabled={!nuevo.termino.trim()} onClick={() => correr(async () => {
            await api.post("/terminos", { ...nuevo, fuentes: nuevo.fuentes || null, activo: true });
            setNuevo({ ...nuevo, termino: "" });
          })}>Agregar</button>
        </div>
      )}
      <div className="tarjeta overflow-x-auto">
        <div className="mb-2"><select className="campo" value={filtro} onChange={(e) => setFiltro(e.target.value)}><option value="">Todas las carreras</option>{CARRERAS.map((c) => <option key={c}>{c}</option>)}</select>
          <span className="ml-2 text-sm text-texto-suave">{visibles.length} términos</span></div>
        <table className="tabla">
          <thead><tr><th>Término</th><th>Carrera</th><th>Tipo</th><th>Fuentes</th><th>Activo</th><th /></tr></thead>
          <tbody>{visibles.map((t) => (
            <tr key={t.id} className={t.activo ? "" : "opacity-50"}>
              <td>{t.termino}</td><td>{t.carrera}</td><td>{t.tipo}</td><td>{t.fuentes || "todas"}</td>
              <td>{admin ? <input type="checkbox" checked={t.activo} onChange={(e) => correr(() => api.put(`/terminos/${t.id}`, { ...t, activo: e.target.checked }))} /> : t.activo ? "sí" : "no"}</td>
              <td>{admin && <button className="btn-peligro" onClick={() => confirm(`¿Eliminar “${t.termino}”?`) && correr(() => api.del(`/terminos/${t.id}`))}>Eliminar</button>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
