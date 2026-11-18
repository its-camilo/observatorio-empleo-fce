import { useParams } from "react-router-dom";
import FormularioLanzarCorrida from "../componentes/FormularioLanzarCorrida";
import { Titulo } from "../componentes/ui";
import { DetalleCorrida, ListaEjecuciones } from "./Ejecuciones";

export default function Corridas() {
  const { id } = useParams();
  if (id) return <DetalleCorrida id={id} />;
  return (
    <div className="space-y-4">
      <Titulo>Corridas</Titulo>
      <details className="tarjeta group">
        <summary className="cursor-pointer list-none font-semibold marker:content-none">
          <span className="text-institucional group-open:text-marina">Lanzar nueva corrida</span>
          <span className="ml-2 text-xs font-normal text-texto-suave">(clic para expandir)</span>
        </summary>
        <div className="mt-3 border-t border-niebla/60 pt-3">
          <FormularioLanzarCorrida />
        </div>
      </details>
      <ListaEjecuciones />
    </div>
  );
}