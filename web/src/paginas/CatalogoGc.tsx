import { useState } from "react";
import { api } from "../api";
import { useEsAdmin } from "../main";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Item = { id: number; nombre: string; activo: boolean; sinonimos: string[] };

function PanelCatalogo({ ruta, titulo }: { ruta: string; titulo: string }) {
  const admin = useEsAdmin();
  const { datos, error, recargar } = useDatos<Item[]>(ruta, []);
  const [nuevo, setNuevo] = useState({ nombre: "", sinonimo: "" });
  const [err, setErr] = useState<string | null>(null);
  const guardar = async () => {
    setErr(null);
    try {
      await api.post(ruta, { nombre: nuevo.nombre, activo: true, sinonimos: nuevo.sinonimo ? [nuevo.sinonimo] : [] });
      setNuevo({ nombre: "", sinonimo: "" });
      recargar();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <div className="tarjeta space-y-3">
      <h2 className="font-semibold">{titulo}</h2>
      {err && <Aviso tipo="error">{err}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos ? <Cargando /> : (
        <table className="tabla">
          <thead><tr><th>Nombre</th><th>Sinónimos</th><th>Activo</th></tr></thead>
          <tbody>
            {datos.map((x) => (
              <tr key={x.id}>
                <td className="font-medium">{x.nombre}</td>
                <td className="text-xs">{x.sinonimos.join(" · ")}</td>
                <td>{x.activo ? "sí" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {admin && (
        <div className="flex flex-wrap gap-2">
          <input className="campo" placeholder="Nombre canónico" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} />
          <input className="campo" placeholder="Sinónimo inicial (opcional)" value={nuevo.sinonimo} onChange={(e) => setNuevo({ ...nuevo, sinonimo: e.target.value })} />
          <button className="btn" disabled={!nuevo.nombre.trim()} onClick={guardar}>Agregar</button>
        </div>
      )}
      {admin && datos && datos.length > 0 && (
        <p className="text-xs text-texto-suave">Para más sinónimos use la API o edite en base; la vista rápida agrega con el formulario de arriba por ítem existente en futuras iteraciones.</p>
      )}
    </div>
  );
}

export default function CatalogoGc({ embebido = false }: { embebido?: boolean }) {
  return (
    <div className="space-y-4">
      {!embebido && <Titulo>Catálogo de habilidades e idiomas</Titulo>}
      {embebido && <h2 className="font-semibold">Habilidades e idiomas</h2>}
      <Aviso>Lista editable (RF-18): los sinónimos en español e inglés alimentan la detección en las ofertas sin cambiar código.</Aviso>
      <PanelCatalogo ruta="/catalogo-habilidades" titulo="Habilidades blandas" />
      <PanelCatalogo ruta="/catalogo-idiomas" titulo="Idiomas" />
    </div>
  );
}