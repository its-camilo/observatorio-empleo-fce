import React, { createContext, useContext, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import "./index.css";
import { guardarSesion, leerSesion, Sesion } from "./api";
import Login from "./paginas/Login";
import Dashboard from "./paginas/Dashboard";
import LanzarCorrida from "./paginas/LanzarCorrida";
import Ejecuciones from "./paginas/Ejecuciones";
import Ofertas from "./paginas/Ofertas";
import Rankings from "./paginas/Rankings";
import Catalogo from "./paginas/Catalogo";
import Terminos from "./paginas/Terminos";
import NoCatalogados from "./paginas/NoCatalogados";
import Validacion from "./paginas/Validacion";
import Usuarios from "./paginas/Usuarios";
import Cursos from "./paginas/Cursos";
import Configuracion from "./paginas/Configuracion";
import TokensMcp from "./paginas/TokensMcp";

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

function Marco() {
  const { sesion, setSesion } = useSesion();
  const navegar = useNavigate();
  const [abierto, setAbierto] = useState(false);
  if (!sesion) return <Navigate to="/login" replace />;
  const salir = () => {
    setSesion(null);
    navegar("/login");
  };
  return (
    <div className="min-h-screen md:flex">
      <aside className={`${abierto ? "block" : "hidden"} w-full bg-tinta text-slate-100 md:block md:w-60 md:shrink-0`}>
        <div className="px-4 py-4">
          <div className="text-xs uppercase tracking-widest text-unal">UIFCE · UNAL</div>
          <div className="font-semibold">Observatorio de Empleo FCE</div>
        </div>
        <nav className="px-2 pb-4">
          {MENU.filter((m) => !m.admin || sesion.usuario.rol === "admin").map((m) => (
            <NavLink key={m.a} to={m.a} end={m.a === "/"} onClick={() => setAbierto(false)}
              className={({ isActive }) => `block rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-unal-oscuro text-white" : "text-slate-300 hover:bg-slate-700"}`}>
              {m.texto}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-700 px-4 py-3 text-xs text-slate-400">
          <div className="truncate">{sesion.usuario.email}</div>
          <div>{sesion.usuario.rol === "admin" ? "Administrador" : "Usuario"}</div>
          <button className="mt-2 underline" onClick={salir}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-6">
        <button className="btn-sec mb-3 md:hidden" onClick={() => setAbierto(!abierto)}>Menú</button>
        <Outlet />
      </main>
    </div>
  );
}

function SoloAdmin({ children }: { children: React.ReactNode }) {
  return useEsAdmin() ? <>{children}</> : <p className="text-sm text-slate-600">Solo los administradores pueden ver esta página.</p>;
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
