import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";

type Props = {
  abierto: boolean;
  onCerrar: () => void;
  children: ReactNode;
};

/** Menú móvil en portal (fuera de `.shell-card`) para que el panel quede por encima del backdrop en iOS Safari. */
export function MenuMovil({ abierto, onCerrar, children }: Props) {
  useEffect(() => {
    if (!abierto) return;
    const html = document.documentElement;
    const body = document.body;
    const prevHtmlOverflow = html.style.overflow;
    const prevBodyOverflow = body.style.overflow;
    html.classList.add("menu-movil-abierto");
    body.classList.add("menu-movil-abierto");
    return () => {
      html.classList.remove("menu-movil-abierto");
      body.classList.remove("menu-movil-abierto");
      html.style.overflow = prevHtmlOverflow;
      body.style.overflow = prevBodyOverflow;
    };
  }, [abierto]);

  if (!abierto) return null;

  return createPortal(
    <div className="menu-movil-capas md:hidden" role="presentation">
      <button
        type="button"
        className="menu-movil-backdrop fixed inset-0 z-[1200] cursor-default border-0 bg-marina/50 p-0"
        aria-label="Cerrar menú"
        onClick={onCerrar}
      />
      <aside
        className="menu-movil-panel fixed inset-y-0 left-0 z-[1210] flex w-[min(100%,16.5rem)] translate-x-0 flex-col overflow-y-auto overscroll-contain bg-institucional text-white shadow-2xl [transform:translate3d(0,0,0)]"
        data-testid="menu-movil-panel"
      >
        {children}
      </aside>
    </div>,
    document.body,
  );
}