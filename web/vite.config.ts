import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api y /mcp se envían a la API local (uvicorn en el puerto 8000).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000", "/mcp": "http://localhost:8000" } },
});
