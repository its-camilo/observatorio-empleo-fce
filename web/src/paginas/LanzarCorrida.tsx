import { Navigate } from "react-router-dom";

/** Ruta legada: redirige al apartado unificado Corridas. */
export default function LanzarCorrida() {
  return <Navigate to="/corridas" replace />;
}