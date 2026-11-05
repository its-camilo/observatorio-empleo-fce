import { useState } from "react";
import { descargar, qs } from "../api";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Filtros = {
  semestres: string[]; cortes: string[]; fuentes: string[]; ciudades: string[]; tipos_oferta: string[];
  niveles: string[]; modalidades: string[]; carreras: string[]; softwares: string[];
};
type Oferta = {
  id_oferta: string; fuente: string; url: string; fecha_publicacion: string | null; semestre: string; corte: string; cargo: string;
  empresa: string | null; ciudad: string; modalidad: string; tipo_oferta: string; nivel_experiencia: string; carrera: string;
  softwares: string[]; idiomas: string | null; descripcion?: string;
  detecciones?: { software: string; grupo: string; texto_encontrado: string }[];
};
type Pagina = { total: number; pagina: number; paginas: number; items: Oferta[] };

const VACIO = { semestre: "", corte: "", carrera: "", fuente: "", ciudad: "", software: "", tipo_oferta: "", nivel: "", modalidad: "", texto: "" };

function Select({ etiqueta, valor, opciones, onCambio }: { etiqueta: string; valor: string; opciones: string[]; onCambio: (v: string) => void }) {
  return (
    <div><label className="etiqueta">{etiqueta}</label>
      <select className="campo w-full" value={valor} onChange={(e) => onCambio(e.target.value)}>
        <option value="">Todos</option>
        {opciones.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

export default function Ofertas() {
  const { datos: filtros } = useDatos<Filtros>("/ofertas/filtros");
  const [f, setF] = useState(VACIO);
  const [aplicados, setAplicados] = useState(VACIO);
  const [pagina, setPagina] = useState(1);
  const [abierta, setAbierta] = useState<Oferta | null>(null);
  const { datos, error, cargando } = useDatos<Pagina>(`/ofertas${qs({ ...aplicados, pagina, tamano: 25 })}`, [aplicados, pagina]);
  const { datos: detalle } = useDatos<Oferta>(abierta ? `/ofertas/${encodeURIComponent(abierta.id_oferta)}` : null, [abierta]);
  const cambiar = (k: keyof typeof VACIO) => (v: string) => setF({ ...f, [k]: v });
  const [errDesc, setErrDesc] = useState<string | null>(null);

  const exportar = async (tipo: "excel" | "csv") => {
    setErrDesc(null);
    try {
      const sufijo = `${aplicados.semestre || "todo"}_${aplicados.corte || "todos"}`;
      if (tipo === "excel") await descargar(`/exportar/excel${qs({ semestre: aplicados.semestre, corte: aplicados.corte })}`, `observatorio_${sufijo}.xlsx`);
      else await descargar(`/exportar/csv${qs({ tabla: "ofertas", semestre: aplicados.semestre, corte: aplicados.corte })}`, `ofertas_${sufijo}.csv`);
    } catch (e) {
      setErrDesc((e as Error).message);
    }
  };

  return (
    <div>
      <Titulo extra={<div className="flex gap-2">
        <button className="btn-sec" onClick={() => exportar("csv")}>Descargar CSV</button>
        <button className="btn-sec" onClick={() => exportar("excel")}>Descargar Excel</button>
      </div>}>Ofertas</Titulo>
      {errDesc && <Aviso tipo="error">{errDesc}</Aviso>}
      <div className="tarjeta mb-4">
        {!filtros ? <Cargando /> : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            <Select etiqueta="Semestre" valor={f.semestre} opciones={filtros.semestres} onCambio={cambiar("semestre")} />
            <Select etiqueta="Corte" valor={f.corte} opciones={filtros.cortes} onCambio={cambiar("corte")} />
            <Select etiqueta="Carrera" valor={f.carrera} opciones={filtros.carreras} onCambio={cambiar("carrera")} />
            <Select etiqueta="Fuente" valor={f.fuente} opciones={filtros.fuentes} onCambio={cambiar("fuente")} />
            <Select etiqueta="Ciudad" valor={f.ciudad} opciones={filtros.ciudades} onCambio={cambiar("ciudad")} />
            <Select etiqueta="Software" valor={f.software} opciones={filtros.softwares} onCambio={cambiar("software")} />
            <Select etiqueta="Tipo de oferta" valor={f.tipo_oferta} opciones={filtros.tipos_oferta} onCambio={cambiar("tipo_oferta")} />
            <Select etiqueta="Nivel" valor={f.nivel} opciones={filtros.niveles} onCambio={cambiar("nivel")} />
            <Select etiqueta="Modalidad" valor={f.modalidad} opciones={filtros.modalidades} onCambio={cambiar("modalidad")} />
            <div><label className="etiqueta">Texto</label><input className="campo w-full" value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} placeholder="cargo, empresa…" /></div>
          </div>
        )}
        <div className="mt-3 flex gap-2">
          <button className="btn" onClick={() => { setAplicados(f); setPagina(1); }}>Filtrar</button>
          <button className="btn-sec" onClick={() => { setF(VACIO); setAplicados(VACIO); setPagina(1); }}>Limpiar</button>
        </div>
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {datos && (
        <div className="tarjeta overflow-x-auto">
          <div className="mb-2 text-sm text-slate-600">{datos.total.toLocaleString("es-CO")} ofertas {cargando && "· actualizando…"}</div>
          <table className="tabla">
            <thead><tr><th>Cargo</th><th>Empresa</th><th>Ciudad</th><th>Carrera</th><th>Tipo / nivel</th><th>Softwares</th><th>Fuente</th><th>Publicada</th></tr></thead>
            <tbody>
              {datos.items.map((o) => (
                <tr key={o.id_oferta} className="cursor-pointer hover:bg-slate-50" onClick={() => setAbierta(o)}>
                  <td className="font-medium">{o.cargo}</td><td>{o.empresa}</td><td>{o.ciudad}<div className="text-xs text-slate-500">{o.modalidad}</div></td>
                  <td className="text-xs">{o.carrera}</td><td className="text-xs">{o.tipo_oferta}<br />{o.nivel_experiencia}</td>
                  <td>{o.softwares.map((s) => <span key={s} className="chip">{s}</span>)}</td>
                  <td><a className="text-unal-oscuro underline" href={o.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{o.fuente}</a></td>
                  <td className="whitespace-nowrap text-xs">{o.fecha_publicacion}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex items-center gap-2 text-sm">
            <button className="btn-sec" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
            <span>Página {datos.pagina} de {Math.max(1, datos.paginas)}</span>
            <button className="btn-sec" disabled={pagina >= datos.paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
          </div>
        </div>
      )}
      {abierta && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4" onClick={() => setAbierta(null)}>
          <div className="tarjeta max-h-[85vh] w-full max-w-3xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-2">
              <div><h2 className="text-lg font-semibold">{abierta.cargo}</h2>
                <div className="text-sm text-slate-600">{abierta.empresa} · {abierta.ciudad} · {abierta.fuente} · {abierta.id_oferta}</div></div>
              <button className="btn-sec" onClick={() => setAbierta(null)}>Cerrar</button>
            </div>
            <a className="text-sm text-unal-oscuro underline" href={abierta.url} target="_blank" rel="noreferrer">Abrir oferta original</a>
            {!detalle ? <Cargando /> : (
              <>
                <div className="mt-3 text-sm">
                  <b>Softwares detectados:</b>{" "}
                  {detalle.detecciones?.length ? detalle.detecciones.map((d) => <span key={d.software} className="chip" title={d.grupo}>{d.software} ← “{d.texto_encontrado}”</span>) : "ninguno"}
                </div>
                {detalle.idiomas && <div className="text-sm"><b>Idiomas:</b> {detalle.idiomas}</div>}
                <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-slate-700">{detalle.descripcion}</pre>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
