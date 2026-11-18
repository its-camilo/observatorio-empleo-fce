import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Aviso, semestreActual } from "./ui";
import type { Ejecucion } from "../paginas/Ejecuciones";
import { PanelProgreso, Reporte } from "../paginas/Ejecuciones";

type Props = {
  /** Muestra progreso/reporte de la corrida activa bajo el formulario (página dedicada antigua). */
  mostrarCorridaActiva?: boolean;
};

export default function FormularioLanzarCorrida({ mostrarCorridaActiva = false }: Props) {
  const [semestre, setSemestre] = useState(semestreActual());
  const [corte, setCorte] = useState("inicio");
  const [modo, setModo] = useState("completa");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [actual, setActual] = useState<Ejecucion | null>(null);

  useEffect(() => {
    if (!mostrarCorridaActiva) return;
    api
      .get<Ejecucion[]>("/corridas")
      .then((l) => {
        const activa = l.find((e) => ["en_cola", "en_curso"].includes(e.estado));
        if (activa) api.get<Ejecucion>(`/corridas/${activa.id_ejecucion}`).then(setActual);
      })
      .catch(() => {});
  }, [mostrarCorridaActiva]);

  useEffect(() => {
    if (!mostrarCorridaActiva || !actual || !["en_cola", "en_curso"].includes(actual.estado)) return;
    const t = setInterval(
      () => api.get<Ejecucion>(`/corridas/${actual.id_ejecucion}`).then(setActual).catch(() => {}),
      15000
    );
    return () => clearInterval(t);
  }, [actual, mostrarCorridaActiva]);

  const lanzar = async () => {
    if (!confirm(`¿Lanzar una corrida ${modo} para ${semestre} · ${corte}? Puede tardar varias horas.`)) return;
    setEnviando(true);
    setError(null);
    try {
      const e = await api.post<Ejecucion>("/corridas", { semestre, corte, modo });
      const det = await api.get<Ejecucion>(`/corridas/${e.id_ejecucion}`);
      if (mostrarCorridaActiva) setActual(det);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  const enMarcha = actual && ["en_cola", "en_curso"].includes(actual.estado);

  return (
    <>
      <p className="mb-3 text-sm text-texto-suave">
        La corrida se ejecuta en GitHub Actions: busca ofertas en LinkedIn, Indeed y Computrabajo (últimos 30 días), limpia,
        elimina duplicados, clasifica por carrera, detecta softwares y guarda todo en la base. El tope de descarga por corrida
        lo define `objetivo_ofertas_corrida` en Configuración; el reparto por fuente y carrera se edita allí.
        Si no llega a la meta, puede lanzarse una mini corrida. Puede tardar varias horas; puede cerrar esta página.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="etiqueta">Semestre</label>
          <input className="campo w-28" value={semestre} onChange={(e) => setSemestre(e.target.value)} placeholder="2026-II" />
        </div>
        <div>
          <label className="etiqueta">Corte</label>
          <select className="campo" value={corte} onChange={(e) => setCorte(e.target.value)}>
            <option value="inicio">Inicio</option>
            <option value="mitad">Mitad</option>
            <option value="final">Final</option>
          </select>
        </div>
        <div>
          <label className="etiqueta">Modo</label>
          <select className="campo" value={modo} onChange={(e) => setModo(e.target.value)}>
            <option value="completa">Completa</option>
            <option value="prueba">Prueba (pocas ofertas, minutos)</option>
          </select>
        </div>
        <button className="btn" type="button" disabled={enviando || !!enMarcha} onClick={lanzar}>
          {enviando ? "Enviando…" : "Lanzar"}
        </button>
      </div>
      {enMarcha && (
        <p className="mt-2 text-xs text-texto-suave">Hay una corrida en marcha; espere a que termine para lanzar otra.</p>
      )}
      {error && (
        <div className="mt-3">
          <Aviso tipo="error">{error}</Aviso>
        </div>
      )}
      {mostrarCorridaActiva && actual && (
        <>
          <div className="mt-4 text-sm">
            Corrida{" "}
            <Link className="font-semibold text-institucional underline" to={`/corridas/${actual.id_ejecucion}`}>
              {actual.id_ejecucion}
            </Link>
          </div>
          {actual.progreso && <PanelProgreso p={actual.progreso} />}
          {!enMarcha && <Reporte e={actual} />}
        </>
      )}
    </>
  );
}