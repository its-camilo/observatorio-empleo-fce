import { useState } from "react";

type Props = {
  etiqueta: string;
  items: string[];
  onChange: (items: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
};

export default function EditorChips({ etiqueta, items, onChange, disabled, placeholder }: Props) {
  const [entrada, setEntrada] = useState("");

  const agregar = () => {
    const t = entrada.trim();
    if (!t || items.includes(t)) {
      setEntrada("");
      return;
    }
    onChange([...items, t]);
    setEntrada("");
  };

  return (
    <div>
      <span className="etiqueta">{etiqueta}</span>
      <div className="mb-2 flex flex-wrap gap-1">
        {items.map((t) => (
          <span key={t} className="chip inline-flex items-center gap-1">
            {t}
            {!disabled && (
              <button
                type="button"
                className="text-marina hover:text-red-700"
                aria-label={`Quitar ${t}`}
                onClick={() => onChange(items.filter((x) => x !== t))}
              >
                ×
              </button>
            )}
          </span>
        ))}
        {items.length === 0 && <span className="text-sm text-texto-suave">Ninguno</span>}
      </div>
      {!disabled && (
        <div className="flex gap-2">
          <input
            className="campo flex-1"
            value={entrada}
            placeholder={placeholder || "Escriba y pulse Agregar"}
            onChange={(e) => setEntrada(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                agregar();
              }
            }}
          />
          <button type="button" className="btn-sec shrink-0" onClick={agregar}>
            Agregar
          </button>
        </div>
      )}
    </div>
  );
}