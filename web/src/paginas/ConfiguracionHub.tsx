import { NavLink, Navigate, useParams } from "react-router-dom";
import { useEsAdmin } from "../main";
import { Titulo } from "../componentes/ui";
import { ConfiguracionGeneral } from "./Configuracion";
import Catalogo from "./Catalogo";
import Terminos from "./Terminos";
import NoCatalogados from "./NoCatalogados";
import CatalogoGc from "./CatalogoGc";
import Validacion from "./Validacion";
import Usuarios from "./Usuarios";
import TokensMcp from "./TokensMcp";

const SECCIONES: { id: string; path: string; label: string; adminOnly?: boolean }[] = [
  { id: "", path: "/configuracion", label: "General" },
  { id: "catalogo", path: "/configuracion/catalogo", label: "Catálogo y sinónimos" },
  { id: "terminos", path: "/configuracion/terminos", label: "Términos de búsqueda" },
  { id: "no-catalogados", path: "/configuracion/no-catalogados", label: "No catalogados" },
  { id: "habilidades-idiomas", path: "/configuracion/habilidades-idiomas", label: "Habilidades e idiomas", adminOnly: true },
  { id: "validacion", path: "/configuracion/validacion", label: "Validación" },
  { id: "usuarios", path: "/configuracion/usuarios", label: "Usuarios", adminOnly: true },
  { id: "tokens-mcp", path: "/configuracion/tokens-mcp", label: "Tokens MCP" },
];

function Contenido({ seccion, admin }: { seccion: string; admin: boolean }) {
  switch (seccion) {
    case "":
      return <ConfiguracionGeneral embebido />;
    case "catalogo":
      return <Catalogo embebido />;
    case "terminos":
      return <Terminos embebido />;
    case "no-catalogados":
      return <NoCatalogados embebido />;
    case "habilidades-idiomas":
      if (!admin) {
        return <p className="text-sm text-texto-suave">Solo los administradores pueden editar el catálogo de habilidades e idiomas.</p>;
      }
      return <CatalogoGc embebido />;
    case "validacion":
      return <Validacion embebido />;
    case "usuarios":
      if (!admin) {
        return <p className="text-sm text-texto-suave">Solo los administradores pueden gestionar usuarios.</p>;
      }
      return <Usuarios embebido />;
    case "tokens-mcp":
      return <TokensMcp embebido />;
    default:
      return <Navigate to="/configuracion" replace />;
  }
}

export default function ConfiguracionHub() {
  const { seccion } = useParams<{ seccion?: string }>();
  const admin = useEsAdmin();
  const activa = seccion ?? "";
  const tabs = SECCIONES.filter((t) => !t.adminOnly || admin);

  return (
    <div className="space-y-4">
      <Titulo>Configuración</Titulo>
      <nav
        className="-mx-1 flex gap-2 overflow-x-auto border-b border-niebla px-1 pb-2"
        aria-label="Secciones de configuración"
      >
        {tabs.map((t) => (
          <NavLink
            key={t.id || "general"}
            to={t.path}
            end={t.id === ""}
            className={({ isActive }) =>
              `shrink-0 rounded px-3 py-1 text-sm font-semibold ${isActive ? "bg-institucional text-white" : "bg-niebla/40 text-texto"}`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Contenido seccion={activa} admin={admin} />
    </div>
  );
}