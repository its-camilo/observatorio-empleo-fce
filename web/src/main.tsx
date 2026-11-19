import React, { Suspense, createContext, lazy, useContext, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import "@fontsource/fira-sans/400.css";
import "@fontsource/fira-sans/600.css";
import "@fontsource/fira-sans-condensed/400.css";
import "@fontsource/montserrat/700.css";
import "@fontsource/montserrat/800.css";
import "@fontsource/ubuntu/700.css";
import "./index.css";
import { guardarSesion, leerSesion, Sesion } from "./api";
import { Cargando } from "./componentes/ui";
import Login from "./paginas/Login";
import LogoUnal from "./componentes/LogoUnal";
import { BarraLateral } from "./componentes/BarraLateral";
import { MenuMovil } from "./componentes/MenuMovil";

const Dashboard = lazy(() => import("./paginas/Dashboard"));
const Corridas = lazy(() => import("./paginas/Corridas"));
const LanzarCorrida = lazy(() => import("./paginas/LanzarCorrida"));
const Ejecuciones = lazy(() => import("./paginas/Ejecuciones"));
const Ofertas = lazy(() => import("./paginas/Ofertas"));
const Rankings = lazy(() => import("./paginas/Rankings"));
const ConfiguracionHub = lazy(() => import("./paginas/ConfiguracionHub"));

type Ctx = { sesion: Sesion | null; setSesion: (s: Sesion | null) => void };
const SesionCtx = createContext<Ctx>({ sesion: null, setSesion: () => {} });
export const useSesion = () => useContext(SesionCtx);
export const useEsAdmin = () => useContext(SesionCtx).sesion?.usuario.rol === "admin";

const MENU: { a: string; texto: string; admin?: boolean }[] = [
  { a: "/", texto: "Inicio" },
  { a: "/corridas", texto: "Corridas", admin: true },
  { a: "/ofertas", texto: "Ofertas" },
  { a: "/rankings", texto: "Rankings y comparación" },
  { a: "/configuracion", texto: "Configuración" },
];

function PieInstitucional() {
  return (
    <footer className="pie-institucional">
      <div className="block space-y-0.5 text-center md:text-left">
        <span className="block">Facultad de Ciencias Económicas</span>
        <span className="block">Unidad de Informática (UIFCE)</span>
        <span className="block">Universidad Nacional de Colombia — Sede Bogotá</span>
      </div>
      <a
        href="https://www.unal.edu.co"
        target="_blank"
        rel="noreferrer"
        className="marca-unal mt-3 md:mt-0 md:ml-6 md:shrink-0"
        aria-label="Universidad Nacional de Colombia (sitio web)"
      >
        <LogoUnal className="object-center md:object-right" />
      </a>
    </footer>
  );
}

function Marco() {
  const { sesion, setSesion } = useSesion();
  const navegar = useNavigate();
  const [abierto, setAbierto] = useState(false);
  if (!sesion) return <Navigate to="/login" replace />;
  const salir = () => {
    setSesion(null);
    navegar("/login");
  };
  const enlaces = MENU.filter((m) => !m.admin || sesion.usuario.rol === "admin");
  const cerrarMenu = () => setAbierto(false);
  return (
    <div className="shell-institucional">
      <MenuMovil abierto={abierto} onCerrar={cerrarMenu}>
        <BarraLateral enlaces={enlaces} sesion={sesion} onCerrarMovil={cerrarMenu} onSalir={salir} />
      </MenuMovil>
      <div className="shell-card md:flex-row">
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className="hidden w-64 shrink-0 flex-col overflow-y-auto bg-institucional text-white md:flex md:relative">
            <BarraLateral enlaces={enlaces} sesion={sesion} onSalir={salir} />
          </aside>
          <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-3 sm:p-5 md:p-8 md:pl-6">
            <div className="mb-4 flex items-center justify-between gap-2 border-b border-niebla pb-3 md:hidden">
              <span className="font-titulo text-xs font-bold uppercase text-marina">Observatorio FCE</span>
              <button
                type="button"
                className="btn-sec text-xs"
                aria-expanded={abierto}
                onClick={() => setAbierto(!abierto)}
              >
                {abierto ? "✕ Cerrar" : "☰ Menú"}
              </button>
            </div>
            <Suspense fallback={<Cargando />}>
              <Outlet />
            </Suspense>
          </main>
        </div>
      </div>
      <PieInstitucional />
    </div>
  );
}

function SoloAdmin({ children }: { children: React.ReactNode }) {
  return useEsAdmin() ? (
    <>{children}</>
  ) : (
    <p className="text-sm text-texto-suave">Solo los administradores pueden ver esta página.</p>
  );
}

function App() {
  const [sesion, setSesionEstado] = useState<Sesion | null>(leerSesion());
  const setSesion = (s: Sesion | null) => {
    guardarSesion(s);
    setSesionEstado(s);
  };
  return (
    <SesionCtx.Provider value={{ sesion, setSesion }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Marco />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/corridas" element={<SoloAdmin><Corridas /></SoloAdmin>} />
            <Route path="/corridas/:id" element={<SoloAdmin><Corridas /></SoloAdmin>} />
            <Route path="/lanzar" element={<SoloAdmin><LanzarCorrida /></SoloAdmin>} />
            <Route path="/ejecuciones" element={<SoloAdmin><Ejecuciones /></SoloAdmin>} />
            <Route path="/ejecuciones/:id" element={<SoloAdmin><Ejecuciones /></SoloAdmin>} />
            <Route path="/ofertas" element={<Ofertas />} />
            <Route path="/rankings" element={<Rankings />} />
            <Route path="/configuracion" element={<ConfiguracionHub />} />
            <Route path="/configuracion/:seccion" element={<ConfiguracionHub />} />
            <Route path="/catalogo" element={<Navigate to="/configuracion/catalogo" replace />} />
            <Route path="/terminos" element={<Navigate to="/configuracion/terminos" replace />} />
            <Route path="/no-catalogados" element={<Navigate to="/configuracion/no-catalogados" replace />} />
            <Route path="/catalogo-gc" element={<Navigate to="/configuracion/habilidades-idiomas" replace />} />
            <Route path="/validacion" element={<Navigate to="/configuracion/validacion" replace />} />
            <Route path="/cursos" element={<Navigate to="/rankings?tab=cursos" replace />} />
            <Route path="/temas-recomendados" element={<Navigate to="/rankings?tab=temas" replace />} />
            <Route path="/usuarios" element={<Navigate to="/configuracion/usuarios" replace />} />
            <Route path="/tokens-mcp" element={<Navigate to="/configuracion/tokens-mcp" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SesionCtx.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
