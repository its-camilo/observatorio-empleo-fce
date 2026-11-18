import { useState } from "react";
import { qs } from "../api";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Curso = {
  plataforma: string;
  termino: string;
  habilidad_demanda: string | null;
  demanda_pct: number | null;
  puntaje_recomendacion: number | null;
  posicion: number;
  titulo: string;
  url: string;
  organizacion: string;
  nivel: string | null;
  calificacion: number | null;
  num_calificaciones: number | null;
  inscritos_recientes: number | null;
  semestre: string;
  corte: string;
};

export default function Cursos() {
  const [plataforma, setPlataforma] = useState("");
  const [termino, setTermino] = useState("");
  const [carrera, setCarrera] = useState("");
  const { datos, error } = useDatos<Curso[]>(`/cursos${qs({ plataforma, termino, carrera: carrera || undefined })}`, [
    plataforma,
    termino,
    carrera,
  ]);
  return (
    <div className="space-y-4">
      <Titulo>Cursos en tendencia</Titulo>
      <Aviso>
        Cursos buscados según la demanda en ofertas guardadas del corte (no una lista fija). Ordenados por puntaje de recomendación
        (demanda en ofertas + señal de la plataforma).
      </Aviso>
      <div className="flex flex-wrap gap-2">
        <select className="campo" value={plataforma} onChange={(e) => setPlataforma(e.target.value)}>
          <option value="">Todas las plataformas</option>
          <option>Coursera</option>
          <option>edX</option>
          <option>Platzi</option>
        </select>
        <input className="campo" placeholder="Habilidad o término" value={termino} onChange={(e) => setTermino(e.target.value)} />
        <input className="campo" placeholder="Carrera" value={carrera} onChange={(e) => setCarrera(e.target.value)} />
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos ? (
        <Cargando />
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Habilidad</th>
                <th>Demanda</th>
                <th>Puntaje</th>
                <th>Plataforma</th>
                <th>Curso</th>
                <th>Organización</th>
                <th>Corte</th>
              </tr>
            </thead>
            <tbody>
              {datos.map((c) => (
                <tr key={c.url + c.semestre + c.corte}>
                  <td>{c.habilidad_demanda || c.termino}</td>
                  <td className="text-xs">{c.demanda_pct != null ? `Pedido en ${c.demanda_pct}% de las ofertas` : "—"}</td>
                  <td>{c.puntaje_recomendacion != null ? c.puntaje_recomendacion.toFixed(3) : "—"}</td>
                  <td>{c.plataforma}</td>
                  <td>
                    <a className="text-institucional font-semibold underline" href={c.url} target="_blank" rel="noreferrer">
                      {c.titulo}
                    </a>
                  </td>
                  <td className="text-xs">{c.organizacion}</td>
                  <td className="text-xs">
                    {c.semestre} {c.corte}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {datos.length === 0 && <p className="p-2 text-sm text-texto-suave">Sin cursos todavía (corren tras consolidar).</p>}
        </div>
      )}
    </div>
  );
}