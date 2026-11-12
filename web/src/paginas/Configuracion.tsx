import { useState } from "react";
import { api } from "../api";
import { useEsAdmin } from "../main";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Param = { clave: string; valor: unknown; descripcion: string };

function Editor({ p, admin, alGuardar }: { p: Param; admin: boolean; alGuardar: () => void }) {
  const [texto, setTexto] = useState(JSON.stringify(p.valor, null, 2));
  const [msg, setMsg] = useState<{ tipo: "ok" | "error"; t: string } | null>(null);
  const guardar = async () => {
    try {
      await api.put(`/config/${p.clave}`, { valor: JSON.parse(texto) });
      setMsg({ tipo: "ok", t: "Guardado. Aplica desde la próxima ejecución." });
      alGuardar();
    } catch (e) {
      setMsg({ tipo: "error", t: e instanceof SyntaxError ? "El texto no es JSON válido." : (e as Error).message });
    }
  };
  return (
    <details className="tarjeta">
      <summary className="cursor-pointer"><b>{p.clave}</b> <span className="text-sm text-texto-suave">— {p.descripcion}</span></summary>
      <textarea className="campo mt-2 h-64 w-full font-mono text-xs" disabled={!admin} value={texto} onChange={(e) => setTexto(e.target.value)} />
      {msg && <Aviso tipo={msg.tipo}>{msg.t}</Aviso>}
      {admin && <button className="btn" onClick={guardar}>Guardar</button>}
    </details>
  );
}

export default function Configuracion() {
  const admin = useEsAdmin();
  const { datos, error, recargar } = useDatos<Param[]>("/config");
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;
  return (
    <div className="space-y-3">
      <Titulo>Configuración</Titulo>
      <Aviso>Parámetros de búsqueda y del procesamiento (fuentes, ciudades, ventana de días, límites, meta, reglas de carrera, IA, cursos).
        {admin ? " Edite con cuidado: el formato es JSON." : " Solo los administradores pueden editarlos."}</Aviso>
      {datos.map((p) => <Editor key={p.clave} p={p} admin={admin} alGuardar={recargar} />)}
    </div>
  );
}
