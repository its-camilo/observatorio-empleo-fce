import { useEffect, useState } from "react";
import { qs } from "../api";
import { Aviso, Barras, Cargando, SelectorCorte, Titulo, useDatos } from "../componentes/ui";

type Corte = { semestre: string; corte: string; ofertas: number };
type Fila = { posicion: number; software: string; grupo: string; ofertas: number; porcentaje: number; variacion_pp?: number | null; corte_anterior?: string; total_ofertas_carrera: number };
type FilaGc = { posicion: number; habilidad?: string; idioma?: string; ofertas: number; porcentaje: number; total_ofertas_carrera: number };
type FilaDist = {
  posicion: number;
  tipo_oferta?: string;
  sector?: string;
  ofertas: number;
  porcentaje: number;
  variacion_pp?: number | null;
  corte_anterior?: string;
  total_ofertas_carrera: number;
};
type FilaCmpDist = {
  tipo_oferta?: string;
  sector?: string;
  porcentaje_a: number;
  porcentaje_b: number;
  variacion_pp: number;
  estado: string;
  ofertas_a: number;
  ofertas_b: number;
};
type Comparacion = {
  corte_a: { semestre: string; corte: string; total_ofertas: number; fuentes: string[] };
  corte_b: { semestre: string; corte: string; total_ofertas: number; fuentes: string[] };
  softwares: { software: string; grupo: string; porcentaje_a: number; porcentaje_b: number; variacion_pp: number; estado: string; ofertas_a: number; ofertas_b: number }[];
  tipos_oferta: FilaCmpDist[];
  sectores: FilaCmpDist[];
  advertencias: string[];
};
const CARRERAS = ["", "Administración de Empresas", "Contaduría Pública", "Economía"];
const COLOR: Record<string, string> = { "subió": "text-institucional", "bajó": "text-marina", nuevo: "text-acento", "desapareció": "text-texto-suave", igual: "text-texto-suave" };

export default function Rankings() {
  const { datos: cortes, error } = useDatos<Corte[]>("/analisis/cortes");
  const [sel, setSel] = useState("");
  const [carrera, setCarrera] = useState("");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [extras, setExtras] = useState(false);
  const [compararActivo, setCompararActivo] = useState(false);
  useEffect(() => {
    if (cortes && cortes.length) {
      const ult = cortes[cortes.length - 1];
      setSel(`${ult.semestre}|${ult.corte}`);
      setB(`${ult.semestre}|${ult.corte}`);
      const pen = cortes[Math.max(0, cortes.length - 2)];
      setA(`${pen.semestre}|${pen.corte}`);
    }
  }, [cortes]);
  const [sem, cor] = sel.split("|");
  const { datos: rk } = useDatos<{ ranking: Fila[]; grupos: { grupo: string; menciones: number }[] }>(
    sel ? `/analisis/ranking${qs({ semestre: sem, corte: cor, carrera })}` : null, [sel, carrera]);
  const extraQs = sel ? qs({ semestre: sem, corte: cor, carrera }) : "";
  const { datos: rkHab } = useDatos<{ ranking: FilaGc[] }>(
    extras && sel ? `/analisis/ranking-habilidades${extraQs}` : null,
    [extras, sel, carrera],
  );
  const { datos: rkIdi } = useDatos<{ ranking: FilaGc[] }>(
    extras && sel ? `/analisis/ranking-idiomas${extraQs}` : null,
    [extras, sel, carrera],
  );
  const { datos: rkTipo } = useDatos<{ ranking: FilaDist[] }>(
    extras && sel ? `/analisis/ranking-tipo-oferta${extraQs}` : null,
    [extras, sel, carrera],
  );
  const { datos: rkSector } = useDatos<{ ranking: FilaDist[] }>(
    extras && sel ? `/analisis/ranking-sector${extraQs}` : null,
    [extras, sel, carrera],
  );
  const [sa, ca] = a.split("|");
  const [sb, cb] = b.split("|");
  const { datos: cmp } = useDatos<Comparacion>(
    compararActivo && a && b
      ? `/analisis/comparar${qs({ semestre_a: sa, corte_a: ca, semestre_b: sb, corte_b: cb, carrera })}`
      : null,
    [compararActivo, a, b, carrera],
  );

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!cortes) return <Cargando />;
  if (!cortes.length) return <Aviso>Aún no hay datos. Lance una corrida primero.</Aviso>;
  return (
    <div className="space-y-4">
      <Titulo>Rankings y comparación</Titulo>
      <div className="tarjeta flex flex-wrap items-end gap-3">
        <div><label className="etiqueta">Corte</label><SelectorCorte cortes={cortes} valor={sel} onCambio={setSel} /></div>
        <div><label className="etiqueta">Carrera</label>
          <select className="campo" value={carrera} onChange={(e) => setCarrera(e.target.value)}>
            {CARRERAS.map((c) => <option key={c} value={c}>{c || "Todas"}</option>)}
          </select></div>
      </div>
      <div className="flex flex-wrap gap-2">
        {!extras && (
          <button type="button" className="btn-sec text-xs" onClick={() => setExtras(true)}>
            Cargar habilidades, idiomas, tipos y sectores
          </button>
        )}
        {!compararActivo && (
          <button type="button" className="btn-sec text-xs" onClick={() => setCompararActivo(true)}>
            Cargar comparación entre cortes
          </button>
        )}
      </div>
      {rk && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="tarjeta tabla-contenedor lg:col-span-2">
            <h2 className="mb-2 font-semibold">Ranking de softwares {rk.ranking[0] && `· ${rk.ranking[0].total_ofertas_carrera} ofertas`}</h2>
            <table className="tabla">
              <thead><tr><th>#</th><th>Software</th><th>Grupo</th><th>Ofertas</th><th>%</th><th>Variación vs. {rk.ranking[0]?.corte_anterior || "anterior"}</th></tr></thead>
              <tbody>{rk.ranking.map((r) => (
                <tr key={r.software}><td>{r.posicion}</td><td className="font-medium">{r.software}</td><td className="text-xs">{r.grupo}</td><td>{r.ofertas}</td>
                  <td>{r.porcentaje.toFixed(1)} %</td>
                  <td className={r.variacion_pp == null ? "text-texto-suave/70" : r.variacion_pp >= 0 ? "text-institucional" : "text-marina"}>
                    {r.variacion_pp == null ? (r.corte_anterior ? "nuevo" : "—") : `${r.variacion_pp > 0 ? "+" : ""}${r.variacion_pp.toFixed(1)} pp`}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <div className="tarjeta"><h2 className="mb-2 font-semibold">Peso por grupo</h2>
            <Barras datos={rk.grupos.map((g) => ({ etiqueta: g.grupo, valor: g.menciones }))} /></div>
        </div>
      )}
      {(rkHab?.ranking?.length || rkIdi?.ranking?.length) ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {rkHab && (
            <div className="tarjeta tabla-contenedor">
              <h2 className="mb-2 font-semibold">Habilidades blandas (RF-18)</h2>
              <table className="tabla">
                <thead><tr><th>#</th><th>Habilidad</th><th>Ofertas</th><th>%</th></tr></thead>
                <tbody>{rkHab.ranking.slice(0, 15).map((r) => (
                  <tr key={r.habilidad}><td>{r.posicion}</td><td>{r.habilidad}</td><td>{r.ofertas}</td><td>{r.porcentaje.toFixed(1)} %</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {rkIdi && (
            <div className="tarjeta tabla-contenedor">
              <h2 className="mb-2 font-semibold">Idiomas (RF-18)</h2>
              <table className="tabla">
                <thead><tr><th>#</th><th>Idioma</th><th>Ofertas</th><th>%</th></tr></thead>
                <tbody>{rkIdi.ranking.slice(0, 15).map((r) => (
                  <tr key={r.idioma}><td>{r.posicion}</td><td>{r.idioma}</td><td>{r.ofertas}</td><td>{r.porcentaje.toFixed(1)} %</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
      {(rkTipo?.ranking?.length || rkSector?.ranking?.length) ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {rkTipo && (
            <div className="tarjeta tabla-contenedor">
              <h2 className="mb-2 font-semibold">
                Tipo de oferta {rkTipo.ranking[0] && `· ${rkTipo.ranking[0].total_ofertas_carrera} ofertas`}
              </h2>
              <table className="tabla">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Tipo</th>
                    <th>Ofertas</th>
                    <th>%</th>
                    <th>Variación vs. {rkTipo.ranking[0]?.corte_anterior || "anterior"}</th>
                  </tr>
                </thead>
                <tbody>
                  {rkTipo.ranking.map((r) => (
                    <tr key={r.tipo_oferta}>
                      <td>{r.posicion}</td>
                      <td className="font-medium">{r.tipo_oferta}</td>
                      <td>{r.ofertas}</td>
                      <td>{r.porcentaje.toFixed(1)} %</td>
                      <td className={r.variacion_pp == null ? "text-texto-suave/70" : r.variacion_pp >= 0 ? "text-institucional" : "text-marina"}>
                        {r.variacion_pp == null ? (r.corte_anterior ? "nuevo" : "—") : `${r.variacion_pp > 0 ? "+" : ""}${r.variacion_pp.toFixed(1)} pp`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {rkSector && (
            <div className="tarjeta tabla-contenedor">
              <h2 className="mb-2 font-semibold">
                Sector de empresa {rkSector.ranking[0] && `· ${rkSector.ranking[0].total_ofertas_carrera} ofertas`}
              </h2>
              <table className="tabla">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Sector</th>
                    <th>Ofertas</th>
                    <th>%</th>
                    <th>Variación vs. {rkSector.ranking[0]?.corte_anterior || "anterior"}</th>
                  </tr>
                </thead>
                <tbody>
                  {rkSector.ranking.map((r) => (
                    <tr key={r.sector}>
                      <td>{r.posicion}</td>
                      <td className="font-medium">{r.sector}</td>
                      <td>{r.ofertas}</td>
                      <td>{r.porcentaje.toFixed(1)} %</td>
                      <td className={r.variacion_pp == null ? "text-texto-suave/70" : r.variacion_pp >= 0 ? "text-institucional" : "text-marina"}>
                        {r.variacion_pp == null ? (r.corte_anterior ? "nuevo" : "—") : `${r.variacion_pp > 0 ? "+" : ""}${r.variacion_pp.toFixed(1)} pp`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
      <div className="tarjeta tabla-contenedor">
        <h2 className="mb-2 font-semibold">Comparación entre cortes</h2>
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div><label className="etiqueta">Corte A (anterior)</label><SelectorCorte cortes={cortes} valor={a} onCambio={setA} /></div>
          <div><label className="etiqueta">Corte B (posterior)</label><SelectorCorte cortes={cortes} valor={b} onCambio={setB} /></div>
        </div>
        {cmp && (
          <>
            {cmp.advertencias.map((x) => <Aviso key={x} tipo="alerta">{x}</Aviso>)}
            <p className="mb-2 text-xs text-texto-suave">A: {cmp.corte_a.total_ofertas} ofertas ({cmp.corte_a.fuentes.join(", ")}) · B: {cmp.corte_b.total_ofertas} ofertas ({cmp.corte_b.fuentes.join(", ")})</p>
            <h3 className="mb-2 mt-4 text-sm font-semibold uppercase text-marina">Softwares</h3>
            <table className="tabla">
              <thead><tr><th>Software</th><th>Grupo</th><th>% A</th><th>% B</th><th>Variación</th><th>Estado</th></tr></thead>
              <tbody>{cmp.softwares.map((r) => (
                <tr key={r.software}><td className="font-medium">{r.software}</td><td className="text-xs">{r.grupo}</td><td>{r.porcentaje_a.toFixed(1)} %</td>
                  <td>{r.porcentaje_b.toFixed(1)} %</td><td>{r.variacion_pp > 0 ? "+" : ""}{r.variacion_pp.toFixed(1)} pp</td>
                  <td className={`font-medium ${COLOR[r.estado] || ""}`}>{r.estado}</td></tr>
              ))}</tbody>
            </table>
            {cmp.tipos_oferta?.length ? (
              <>
                <h3 className="mb-2 mt-6 text-sm font-semibold uppercase text-marina">Tipo de oferta</h3>
                <table className="tabla">
                  <thead><tr><th>Tipo</th><th>% A</th><th>% B</th><th>Variación</th><th>Estado</th></tr></thead>
                  <tbody>{cmp.tipos_oferta.map((r) => (
                    <tr key={r.tipo_oferta}>
                      <td className="font-medium">{r.tipo_oferta}</td>
                      <td>{r.porcentaje_a.toFixed(1)} %</td>
                      <td>{r.porcentaje_b.toFixed(1)} %</td>
                      <td>{r.variacion_pp > 0 ? "+" : ""}{r.variacion_pp.toFixed(1)} pp</td>
                      <td className={`font-medium ${COLOR[r.estado] || ""}`}>{r.estado}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </>
            ) : null}
            {cmp.sectores?.length ? (
              <>
                <h3 className="mb-2 mt-6 text-sm font-semibold uppercase text-marina">Sector de empresa</h3>
                <table className="tabla">
                  <thead><tr><th>Sector</th><th>% A</th><th>% B</th><th>Variación</th><th>Estado</th></tr></thead>
                  <tbody>{cmp.sectores.map((r) => (
                    <tr key={r.sector}>
                      <td className="font-medium">{r.sector}</td>
                      <td>{r.porcentaje_a.toFixed(1)} %</td>
                      <td>{r.porcentaje_b.toFixed(1)} %</td>
                      <td>{r.variacion_pp > 0 ? "+" : ""}{r.variacion_pp.toFixed(1)} pp</td>
                      <td className={`font-medium ${COLOR[r.estado] || ""}`}>{r.estado}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
