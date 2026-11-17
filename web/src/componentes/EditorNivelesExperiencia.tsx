import { useMemo, useState } from "react";
import { api } from "../api";
import { Aviso } from "./ui";

export const NIVELES_EXPERIENCIA = [
  "Practicante",
  "Sin experiencia / Junior",
  "Intermedio",
  "Senior",
  "Directivo",
  "No especificado",
] as const;

type Modo = "todos" | "algunos";

type ValorNiveles = { modo: Modo; niveles: string[] };

function normalizarValor(raw: unknown): ValorNiveles {
  if (raw && typeof raw === "object" && "modo" in raw) {
    const o = raw as { modo?: string; niveles?: string[] };
    const modo: Modo = o.modo === "todos" ? "todos" : "algunos";
    const niveles = (o.niveles || []).filter((x) => NIVELES_EXPERIENCIA.includes(x as (typeof NIVELES_EXPERIENCIA)[number]));
    if (modo === "todos") {
      return { modo: "todos", niveles: [...NIVELES_EXPERIENCIA] };
    }
    return { modo: "algunos", niveles };
  }
  return { modo: "todos", niveles: [...NIVELES_EXPERIENCIA] };
}

export default function EditorNivelesExperiencia({
  descripcion,
  valorInicial,
  admin,
  alGuardar,
}: {
  descripcion: string;
  valorInicial: unknown;
  admin: boolean;
  alGuardar: () => void;
}) {
  const base = useMemo(() => normalizarValor(valorInicial), [valorInicial]);
  const [modo, setModo] = useState<Modo>(base.modo);
  const [niveles, setNiveles] = useState<string[]>(base.modo === "algunos" ? base.niveles : []);
  const [msg, setMsg] = useState<{ tipo: "ok" | "error"; t: string } | null>(null);

  const toggle = (n: string) => {
    setNiveles((prev) => (prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n]));
  };

  const guardar = async () => {
    if (modo === "algunos" && niveles.length === 0) {
      setMsg({ tipo: "error", t: "Elija al menos un nivel o use la opción «todos»." });
      return;
    }
    const payload: ValorNiveles =
      modo === "todos"
        ? { modo: "todos", niveles: [...NIVELES_EXPERIENCIA] }
        : { modo: "algunos", niveles: [...niveles] };
    try {
      await api.put("/config/niveles_experiencia", { valor: payload });
      setMsg({ tipo: "ok", t: "Guardado. Las nuevas corridas usarán esta preferencia al prepararse." });
      alGuardar();
    } catch (e) {
      setMsg({ tipo: "error", t: (e as Error).message });
    }
  };

  return (
    <details className="tarjeta" open>
      <summary className="cursor-pointer">
        <b>Niveles de experiencia</b> <span className="text-sm text-texto-suave">— {descripcion}</span>
      </summary>
      <fieldset className="mt-3 space-y-2" disabled={!admin}>
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="radio"
            name="modo-niveles"
            checked={modo === "todos"}
            onChange={() => setModo("todos")}
          />
          <span>Buscar ofertas con todos los niveles de experiencia</span>
        </label>
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="radio"
            name="modo-niveles"
            checked={modo === "algunos"}
            onChange={() => {
              setModo("algunos");
              if (niveles.length === 0) {
                setNiveles(["Practicante", "Sin experiencia / Junior"]);
              }
            }}
          />
          <span>Solo con algunos niveles</span>
        </label>
        {modo === "algunos" && (
          <div className="ml-6 grid gap-1 sm:grid-cols-2">
            {NIVELES_EXPERIENCIA.map((n) => (
              <label key={n} className="flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" checked={niveles.includes(n)} onChange={() => toggle(n)} />
                {n}
              </label>
            ))}
          </div>
        )}
      </fieldset>
      {msg && <Aviso tipo={msg.tipo}>{msg.t}</Aviso>}
      {admin && (
        <button className="btn mt-2" type="button" onClick={guardar}>
          Guardar
        </button>
      )}
    </details>
  );
}