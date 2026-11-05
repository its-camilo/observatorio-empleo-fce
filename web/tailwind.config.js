/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        unal: { DEFAULT: "#94B43B", oscuro: "#5F7A1F" },
        tinta: "#1F2937",
      },
    },
  },
  plugins: [],
};
