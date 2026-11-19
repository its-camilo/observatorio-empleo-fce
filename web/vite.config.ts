import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api y /mcp se envían a la API local (uvicorn en el puerto 8000).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000", "/mcp": "http://localhost:8000" } },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react-router") || id.includes("node_modules/react-dom") || id.includes("node_modules/react/")) {
            return "react-vendor";
          }
          if (id.includes("node_modules/swr")) {
            return "swr";
          }
        },
      },
    },
  },
});
