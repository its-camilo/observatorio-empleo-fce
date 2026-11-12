/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        institucional: "#4574B9",
        marina: "#042361",
        acento: "#44D3FE",
        superficie: "#FEFEFE",
        "texto-suave": "#525C76",
        niebla: "#AFC6E4",
        crema: "#EAE9CB",
        grafito: "#5B5B5B",
        destacado: "#F4CB18",
      },
      fontFamily: {
        titulo: ["Montserrat", "system-ui", "sans-serif"],
        subtitulo: ["Ubuntu", "system-ui", "sans-serif"],
        cuerpo: ["Fira Sans", "system-ui", "sans-serif"],
        pie: ['"Fira Sans Condensed"', "Fira Sans", "system-ui", "sans-serif"],
      },
      borderRadius: {
        tarjeta: "2.5rem",
        bloque: "1.5rem",
        boton: "999px",
      },
      boxShadow: {
        suave: "0 8px 30px rgba(4, 35, 97, 0.12)",
      },
      maxWidth: {
        contenedor: "1280px",
      },
    },
  },
  plugins: [],
};
