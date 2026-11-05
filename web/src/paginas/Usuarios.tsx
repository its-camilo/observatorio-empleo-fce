import { useState } from "react";
import { api } from "../api";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type U = { id: number; email: string; nombre: string | null; rol: string; estado: string; creado_en: string; ultimo_acceso: string | null };

export default function Usuarios() {
  const { datos, error, recargar } = useDatos<U[]>("/usuarios");
  const [err, setErr] = useState<string | null>(null);
  const cambiar = async (u: U, cambio: Partial<U>) => {
    setErr(null);
    try { await api.put(`/usuarios/${u.id}`, cambio); recargar(); } catch (e) { setErr((e as Error).message); }
  };
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;
  const pendientes = datos.filter((u) => u.estado === "pendiente").length;
  return (
    <div className="space-y-4">
      <Titulo>Usuarios</Titulo>
      {pendientes > 0 && <Aviso tipo="alerta">{pendientes} usuario(s) esperan aprobación.</Aviso>}
      {err && <Aviso tipo="error">{err}</Aviso>}
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Correo</th><th>Nombre</th><th>Rol</th><th>Estado</th><th>Último acceso</th><th>Acciones</th></tr></thead>
          <tbody>{datos.map((u) => (
            <tr key={u.id}>
              <td>{u.email}</td><td>{u.nombre}</td>
              <td><select className="campo" value={u.rol} onChange={(e) => cambiar(u, { rol: e.target.value })}><option value="usuario">usuario</option><option value="admin">admin</option></select></td>
              <td>{u.estado}</td><td className="text-xs">{u.ultimo_acceso?.slice(0, 16).replace("T", " ")}</td>
              <td className="whitespace-nowrap">
                {u.estado !== "aprobado" && <button className="btn mr-1" onClick={() => cambiar(u, { estado: "aprobado" })}>Aprobar</button>}
                {u.estado !== "rechazado" && <button className="btn-sec" onClick={() => cambiar(u, { estado: "rechazado" })}>Bloquear</button>}
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
