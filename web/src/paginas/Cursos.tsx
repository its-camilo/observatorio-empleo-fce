import { useState } from "react";
import { qs } from "../api";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Curso = { plataforma: string; termino: string; posicion: number; titulo: string; url: string; organizacion: string; nivel: string | null;
  calificacion: number | null; num_calificaciones: number | null; inscritos_recientes: number | null; semestre: string; corte: string };

export default function Cursos() {
  const [plataforma, setPlataforma] = useState("");
  const [termino, setTermino] = useState("");
  const { datos, error } = useDatos<Curso[]>(`/cursos${qs({ plataforma, termino })}`, [plataforma, termino]);
  return (
    <div className="space-y-4">
      <Titulo>Cursos en tendencia</Titulo>
      <Aviso>Cursos que muestran Coursera, edX y Platzi para los términos configurados (módulo opcional, tabla aparte de las ofertas). La posición es el orden del buscador de cada plataforma.</Aviso>
      <div className="flex gap-2">
        <select className="campo" value={plataforma} onChange={(e) => setPlataforma(e.target.value)}><option value="">Todas las plataformas</option><option>Coursera</option><option>edX</option><option>Platzi</option></select>
        <input className="campo" placeholder="término (p. ej. excel)" value={termino} onChange={(e) => setTermino(e.target.value)} />
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos ? <Cargando /> : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Término</th><th>Plataforma</th><th>#</th><th>Curso</th><th>Organización</th><th>Nivel</th><th>Calificación</th><th>Popularidad</th><th>Corte</th></tr></thead>
            <tbody>{datos.map((c) => (
              <tr key={c.url + c.semestre + c.corte}>
                <td>{c.termino}</td><td>{c.plataforma}</td><td>{c.posicion}</td>
                <td><a className="text-institucional font-semibold underline" href={c.url} target="_blank" rel="noreferrer">{c.titulo}</a></td>
                <td className="text-xs">{c.organizacion}</td><td className="text-xs">{c.nivel}</td>
                <td>{c.calificacion ?? "—"}</td>
                <td className="text-xs">{c.num_calificaciones ? `${c.num_calificaciones.toLocaleString("es-CO")} calificaciones` : c.inscritos_recientes ? `${c.inscritos_recientes.toLocaleString("es-CO")} inscritos recientes` : "—"}</td>
                <td className="text-xs">{c.semestre} {c.corte}</td>
              </tr>
            ))}</tbody>
          </table>
          {datos.length === 0 && <p className="p-2 text-sm text-texto-suave">Sin cursos todavía.</p>}
        </div>
      )}
    </div>
  );
}
