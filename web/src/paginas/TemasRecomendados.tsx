import { useMemo, useState } from "react";
import { qs } from "../api";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type CursoRef = { titulo: string; url: string; plataforma: string };
type Tema = {
  tema: string;
  grupo: string;
  ofertas: number;
  pct_ofertas: number;
  variacion_pp: number | null;
  por_carrera: Record<string, { n: number; pct: number }>;
  cursos_referencia: CursoRef[];
  semestre: string;
  corte: string;
};

export default function TemasRecomendados() {
  const [semestre, setSemestre] = useState("2026-II");
  const [corte, setCorte] = useState("Mitad");
  const [carrera, setCarrera] = useState("");
  const q = useMemo(() => qs({ semestre, corte, carrera: carrera || undefined }), [semestre, corte, carrera]);
  const { datos, error } = useDatos<Tema[]>(`/temas-recomendados${q}`, [q]);
  const exportUrl = `/api/exportar/csv?tabla=temas_recomendados&${new URLSearchParams({ semestre, corte }).toString()}`;

  return (
    <div className="space-y-4">
      <Titulo>Temas recomendados para dictar</Titulo>
      <Aviso>
        Prioridades de cursos libres y gestión del conocimiento (FCE): habilidades y software que más piden las ofertas guardadas del corte,
        con referencias en Coursera, edX y Platzi. La variación compara el porcentaje de ofertas con el corte anterior si existe.
      </Aviso>
      <div className="flex flex-wrap gap-2">
        <input className="campo" value={semestre} onChange={(e) => setSemestre(e.target.value)} placeholder="semestre" />
        <select className="campo" value={corte} onChange={(e) => setCorte(e.target.value)}>
          <option>Inicio</option>
          <option>Mitad</option>
          <option>Final</option>
        </select>
        <input className="campo" placeholder="Filtrar carrera" value={carrera} onChange={(e) => setCarrera(e.target.value)} />
        <a className="boton-secundario" href={exportUrl}>
          Exportar CSV
        </a>
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos ? (
        <Cargando />
      ) : (
        <div className="tarjeta tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>#</th>
                <th>Tema / habilidad</th>
                <th>Demanda</th>
                <th>Tendencia</th>
                <th>Por carrera</th>
                <th>Cursos de referencia (top 3)</th>
              </tr>
            </thead>
            <tbody>
              {datos.map((t, i) => (
                <tr key={t.tema}>
                  <td>{i + 1}</td>
                  <td className="font-medium">{t.tema}</td>
                  <td>
                    {t.ofertas} ofertas ({t.pct_ofertas}%)
                  </td>
                  <td className="text-xs">{t.variacion_pp != null ? `${t.variacion_pp >= 0 ? "+" : ""}${t.variacion_pp} pp` : "—"}</td>
                  <td className="text-xs max-w-[14rem]">
                    {Object.entries(t.por_carrera || {})
                      .map(([c, v]) => `${c}: ${v.pct}%`)
                      .join(" · ") || "—"}
                  </td>
                  <td className="text-xs space-y-1">
                    {(t.cursos_referencia || []).map((c) => (
                      <div key={c.url}>
                        <span className="text-texto-suave">{c.plataforma}: </span>
                        <a className="text-institucional underline" href={c.url} target="_blank" rel="noreferrer">
                          {c.titulo}
                        </a>
                      </div>
                    ))}
                    {(t.cursos_referencia || []).length === 0 && "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {datos.length === 0 && <p className="p-2 text-sm text-texto-suave">Sin datos para este corte (consolide ofertas primero).</p>}
        </div>
      )}
    </div>
  );
}