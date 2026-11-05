import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Aviso, Titulo, semestreActual } from "../componentes/ui";
import { Ejecucion, PanelProgreso, Reporte } from "./Ejecuciones";

export default function LanzarCorrida() {
  const [semestre, setSemestre] = useState(semestreActual());
  const [corte, setCorte] = useState("inicio");
  const [modo, setModo] = useState("completa");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [actual, setActual] = useState<Ejecucion | null>(null);

  // Si hay una corrida en marcha, mostrarla
  useEffect(() => {
    api.get<Ejecucion[]>("/corridas").then((l) => {
      const activa = l.find((e) => ["en_cola", "en_curso"].includes(e.estado));
      if (activa) api.get<Ejecucion>(`/corridas/${activa.id_ejecucion}`).then(setActual);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!actual || !["en_cola", "en_curso"].includes(actual.estado)) return;
    const t = setInterval(() => api.get<Ejecucion>(`/corridas/${actual.id_ejecucion}`).then(setActual).catch(() => {}), 15000);
    return () => clearInterval(t);
  }, [actual]);

  const lanzar = async () => {
    if (!confirm(`¿Lanzar una corrida ${modo} para ${semestre} · ${corte}? Puede tardar varias horas.`)) return;
    setEnviando(true);
    setError(null);
    try {
      const e = await api.post<Ejecucion>("/corridas", { semestre, corte, modo });
      setActual(await api.get<Ejecucion>(`/corridas/${e.id_ejecucion}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  const enMarcha = actual && ["en_cola", "en_curso"].includes(actual.estado);
  return (
    <div className="space-y-4">
      <Titulo>Lanzar corrida</Titulo>
      <div className="tarjeta max-w-2xl">
        <p className="mb-3 text-sm text-slate-600">
          La corrida se ejecuta en GitHub Actions: busca ofertas en LinkedIn, Indeed, Google Jobs y Computrabajo (últimos 30 días), limpia,
          elimina duplicados, clasifica por carrera, detecta softwares y guarda todo en la base. Si no llega a la meta de ofertas, hace sola
          una mini corrida con términos más variados. Puede tardar varias horas; puede cerrar esta página.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div><label className="etiqueta">Semestre</label>
            <input className="campo w-28" value={semestre} onChange={(e) => setSemestre(e.target.value)} placeholder="2026-II" /></div>
          <div><label className="etiqueta">Corte</label>
            <select className="campo" value={corte} onChange={(e) => setCorte(e.target.value)}>
              <option value="inicio">Inicio</option><option value="mitad">Mitad</option><option value="final">Final</option>
            </select></div>
          <div><label className="etiqueta">Modo</label>
            <select className="campo" value={modo} onChange={(e) => setModo(e.target.value)}>
              <option value="completa">Completa</option><option value="prueba">Prueba (pocas ofertas, minutos)</option>
            </select></div>
          <button className="btn" disabled={enviando || !!enMarcha} onClick={lanzar}>{enviando ? "Enviando…" : "Lanzar"}</button>
        </div>
        {enMarcha && <p className="mt-2 text-xs text-slate-500">Hay una corrida en marcha; espere a que termine para lanzar otra.</p>}
        {error && <div className="mt-3"><Aviso tipo="error">{error}</Aviso></div>}
      </div>
      {actual && (
        <>
          <div className="text-sm">Corrida <Link className="text-unal-oscuro underline" to={`/ejecuciones/${actual.id_ejecucion}`}>{actual.id_ejecucion}</Link></div>
          {actual.progreso && <PanelProgreso p={actual.progreso} />}
          {!enMarcha && <Reporte e={actual} />}
        </>
      )}
    </div>
  );
}
