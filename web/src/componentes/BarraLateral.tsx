import { NavLink } from "react-router-dom";
import type { Sesion } from "../api";
import { prefetchNav } from "../prefetchNav";

export type EnlaceMenu = { a: string; texto: string; admin?: boolean };

type Props = {
  enlaces: EnlaceMenu[];
  sesion: Sesion;
  onCerrarMovil?: () => void;
  onSalir: () => void;
};

export function BarraLateral({ enlaces, sesion, onCerrarMovil, onSalir }: Props) {
  return (
    <>
      <div className="border-b border-white/15 px-5 py-5">
        <div className="font-titulo text-xs font-extrabold uppercase tracking-widest text-acento">UIFCE · 2026</div>
        <div className="mt-1 font-titulo text-sm font-extrabold uppercase leading-tight text-white">
          Observatorio de Empleo FCE
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-3" data-testid="nav-lateral">
        {enlaces.map((m) => (
          <NavLink
            key={m.a}
            to={m.a}
            end={m.a === "/"}
            onClick={() => onCerrarMovil?.()}
            onMouseEnter={() => prefetchNav(m.a)}
            onFocus={() => prefetchNav(m.a)}
            className={({ isActive }) => `nav-link ${isActive ? "nav-link-activo" : ""}`}
          >
            {m.texto}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-white/15 px-4 py-4 text-xs text-white/80">
        <div className="truncate font-semibold">{sesion.usuario.email}</div>
        <div className="text-acento">{sesion.usuario.rol === "admin" ? "Administrador" : "Usuario"}</div>
        <button
          type="button"
          className="mt-2 font-semibold underline decoration-acento underline-offset-2"
          onClick={() => {
            onCerrarMovil?.();
            onSalir();
          }}
        >
          Cerrar sesión
        </button>
      </div>
    </>
  );
}