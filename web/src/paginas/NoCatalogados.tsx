import { useState } from "react";
import { api, qs } from "../api";
import { useEsAdmin } from "../main";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Nc = { id: number; termino: string; frecuencia_total: number; frecuencia_ultima: number; estado: string; ejemplo_id_oferta: string | null; semestre: string; corte: string };

export default function NoCatalogados() {
  const admin = useEsAdmin();
  const [estado, setEstado] = useState("pendiente");
  const { datos, error, recargar } = useDatos<Nc[]>(`/no-catalogados${qs({ estado })}`, [estado]);
  const { datos: cat } = useDatos<{ software: string; grupo: string }[]>("/catalogo");
  const [grupo, setGrupo] = useState<Record<number, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const grupos = Array.from(new Set((cat || []).map((c) => c.grupo)));
  const decidir = async (x: Nc, nuevo: string) => {
    setErr(null);
    try {
      await api.put(`/no-catalogados/${x.id}`, { estado: nuevo, software: x.termino, grupo: grupo[x.id] || grupos[0] });
      recargar();
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="space-y-4">
      <Titulo>Términos no catalogados</Titulo>
      <Aviso>Herramientas que aparecen con frecuencia en las ofertas y no están en el catálogo. Agréguelas para que se cuenten desde la próxima ejecución, o descártelas.</Aviso>
      {err && <Aviso tipo="error">{err}</Aviso>}
      <select className="campo" value={estado} onChange={(e) => setEstado(e.target.value)}>
        <option value="pendiente">Pendientes</option><option value="agregado">Agregados</option><option value="descartado">Descartados</option><option value="">Todos</option>
      </select>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos ? <Cargando /> : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Término</th><th>Ofertas (última corrida)</th><th>Ofertas (total)</th><th>Corte</th><th>Ejemplo</th><th>Estado</th>{admin && <th>Decisión</th>}</tr></thead>
            <tbody>{datos.map((x) => (
              <tr key={x.id}>
                <td className="font-medium">{x.termino}</td><td>{x.frecuencia_ultima}</td><td>{x.frecuencia_total}</td><td>{x.semestre} {x.corte}</td>
                <td className="text-xs">{x.ejemplo_id_oferta}</td><td>{x.estado}</td>
                {admin && <td className="whitespace-nowrap">
                  <select className="campo mr-1 max-w-[12rem]" value={grupo[x.id] || grupos[0] || ""} onChange={(e) => setGrupo({ ...grupo, [x.id]: e.target.value })}>
                    {grupos.map((g) => <option key={g}>{g}</option>)}</select>
                  <button className="btn mr-1" onClick={() => decidir(x, "agregado")}>Agregar</button>
                  <button className="btn-sec" onClick={() => decidir(x, "descartado")}>Descartar</button>
                </td>}
              </tr>
            ))}</tbody>
          </table>
          {datos.length === 0 && <p className="p-2 text-sm text-slate-500">No hay términos en este estado.</p>}
        </div>
      )}
    </div>
  );
}
