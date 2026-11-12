import { useState } from "react";
import { api } from "../api";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Token = { id: number; nombre: string; prefijo: string; revocado: boolean; creado_en: string; ultimo_uso: string | null };

export default function TokensMcp() {
  const { datos, error, recargar } = useDatos<Token[]>("/tokens-mcp");
  const [nombre, setNombre] = useState("Claude de escritorio");
  const [nuevo, setNuevo] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const url = `${window.location.origin}/mcp`;
  const crear = async () => {
    setErr(null);
    try {
      const r = await api.post<{ token: string }>("/tokens-mcp", { nombre });
      setNuevo(r.token);
      recargar();
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="space-y-4">
      <Titulo>Tokens del servidor MCP</Titulo>
      <Aviso>
        El servidor MCP <code className="font-mono">{url}</code> es público y de solo lectura. Su token personal hereda su rol: con cuenta
        de usuario amplía las mismas consultas que la sesión web; los administradores además ven <b>estado_corrida</b> y <b>lanzar_corrida</b>. Envíe el token en la cabecera
        <code className="font-mono"> Authorization: Bearer &lt;token&gt;</code>. Revóquelo si se filtra.
      </Aviso>
      {err && <Aviso tipo="error">{err}</Aviso>}
      <div className="tarjeta flex flex-wrap items-end gap-2">
        <div><label className="etiqueta">Nombre (para reconocerlo)</label><input className="campo" value={nombre} onChange={(e) => setNombre(e.target.value)} /></div>
        <button className="btn" onClick={crear}>Generar token</button>
      </div>
      {nuevo && (
        <Aviso tipo="ok">
          <div className="font-semibold">Copie el token ahora: no se volverá a mostrar.</div>
          <code className="block break-all rounded bg-white p-2 font-mono text-xs">{nuevo}</code>
          <button className="btn-sec mt-2" onClick={() => navigator.clipboard.writeText(nuevo)}>Copiar</button>
          <pre className="mt-2 whitespace-pre-wrap rounded bg-white p-2 font-mono text-xs">{JSON.stringify({ mcpServers: { observatorio: { url, headers: { Authorization: `Bearer ${nuevo}` } } } }, null, 2)}</pre>
        </Aviso>
      )}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos ? <Cargando /> : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Nombre</th><th>Inicio</th><th>Creado</th><th>Último uso</th><th>Estado</th><th /></tr></thead>
            <tbody>{datos.map((t) => (
              <tr key={t.id}><td>{t.nombre}</td><td className="font-mono text-xs">{t.prefijo}…</td><td className="text-xs">{t.creado_en?.slice(0, 16).replace("T", " ")}</td>
                <td className="text-xs">{t.ultimo_uso?.slice(0, 16).replace("T", " ") || "—"}</td><td>{t.revocado ? "revocado" : "activo"}</td>
                <td>{!t.revocado && <button className="btn-peligro" onClick={async () => { if (confirm("¿Revocar este token?")) { await api.del(`/tokens-mcp/${t.id}`); recargar(); } }}>Revocar</button>}</td></tr>
            ))}</tbody>
          </table>
          {datos.length === 0 && <p className="p-2 text-sm text-slate-500">No tiene tokens.</p>}
        </div>
      )}
    </div>
  );
}
