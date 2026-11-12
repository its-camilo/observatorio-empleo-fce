import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, Sesion } from "../api";
import { useSesion } from "../main";
import { Aviso } from "../componentes/ui";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; hd?: string }) => void;
          renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
        };
      };
    };
  }
}

type ConfigAuth = { google_client_id: string; dominio: string; modo_dev: boolean };

export default function Login() {
  const { sesion, setSesion } = useSesion();
  const navegar = useNavigate();
  const boton = useRef<HTMLDivElement>(null);
  const [cfg, setCfg] = useState<ConfigAuth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [correoDev, setCorreoDev] = useState("");

  useEffect(() => {
    api.get<ConfigAuth>("/auth/config").then(setCfg).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!cfg?.google_client_id) return;
    let intentos = 0;
    const iniciar = () => {
      if (!window.google || !boton.current) {
        if (intentos++ < 50) setTimeout(iniciar, 200);
        return;
      }
      window.google.accounts.id.initialize({
        client_id: cfg.google_client_id,
        hd: cfg.dominio,
        callback: async (r) => {
          try {
            setError(null);
            setSesion(await api.post<Sesion>("/auth/google", { credential: r.credential }));
            navegar("/");
          } catch (e) {
            setError((e as Error).message);
          }
        },
      });
      window.google.accounts.id.renderButton(boton.current, { theme: "outline", size: "large", text: "signin_with", locale: "es" });
    };
    iniciar();
  }, [cfg, navegar, setSesion]);

  if (sesion) return <Navigate to="/" replace />;

  const ingresarDev = async () => {
    try {
      setSesion(await api.post<Sesion>("/auth/dev", { email: correoDev }));
      navegar("/");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="shell-institucional flex min-h-screen flex-col items-center justify-center">
      <div className="shell-card w-full max-w-lg p-8 text-center md:p-12">
        <div className="font-titulo text-sm font-extrabold uppercase tracking-widest text-acento">UIFCE · UNAL</div>
        <h1 className="mt-2 font-titulo text-2xl font-extrabold uppercase leading-tight text-marina md:text-3xl">
          Observatorio de Empleo FCE
        </h1>
        <p className="subtitulo-acento mt-2">Gestión del conocimiento</p>
        <p className="mx-auto mt-4 max-w-sm text-sm leading-relaxed text-texto-suave">
          Ingrese con su cuenta institucional @{cfg?.dominio || "unal.edu.co"}. Las cuentas nuevas quedan pendientes hasta que un
          administrador las apruebe.
        </p>
        <div className="mt-6 flex justify-center" ref={boton} />
        {error && (
          <div className="mt-4 text-left">
            <Aviso tipo="error">{error}</Aviso>
          </div>
        )}
        {cfg?.modo_dev && (
          <div className="mt-8 border-t border-niebla pt-6 text-left">
            <Aviso tipo="alerta">Modo de desarrollo activo (AUTH_DEV_MODE). No use esto en producción.</Aviso>
            <div className="flex flex-wrap gap-2">
              <input className="campo min-w-0 flex-1" placeholder="correo@unal.edu.co" value={correoDev} onChange={(e) => setCorreoDev(e.target.value)} />
              <button type="button" className="btn" onClick={ingresarDev}>
                Entrar
              </button>
            </div>
          </div>
        )}
      </div>
      <footer className="mt-4 px-4 text-center font-pie text-sm italic text-white/90">
        Facultad de Ciencias Económicas · Unidad de Informática · Universidad Nacional de Colombia
      </footer>
    </div>
  );
}
