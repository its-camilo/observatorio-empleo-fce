import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { qs } from "../api";
import { Aviso, Barras, Cargando, SelectorCorte, Titulo, useDatos } from "../componentes/ui";
import Cursos from "./Cursos";
import TemasRecomendados from "./TemasRecomendados";

type Corte = { semestre: string; corte: string; ofertas: number };
type Fila = {
  posicion: number;
  software: string;
  grupo: string;
  ofertas: number;
  porcentaje: number;
  variacion_pp?: number | null;
  corte_anterior?: string;
  total_ofertas_carrera: number;
};
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
  softwares: {
    software: string;
    grupo: string;
    porcentaje_a: number;
    porcentaje_b: number;
    variacion_pp: number;
    estado: string;
    ofertas_a: number;
    ofertas_b: number;
  }[];
  tipos_oferta: FilaCmpDist[];
  sectores: FilaCmpDist[];
  advertencias: string[];
};

const CARRERAS = ["", "Administración de Empresas", "Contaduría Pública", "Economía"];
const COLOR: Record<string, string> = { "subió": "text-institucional", "bajó": "text-marina", nuevo: "text-acento", "desapareció": "text-texto-suave", igual: "text-texto-suave" };

const PESTANAS = [
  { id: "general", label: "Software y grupos" },
  { id: "competencias", label: "Habilidades e idiomas" },
  { id: "tipo-oferta", label: "Tipo de oferta" },
  { id: "sector", label: "Sector" },
  { id: "comparar", label: "Comparar cortes" },
  { id: "cursos", label: "Cursos en tendencia" },
  { id: "temas", label: "Temas para dictar" },
] as const;

type TabId = (typeof PESTANAS)[number]["id"];

const PESTANAS_FILTRO_CORTE = new Set<TabId>(["general", "competencias", "tipo-oferta", "sector"]);

const TAB_IDS = new Set<string>(PESTANAS.map((p) => p.id));

function tabValido(raw: string | null): TabId {
  if (raw && TAB_IDS.has(raw)) return raw as TabId;
  return "general";
}

function CeldaVariacion({ v, corteAnterior }: { v: number | null | undefined; corteAnterior?: string }) {
  if (v == null) {
    return <span className="text-texto-suave/70">{corteAnterior ? "nuevo" : "—"}</span>;
  }
  const cls = v >= 0 ? "text-institucional" : "text-marina";
  return (
    <span className={cls}>
      {v > 0 ? "+" : ""}
      {v.toFixed(1)} pp
    </span>
  );
}

function PestanaGeneral({ sem, cor, carrera }: { sem: string; cor: string; carrera: string }) {
  const { datos: rk, cargando } = useDatos<{ ranking: Fila[]; grupos: { grupo: string; menciones: number }[] }>(
    `/analisis/ranking${qs({ semestre: sem, corte: cor, carrera })}`,
    [sem, cor, carrera],
  );
  if (cargando && !rk) return <Cargando />;
  if (!rk) return <Aviso>Sin datos para este corte.</Aviso>;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="tarjeta tabla-contenedor lg:col-span-2">
        <h2 className="mb-2 font-semibold">
          Ranking de softwares {rk.ranking[0] && `· ${rk.ranking[0].total_ofertas_carrera} ofertas`}
          {carrera ? ` · ${carrera}` : " · Todas las carreras"}
        </h2>
        <table className="tabla">
          <thead>
            <tr>
              <th>#</th>
              <th>Software</th>
              <th>Grupo</th>
              <th>Ofertas</th>
              <th>%</th>
              <th>Variación vs. {rk.ranking[0]?.corte_anterior || "anterior"}</th>
            </tr>
          </thead>
          <tbody>
            {rk.ranking.map((r) => (
              <tr key={r.software}>
                <td>{r.posicion}</td>
                <td className="font-medium">{r.software}</td>
                <td className="text-xs">{r.grupo}</td>
                <td>{r.ofertas}</td>
                <td>{r.porcentaje.toFixed(1)} %</td>
                <td>
                  <CeldaVariacion v={r.variacion_pp} corteAnterior={r.corte_anterior} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="tarjeta">
        <h2 className="mb-2 font-semibold">Peso por grupo</h2>
        <Barras datos={rk.grupos.map((g) => ({ etiqueta: g.grupo, valor: g.menciones }))} />
      </div>
    </div>
  );
}

function PestanaCompetencias({ sem, cor, carrera }: { sem: string; cor: string; carrera: string }) {
  const extraQs = qs({ semestre: sem, corte: cor, carrera });
  const { datos: rkHab, cargando: cHab } = useDatos<{ ranking: FilaGc[] }>(`/analisis/ranking-habilidades${extraQs}`, [sem, cor, carrera]);
  const { datos: rkIdi, cargando: cIdi } = useDatos<{ ranking: FilaGc[] }>(`/analisis/ranking-idiomas${extraQs}`, [sem, cor, carrera]);
  if ((cHab || cIdi) && !rkHab && !rkIdi) return <Cargando />;
  if (!rkHab?.ranking?.length && !rkIdi?.ranking?.length) {
    return <Aviso>No hay menciones de habilidades o idiomas en este corte{carrera ? ` para ${carrera}` : ""}.</Aviso>;
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {rkHab && (
        <div className="tarjeta tabla-contenedor">
          <h2 className="mb-2 font-semibold">Habilidades blandas (RF-18)</h2>
          <table className="tabla">
            <thead>
              <tr>
                <th>#</th>
                <th>Habilidad</th>
                <th>Ofertas</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {rkHab.ranking.slice(0, 15).map((r) => (
                <tr key={r.habilidad}>
                  <td>{r.posicion}</td>
                  <td>{r.habilidad}</td>
                  <td>{r.ofertas}</td>
                  <td>{r.porcentaje.toFixed(1)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rkIdi && (
        <div className="tarjeta tabla-contenedor">
          <h2 className="mb-2 font-semibold">Idiomas (RF-18)</h2>
          <table className="tabla">
            <thead>
              <tr>
                <th>#</th>
                <th>Idioma</th>
                <th>Ofertas</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {rkIdi.ranking.slice(0, 15).map((r) => (
                <tr key={r.idioma}>
                  <td>{r.posicion}</td>
                  <td>{r.idioma}</td>
                  <td>{r.ofertas}</td>
                  <td>{r.porcentaje.toFixed(1)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PestanaTipoOferta({ sem, cor, carrera }: { sem: string; cor: string; carrera: string }) {
  const { datos: rkTipo, cargando } = useDatos<{ ranking: FilaDist[] }>(
    `/analisis/ranking-tipo-oferta${qs({ semestre: sem, corte: cor, carrera })}`,
    [sem, cor, carrera],
  );
  if (cargando && !rkTipo) return <Cargando />;
  if (!rkTipo?.ranking?.length) return <Aviso>Sin datos de tipo de oferta en este corte.</Aviso>;
  return (
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
              <td>
                <CeldaVariacion v={r.variacion_pp} corteAnterior={r.corte_anterior} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PestanaSector({ sem, cor, carrera }: { sem: string; cor: string; carrera: string }) {
  const { datos: rkSector, cargando } = useDatos<{ ranking: FilaDist[] }>(
    `/analisis/ranking-sector${qs({ semestre: sem, corte: cor, carrera })}`,
    [sem, cor, carrera],
  );
  if (cargando && !rkSector) return <Cargando />;
  if (!rkSector?.ranking?.length) return <Aviso>Sin datos de sector en este corte.</Aviso>;
  return (
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
              <td>
                <CeldaVariacion v={r.variacion_pp} corteAnterior={r.corte_anterior} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PestanaComparar({
  cortes,
  a,
  b,
  carrera,
  onA,
  onB,
}: {
  cortes: Corte[];
  a: string;
  b: string;
  carrera: string;
  onA: (v: string) => void;
  onB: (v: string) => void;
}) {
  const [sa, ca] = a.split("|");
  const [sb, cb] = b.split("|");
  const { datos: cmp, cargando } = useDatos<Comparacion>(
    a && b ? `/analisis/comparar${qs({ semestre_a: sa, corte_a: ca, semestre_b: sb, corte_b: cb, carrera })}` : null,
    [a, b, carrera],
  );
  return (
    <div className="tarjeta tabla-contenedor">
      <h2 className="mb-2 font-semibold">Comparación entre cortes</h2>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div>
          <label className="etiqueta">Corte A (anterior)</label>
          <SelectorCorte cortes={cortes} valor={a} onCambio={onA} />
        </div>
        <div>
          <label className="etiqueta">Corte B (posterior)</label>
          <SelectorCorte cortes={cortes} valor={b} onCambio={onB} />
        </div>
      </div>
      {cargando && !cmp && <Cargando />}
      {cmp && (
        <>
          {cmp.advertencias.map((x) => (
            <Aviso key={x} tipo="alerta">
              {x}
            </Aviso>
          ))}
          <p className="mb-2 text-xs text-texto-suave">
            A: {cmp.corte_a.total_ofertas} ofertas ({cmp.corte_a.fuentes.join(", ")}) · B: {cmp.corte_b.total_ofertas}{" "}
            ofertas ({cmp.corte_b.fuentes.join(", ")})
            {carrera ? ` · Carrera: ${carrera}` : " · Todas las carreras"}
          </p>
          <h3 className="mb-2 mt-4 text-sm font-semibold uppercase text-marina">Softwares</h3>
          <table className="tabla">
            <thead>
              <tr>
                <th>Software</th>
                <th>Grupo</th>
                <th>% A</th>
                <th>% B</th>
                <th>Variación</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {cmp.softwares.map((r) => (
                <tr key={r.software}>
                  <td className="font-medium">{r.software}</td>
                  <td className="text-xs">{r.grupo}</td>
                  <td>{r.porcentaje_a.toFixed(1)} %</td>
                  <td>{r.porcentaje_b.toFixed(1)} %</td>
                  <td>
                    {r.variacion_pp > 0 ? "+" : ""}
                    {r.variacion_pp.toFixed(1)} pp
                  </td>
                  <td className={`font-medium ${COLOR[r.estado] || ""}`}>{r.estado}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {cmp.tipos_oferta?.length ? (
            <>
              <h3 className="mb-2 mt-6 text-sm font-semibold uppercase text-marina">Tipo de oferta</h3>
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>% A</th>
                    <th>% B</th>
                    <th>Variación</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {cmp.tipos_oferta.map((r) => (
                    <tr key={r.tipo_oferta}>
                      <td className="font-medium">{r.tipo_oferta}</td>
                      <td>{r.porcentaje_a.toFixed(1)} %</td>
                      <td>{r.porcentaje_b.toFixed(1)} %</td>
                      <td>
                        {r.variacion_pp > 0 ? "+" : ""}
                        {r.variacion_pp.toFixed(1)} pp
                      </td>
                      <td className={`font-medium ${COLOR[r.estado] || ""}`}>{r.estado}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
          {cmp.sectores?.length ? (
            <>
              <h3 className="mb-2 mt-6 text-sm font-semibold uppercase text-marina">Sector de empresa</h3>
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Sector</th>
                    <th>% A</th>
                    <th>% B</th>
                    <th>Variación</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {cmp.sectores.map((r) => (
                    <tr key={r.sector}>
                      <td className="font-medium">{r.sector}</td>
                      <td>{r.porcentaje_a.toFixed(1)} %</td>
                      <td>{r.porcentaje_b.toFixed(1)} %</td>
                      <td>
                        {r.variacion_pp > 0 ? "+" : ""}
                        {r.variacion_pp.toFixed(1)} pp
                      </td>
                      <td className={`font-medium ${COLOR[r.estado] || ""}`}>{r.estado}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

export default function Rankings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = tabValido(searchParams.get("tab"));
  const { datos: cortes, error } = useDatos<Corte[]>("/analisis/cortes");
  const [sel, setSel] = useState("");
  const [carrera, setCarrera] = useState("");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [montados, setMontados] = useState<Record<string, boolean>>(() => ({ [tab]: true }));

  useEffect(() => {
    setMontados((m) => (m[tab] ? m : { ...m, [tab]: true }));
  }, [tab]);

  useEffect(() => {
    if (cortes && cortes.length) {
      const ult = cortes[cortes.length - 1];
      const ultKey = `${ult.semestre}|${ult.corte}`;
      setSel((prev) => prev || ultKey);
      setB((prev) => prev || ultKey);
      const pen = cortes[Math.max(0, cortes.length - 2)];
      setA((prev) => prev || `${pen.semestre}|${pen.corte}`);
    }
  }, [cortes]);

  const setTab = useCallback(
    (id: TabId) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("tab", id);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  const onCortePrincipal = (v: string) => {
    setSel(v);
    setB(v);
  };

  const onCorteBComparar = (v: string) => {
    setB(v);
    setSel(v);
  };

  const [sem, cor] = sel.split("|");
  const filtrosListos = Boolean(sem && cor);
  const compararListo = Boolean(a && b);
  const usaFiltroCorte = PESTANAS_FILTRO_CORTE.has(tab);
  const tabAutonoma = tab === "cursos" || tab === "temas";

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!cortes) return <Cargando />;
  if (!cortes.length && !tabAutonoma) return <Aviso>Aún no hay datos. Lance una corrida primero.</Aviso>;

  return (
    <div className="space-y-4">
      <Titulo>Rankings y comparación</Titulo>

      {usaFiltroCorte && (
        <div className="tarjeta flex flex-wrap items-end gap-3">
          <div>
            <label className="etiqueta">Semestre y corte</label>
            <SelectorCorte cortes={cortes} valor={sel} onCambio={onCortePrincipal} />
          </div>
          <div>
            <label className="etiqueta">Carrera</label>
            <select className="campo" value={carrera} onChange={(e) => setCarrera(e.target.value)}>
              {CARRERAS.map((c) => (
                <option key={c} value={c}>
                  {c || "Todas"}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      <nav
        className="-mx-1 flex gap-2 overflow-x-auto border-b border-niebla px-1 pb-2"
        aria-label="Secciones de rankings"
      >
        {PESTANAS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`shrink-0 rounded px-3 py-1 text-sm font-semibold ${
              tab === t.id ? "bg-institucional text-white" : "bg-niebla/40 text-texto"
            }`}
            aria-current={tab === t.id ? "page" : undefined}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {usaFiltroCorte && !filtrosListos ? (
        <Aviso>Elija un corte para ver los rankings.</Aviso>
      ) : tab === "comparar" && !compararListo ? (
        <Aviso>Elija los dos cortes a comparar.</Aviso>
      ) : (
        <>
          {montados.cursos && (
            <div className={tab === "cursos" ? "" : "hidden"} aria-hidden={tab !== "cursos"}>
              <Cursos embebido />
            </div>
          )}
          {montados.temas && (
            <div className={tab === "temas" ? "" : "hidden"} aria-hidden={tab !== "temas"}>
              <TemasRecomendados embebido />
            </div>
          )}
          {montados.general && (
            <div className={tab === "general" ? "" : "hidden"} aria-hidden={tab !== "general"}>
              {filtrosListos && <PestanaGeneral sem={sem} cor={cor} carrera={carrera} />}
            </div>
          )}
          {montados.competencias && (
            <div className={tab === "competencias" ? "" : "hidden"} aria-hidden={tab !== "competencias"}>
              {filtrosListos && <PestanaCompetencias sem={sem} cor={cor} carrera={carrera} />}
            </div>
          )}
          {montados["tipo-oferta"] && (
            <div className={tab === "tipo-oferta" ? "" : "hidden"} aria-hidden={tab !== "tipo-oferta"}>
              {filtrosListos && <PestanaTipoOferta sem={sem} cor={cor} carrera={carrera} />}
            </div>
          )}
          {montados.sector && (
            <div className={tab === "sector" ? "" : "hidden"} aria-hidden={tab !== "sector"}>
              {filtrosListos && <PestanaSector sem={sem} cor={cor} carrera={carrera} />}
            </div>
          )}
          {montados.comparar && (
            <div className={tab === "comparar" ? "" : "hidden"} aria-hidden={tab !== "comparar"}>
              <PestanaComparar cortes={cortes} a={a} b={b} carrera={carrera} onA={setA} onB={onCorteBComparar} />
            </div>
          )}
        </>
      )}
    </div>
  );
}