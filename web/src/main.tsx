import React, { Suspense, createContext, lazy, useContext, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import "./index.css";
import { guardarSesion, leerSesion, Sesion } from "./api";
import { Cargando } from "./componentes/ui";
import Login from "./paginas/Login";
import LogoUnal from "./componentes/LogoUnal";

const Dashboard = lazy(() => import("./paginas/Dashboard"));
const LanzarCorrida = lazy(() => import("./paginas/LanzarCorrida"));
const Ejecuciones = lazy(() => import("./paginas/Ejecuciones"));
const Ofertas = lazy(() => import("./paginas/Ofertas"));
const Rankings = lazy(() => import("./paginas/Rankings"));
const Catalogo = lazy(() => import("./paginas/Catalogo"));
const Terminos = lazy(() => import("./paginas/Terminos"));
const NoCatalogados = lazy(() => import("./paginas/NoCatalogados"));
const Validacion = lazy(() => import("./paginas/Validacion"));
const Usuarios = lazy(() => import("./paginas/Usuarios"));
const Cursos = lazy(() => import("./paginas/Cursos"));
const Configuracion = lazy(() => import("./paginas/Configuracion"));
const TokensMcp = lazy(() => import("./paginas/TokensMcp"));

type Ctx = { sesion: Sesion | null; setSesion: (s: Sesion | null) => void };
const SesionCtx = createContext<Ctx>({ sesion: null, setSesion: () => {} });
export const useSesion = () => useContext(SesionCtx);
export const useEsAdmin = () => useContext(SesionCtx).sesion?.usuario.rol === "admin";

const MENU: { a: string; texto: string; admin?: boolean }[] = [
  { a: "/", texto: "Inicio" },
  { a: "/lanzar", texto: "Lanzar corrida", admin: true },
  { a: "/ejecuciones", texto: "Ejecuciones y reportes", admin: true },
  { a: "/ofertas", texto: "Ofertas" },
  { a: "/rankings", texto: "Rankings y comparación" },
  { a: "/catalogo", texto: "Catálogo y sinónimos" },
  { a: "/terminos", texto: "Términos de búsqueda" },
  { a: "/no-catalogados", texto: "No catalogados" },
  { a: "/validacion", texto: "Validación" },
  { a: "/cursos", texto: "Cursos en tendencia" },
  { a: "/configuracion", texto: "Configuración" },
  { a: "/usuarios", texto: "Usuarios", admin: true },
  { a: "/tokens-mcp", texto: "Tokens MCP" },
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
  return (
    <div className="shell-institucional">
      <div className="shell-card md:flex-row">
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside
            className={`${
              abierto ? "block" : "hidden"
            } shrink-0 bg-institucional text-white md:flex md:w-64 md:flex-col`}
          >
            <div className="border-b border-white/15 px-5 py-5">
              <div className="font-titulo text-xs font-extrabold uppercase tracking-widest text-acento">UIFCE · 2026</div>
              <div className="mt-1 font-titulo text-sm font-extrabold uppercase leading-tight text-white">
                Observatorio de Empleo FCE
              </div>
            </div>
            <nav className="max-h-[50vh] overflow-y-auto px-2 py-3 md:max-h-none md:flex-1">
              {enlaces.map((m) => (
                <NavLink
                  key={m.a}
                  to={m.a}
                  end={m.a === "/"}
                  onClick={() => setAbierto(false)}
                  className={({ isActive }) => `nav-link ${isActive ? "nav-link-activo" : ""}`}
                >
                  {m.texto}
                </NavLink>
              ))}
            </nav>
            <div className="border-t border-white/15 px-4 py-4 text-xs text-white/80">
              <div className="truncate font-semibold">{sesion.usuario.email}</div>
              <div className="text-acento">{sesion.usuario.rol === "admin" ? "Administrador" : "Usuario"}</div>
              <button type="button" className="mt-2 font-semibold underline decoration-acento underline-offset-2" onClick={salir}>
                Cerrar sesión
              </button>
            </div>
          </aside>
          <main className="min-w-0 flex-1 overflow-auto p-5 md:p-8 md:pl-6">
            <div className="mb-4 flex items-center justify-between gap-2 md:hidden">
              <span className="font-titulo text-xs font-bold uppercase text-marina">Menú</span>
              <button type="button" className="btn-sec text-xs" onClick={() => setAbierto(!abierto)}>
                {abierto ? "Cerrar" : "Abrir"}
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
            <Route path="/lanzar" element={<SoloAdmin><LanzarCorrida /></SoloAdmin>} />
            <Route path="/ejecuciones" element={<SoloAdmin><Ejecuciones /></SoloAdmin>} />
            <Route path="/ejecuciones/:id" element={<SoloAdmin><Ejecuciones /></SoloAdmin>} />
            <Route path="/ofertas" element={<Ofertas />} />
            <Route path="/rankings" element={<Rankings />} />
            <Route path="/catalogo" element={<Catalogo />} />
            <Route path="/terminos" element={<Terminos />} />
            <Route path="/no-catalogados" element={<NoCatalogados />} />
            <Route path="/validacion" element={<Validacion />} />
            <Route path="/cursos" element={<Cursos />} />
            <Route path="/configuracion" element={<Configuracion />} />
            <Route path="/usuarios" element={<SoloAdmin><Usuarios /></SoloAdmin>} />
            <Route path="/tokens-mcp" element={<TokensMcp />} />
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
