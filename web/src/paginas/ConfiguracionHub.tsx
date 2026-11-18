import { NavLink, Navigate, useParams } from "react-router-dom";
import { useEsAdmin } from "../main";
import { Titulo } from "../componentes/ui";
import { ConfiguracionGeneral } from "./Configuracion";
import Catalogo from "./Catalogo";
import Terminos from "./Terminos";
import NoCatalogados from "./NoCatalogados";
import CatalogoGc from "./CatalogoGc";

const SECCIONES: { id: string; path: string; label: string; adminOnly?: boolean }[] = [
  { id: "", path: "/configuracion", label: "General" },
  { id: "catalogo", path: "/configuracion/catalogo", label: "Catálogo y sinónimos" },
  { id: "terminos", path: "/configuracion/terminos", label: "Términos de búsqueda" },
  { id: "no-catalogados", path: "/configuracion/no-catalogados", label: "No catalogados" },
  { id: "habilidades-idiomas", path: "/configuracion/habilidades-idiomas", label: "Habilidades e idiomas", adminOnly: true },
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
      <nav className="flex flex-wrap gap-2 border-b border-niebla pb-2" aria-label="Secciones de configuración">
        {tabs.map((t) => (
          <NavLink
            key={t.id || "general"}
            to={t.path}
            end={t.id === ""}
            className={({ isActive }) =>
              `rounded px-3 py-1 text-sm font-semibold ${isActive ? "bg-institucional text-white" : "bg-niebla/40 text-texto"}`
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