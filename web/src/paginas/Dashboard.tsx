import { Link } from "react-router-dom";
import { Aviso, Barras, EstadoChip, EsqueletoKpi, EsqueletoTarjeta, Kpi, Titulo, useDatos } from "../componentes/ui";
import { useEsAdmin } from "../main";
import { Ejecucion } from "./Ejecuciones";

type Resumen = {
  semestre: string; corte: string; total_ofertas: number; ofertas_con_software: number;
  por_fuente: Record<string, number>; por_carrera: Record<string, number>; por_tipo_oferta: Record<string, number>;
  por_modalidad: Record<string, number>;
  top_softwares: { software: string; ofertas: number; porcentaje: number }[];
};
type Datos = {
  cortes: { semestre: string; corte: string; ofertas: number }[];
  ultimo_corte: { semestre: string; corte: string } | null;
  resumen: Resumen | null;
  total_historico: number;
  ultimas_corridas: Ejecucion[];
};

const aBarras = (o: Record<string, number>) => Object.entries(o).map(([etiqueta, valor]) => ({ etiqueta, valor }));

export default function Dashboard() {
  const admin = useEsAdmin();
  const { datos, error, cargando } = useDatos<Datos>("/dashboard");
  const r = datos?.resumen;
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  return (
    <div>
      <Titulo extra={admin ? <Link className="btn-cta" to="/lanzar">Lanzar corrida</Link> : undefined}>Inicio</Titulo>
      {cargando && !datos && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <EsqueletoKpi />
            <EsqueletoKpi />
            <EsqueletoKpi />
            <EsqueletoKpi />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <EsqueletoTarjeta alto="h-56" />
            <EsqueletoTarjeta alto="h-72" />
          </div>
        </>
      )}
      {!datos ? null : (
        <>
      {!r && (
        <Aviso>{admin ? "Aún no hay ofertas. Lance la primera corrida desde “Lanzar corrida”." : "Aún no hay ofertas en el observatorio."}</Aviso>
      )}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi etiqueta="Último corte" valor={r ? `${r.semestre} · ${r.corte}` : "—"} />
        <Kpi etiqueta="Ofertas del corte" valor={(r?.total_ofertas ?? 0).toLocaleString("es-CO")} nota="meta: 10.000 únicas" />
        <Kpi etiqueta="Con algún software" valor={r && r.total_ofertas ? `${Math.round((100 * r.ofertas_con_software) / r.total_ofertas)} %` : "—"} />
        <Kpi etiqueta="Histórico" valor={datos.total_historico.toLocaleString("es-CO")} nota={`${datos.cortes.length} cortes`} />
      </div>
      {r && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="tarjeta">
            <h2 className="mb-2 font-titulo text-lg font-extrabold uppercase text-marina">Top 10 softwares (% de ofertas)</h2>
            <Barras datos={r.top_softwares.map((x) => ({ etiqueta: x.software, valor: x.porcentaje }))} sufijo=" %" />
          </div>
          <div className="tarjeta space-y-4">
            <div><h2 className="mb-2 font-titulo text-lg font-extrabold uppercase text-marina">Por carrera</h2><Barras datos={aBarras(r.por_carrera)} /></div>
            <div><h2 className="mb-2 font-titulo text-lg font-extrabold uppercase text-marina">Por fuente</h2><Barras datos={aBarras(r.por_fuente)} /></div>
            <div><h2 className="mb-2 font-titulo text-lg font-extrabold uppercase text-marina">Práctica vs. empleo</h2><Barras datos={aBarras(r.por_tipo_oferta)} /></div>
          </div>
        </div>
      )}
      {admin && datos.ultimas_corridas.length > 0 && (
        <div className="tarjeta mt-4">
          <h2 className="mb-2 font-titulo text-lg font-extrabold uppercase text-marina">Últimas corridas</h2>
          <table className="tabla">
            <thead><tr><th>Ejecución</th><th>Corte</th><th>Estado</th><th>Guardadas</th><th>Por</th></tr></thead>
            <tbody>
              {datos.ultimas_corridas.map((e) => (
                <tr key={e.id_ejecucion}>
                  <td><Link className="text-institucional font-semibold underline" to={`/ejecuciones/${e.id_ejecucion}`}>{e.id_ejecucion}</Link></td>
                  <td>{e.semestre} · {e.corte}</td>
                  <td><EstadoChip estado={e.estado} /></td>
                  <td>{e.ofertas_guardadas}</td>
                  <td className="text-xs">{e.ejecutado_por}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
        </>
      )}
    </div>
  );
}
