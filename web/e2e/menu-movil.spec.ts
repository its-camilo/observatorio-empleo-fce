import { expect, test } from "@playwright/test";
import path from "node:path";

const ENLACES_USUARIO = [
  { texto: "Inicio", ruta: "/" },
  { texto: "Ofertas", ruta: "/ofertas" },
  { texto: "Rankings y comparación", ruta: "/rankings" },
  { texto: "Validación", ruta: "/validacion" },
  { texto: "Cursos en tendencia", ruta: "/cursos" },
  { texto: "Temas para dictar", ruta: "/temas-recomendados" },
  { texto: "Configuración", ruta: "/configuracion" },
  { texto: "Tokens MCP", ruta: "/tokens-mcp" },
];

const RESUMEN_DASHBOARD = {
  cortes: [],
  ultimo_corte: null,
  resumen: null,
  total_historico: 0,
  ultimas_corridas: [],
};

const FILTROS_OFERTAS = {
  semestres: [],
  cortes: [],
  fuentes: [],
  ciudades: [],
  tipos_oferta: [],
  niveles: [],
  modalidades: [],
  carreras: [],
  softwares: [],
};

function cuerpoApi(url: string): unknown {
  if (url.includes("/auth/config")) {
    return { google_client_id: "", dominio: "unal.edu.co", modo_dev: true };
  }
  if (url.includes("/dashboard")) return RESUMEN_DASHBOARD;
  if (url.includes("/ofertas/filtros")) return FILTROS_OFERTAS;
  if (url.match(/\/ofertas(\?|$)/)) return { total: 0, pagina: 1, paginas: 1, items: [] };
  if (url.match(/\/validacion\/muestras\/[^/]+$/)) {
    return {
      estadisticas: { total: 0, validados: 0, correctos: 0, precision: null, meta: 90, cumple_meta: false },
      items: [],
    };
  }
  if (url.match(/\/validacion\/muestras(\?|$)/)) return [];
  if (url.match(/\/analisis\/cortes(\?|$)/)) return [];
  if (url.includes("/analisis/")) return { ranking: [], grupos: [] };
  if (url.includes("/config")) return [];
  if (url.includes("/catalogo")) return [];
  if (url.includes("/terminos")) return [];
  if (url.includes("/no-catalogados")) return [];
  return [];
}

async function prepararSesion(page: import("@playwright/test").Page) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(cuerpoApi(url)),
    });
  });
  await page.addInitScript(() => {
    localStorage.setItem(
      "observatorio_sesion",
      JSON.stringify({
        token: "token-e2e",
        usuario: { id: 1, email: "monitor@unal.edu.co", rol: "usuario", estado: "activo" },
      }),
    );
  });
}

test.describe("menú móvil", () => {
  test("enlaces navegan y cierran el drawer; backdrop cierra; scroll bloqueado", async ({ page }, testInfo) => {
    test.setTimeout(90_000);
    await prepararSesion(page);
    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login/);

    const botonMenu = page.getByRole("button", { name: /Menú/ });
    await botonMenu.click();

    const panel = page.getByTestId("menu-movil-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("menu-movil-panel")).toBeVisible();

    const shotPath = path.join(testInfo.outputDir, "menu-movil-abierto.png");
    await page.screenshot({ path: shotPath, fullPage: true });

    await expect(page.locator("html")).toHaveClass(/menu-movil-abierto/);

    const backdrop = page.locator(".menu-movil-backdrop");
    await backdrop.click({ position: { x: 350, y: 400 } });
    await expect(panel).toBeHidden();
    await expect(botonMenu).toHaveAttribute("aria-expanded", "false");

    for (const { texto, ruta } of ENLACES_USUARIO) {
      if (await panel.isVisible()) {
        await page.getByRole("button", { name: "✕ Cerrar" }).click();
        await expect(panel).toBeHidden();
      }
      await page.getByRole("button", { name: "☰ Menú" }).click();
      await expect(panel).toBeVisible();
      await page.getByTestId("menu-movil-panel").getByRole("link", { name: texto }).click();
      await expect(page).toHaveURL(new RegExp(`${ruta.replace("/", "\\/")}(\\?.*)?$`));
      await expect(panel).toBeHidden();
      await expect(page.getByRole("button", { name: "☰ Menú" })).toHaveAttribute("aria-expanded", "false");
    }
  });
});