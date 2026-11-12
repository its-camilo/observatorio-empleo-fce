import { useMemo, useState } from "react";
import { api } from "../api";
import { Aviso } from "./ui";

const ETIQUETAS_FUENTE: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  computrabajo: "Computrabajo",
};

type Props = {
  clave: "distribucion_fuentes" | "distribucion_carreras";
  titulo: string;
  descripcion: string;
  claves: string[];
  valores: Record<string, number>;
  admin: boolean;
  alGuardar: () => void;
};

export default function EditorDistribucion({ clave, titulo, descripcion, claves, valores, admin, alGuardar }: Props) {
  const inicial = useMemo(() => {
    const o: Record<string, string> = {};
    for (const k of claves) {
      o[k] = String(valores[k] ?? 0);
    }
    return o;
  }, [claves, valores]);

  const [campos, setCampos] = useState(inicial);
  const [msg, setMsg] = useState<{ tipo: "ok" | "error"; t: string } | null>(null);

  const suma = useMemo(
    () => claves.reduce((a, k) => a + (Number.parseFloat(campos[k] || "0") || 0), 0),
    [campos, claves],
  );
  const sumaOk = Math.abs(suma - 100) <= 0.05;

  const guardar = async () => {
    try {
      const valor: Record<string, number> = {};
      for (const k of claves) {
        valor[k] = Math.max(0, Number.parseFloat(campos[k] || "0") || 0);
      }
      await api.put(`/config/${clave}`, { valor });
      setMsg({ tipo: "ok", t: "Guardado. Aplica desde la próxima corrida." });
      alGuardar();
    } catch (e) {
      setMsg({ tipo: "error", t: (e as Error).message });
    }
  };

  const normalizar = async () => {
    try {
      const valor: Record<string, number> = {};
      for (const k of claves) {
        valor[k] = Math.max(0, Number.parseFloat(campos[k] || "0") || 0);
      }
      const res = await api.post<{ valor: Record<string, number> }>(
        `/config/distribucion/normalizar?clave=${clave}`,
        { valor },
      );
      const next: Record<string, string> = {};
      for (const k of claves) {
        next[k] = String(res.valor[k] ?? 0);
      }
      setCampos(next);
      setMsg({ tipo: "ok", t: "Porcentajes normalizados y guardados." });
      alGuardar();
    } catch (e) {
      setMsg({ tipo: "error", t: (e as Error).message });
    }
  };

  return (
    <div className="tarjeta space-y-3">
      <h2 className="titulo-seccion text-base md:text-lg">{titulo}</h2>
      <p className="text-sm text-texto-suave">{descripcion}</p>
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
        {claves.map((k) => (
          <label key={k} className="block">
            <span className="etiqueta">{ETIQUETAS_FUENTE[k] || k}</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min={0}
                max={100}
                step={0.1}
                className="campo"
                disabled={!admin}
                value={campos[k] ?? "0"}
                onChange={(e) => setCampos({ ...campos, [k]: e.target.value })}
              />
              <span className="text-sm font-semibold text-marina">%</span>
            </div>
          </label>
        ))}
      </div>
      <p className={`text-sm font-semibold ${sumaOk ? "text-marina" : "text-red-700"}`}>
        Suma: {suma.toFixed(2)} % {sumaOk ? "(válida)" : "— debe ser 100 %"}
      </p>
      {msg && <Aviso tipo={msg.tipo}>{msg.t}</Aviso>}
      {admin && (
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn" onClick={guardar} disabled={!sumaOk}>
            Guardar
          </button>
          <button type="button" className="btn-sec" onClick={normalizar}>
            Normalizar a 100 %
          </button>
        </div>
      )}
    </div>
  );
}
