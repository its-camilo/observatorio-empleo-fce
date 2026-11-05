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
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="tarjeta w-full max-w-md text-center">
        <div className="text-xs uppercase tracking-widest text-unal-oscuro">Unidad de Informática · FCE · UNAL</div>
        <h1 className="mt-1 text-2xl font-semibold text-tinta">Observatorio de Empleo FCE</h1>
        <p className="mt-2 text-sm text-slate-600">
          Ingrese con su cuenta institucional @{cfg?.dominio || "unal.edu.co"}. Las cuentas nuevas quedan pendientes hasta que un
          administrador las apruebe.
        </p>
        <div className="mt-5 flex justify-center" ref={boton} />
        {error && <div className="mt-4 text-left"><Aviso tipo="error">{error}</Aviso></div>}
        {cfg?.modo_dev && (
          <div className="mt-6 border-t pt-4 text-left">
            <Aviso tipo="alerta">Modo de desarrollo activo (AUTH_DEV_MODE). No use esto en producción.</Aviso>
            <div className="flex gap-2">
              <input className="campo flex-1" placeholder="correo@unal.edu.co" value={correoDev} onChange={(e) => setCorreoDev(e.target.value)} />
              <button className="btn" onClick={ingresarDev}>Entrar</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
