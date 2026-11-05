# Observatorio de Empleo FCE

Aplicativo de la **Unidad de Informática de la Facultad de Ciencias Económicas (UIFCE) – Universidad Nacional de Colombia**
para el Observatorio Tecnológico del área de Gestión del Conocimiento (GC).

Recoge ofertas de empleo y práctica para **Administración de Empresas, Contaduría Pública y Economía** (LinkedIn, Indeed,
Google Jobs y Computrabajo), detecta los **softwares** que piden con un catálogo editable, clasifica por carrera, elimina
duplicados y deja una base limpia lista para **Power BI**, con rankings por carrera y comparación entre cortes y semestres.

- **Front + API** (React + FastAPI) en Vercel o en un servidor propio (Docker).
- **Base de datos** Postgres (Neon u otro). SQLite solo para pruebas locales.
- **Corridas** en GitHub Actions (lanzadas desde el aplicativo o desde el MCP), o en un computador con un solo comando.
- **Servidor MCP remoto** en `/mcp`: lectura pública para cualquier asistente de IA; herramientas de administración con token.

| Documento | Para quién |
|---|---|
| [docs/manual-usuario.md](docs/manual-usuario.md) | Monitores de GC: configurar, lanzar, revisar, validar, actualizar Power BI |
| [docs/documentacion-tecnica.md](docs/documentacion-tecnica.md) | Desarrollo: arquitectura, RF → archivos, cómo agregar fuentes, riesgos (LinkedIn), MCP |
| [powerbi/README.md](powerbi/README.md) | Conectar Power BI a las URL CSV |

## Estructura

```
observatorio/            Paquete Python
  scraper/               Una parte por fuente: linkedin.py, jobspy_fuentes.py (Indeed, Google), computrabajo.py, cursos.py, http.py
  pipeline/              limpieza.py, dedup.py, software.py, clasificacion.py, llm.py, habilidades.py, no_catalogados.py, procesar.py
  db/                    modelos.py (tablas), sesion.py, semilla.py
  datos/                 catalogo.json y terminos.json (carga inicial; luego se editan en el aplicativo)
  api/                   FastAPI: main.py, seguridad.py, rutas/
  orquestador.py         preparar → extraer (por fragmentos) → consolidar; reanudable
  corridas.py            lanzar corridas en GitHub Actions y calcular el progreso
  analisis.py            rankings (RF-12) y comparación (RF-13)
  exportar.py            CSV / Excel (RF-11) y tablas para Power BI (RF-14)
  mcp_servidor.py        servidor MCP remoto (/mcp)
  parametros.py          parámetros editables por defecto (RF-01)
  run.py                 línea de comandos
api/index.py             entrada de Vercel
web/                     front (React + Vite + TypeScript + Tailwind)
alembic/                 migraciones de la base
.github/workflows/       corrida.yml (scraping) y pruebas.yml
powerbi/                 consultas Power Query y guía
tests/                   pruebas (pytest)
```

## Variables de entorno

Copie `.env.example` a `.env` (nunca suba `.env`). En Vercel y GitHub se configuran como variables/secretos.

| Variable | Dónde | Para qué |
|---|---|---|
| `DATABASE_URL` | Vercel, GitHub (secreto), servidor | Postgres. Ej. Neon: `postgresql://...neon.tech/observatorio?sslmode=require`. Vacío = SQLite local |
| `JWT_SECRET` | Vercel, servidor | Firma de las sesiones (cadena larga aleatoria) |
| `GOOGLE_CLIENT_ID` | Vercel, servidor | Cliente OAuth de Google (`745533004054-gub9dlpg373msnfq05gnhev4jjethhp9.apps.googleusercontent.com`) |
| `GITHUB_TOKEN` | Vercel, servidor | Token *fine-grained* con permiso **Actions: Read and write** sobre el repositorio, para lanzar corridas |
| `GITHUB_REPO` | Vercel, servidor | `its-camilo/observatorio-empleo-fce` |
| `OPENROUTER_API_KEY` | GitHub (secreto) | Opcional. Clasifica solo las ofertas dudosas con modelos gratuitos (`:free`) |
| `OPENROUTER_MODELS` | GitHub (variable) | Opcional. Lista de modelos separada por comas (se prueban en orden) |
| `PROXIES` | GitHub (secreto) | Opcional. Proxies separados por coma, rotan por petición |
| `ADMINS_INICIALES` | opcional | Por defecto `uniic_bog@unal.edu.co,clagosm@unal.edu.co` |
| `CSV_TOKEN` | opcional | Protege las URL CSV de Power BI (`?token=`) |
| `MCP_LIMITE_POR_MINUTO` | opcional | Límite de solicitudes MCP por IP (60 por defecto) |
| `GITHUB_WORKFLOW`, `GITHUB_REF` | opcional | `corrida.yml`, `main` |

## Puesta en marcha local

Requisitos: Python 3.11+, Node 20+.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env          # complete JWT_SECRET; para probar sin Google ponga AUTH_DEV_MODE=true
python -m observatorio.run migrar          # crea/actualiza tablas (Postgres) — con SQLite se crean solas
python -m observatorio.run semilla         # catálogo, términos, parámetros y administradores iniciales
uvicorn observatorio.api.main:app --reload --port 8000
cd web && npm install && npm run dev       # http://localhost:5173 (envía /api y /mcp al puerto 8000)
pytest                                     # pruebas
```

### Correr una corrida desde un computador (CLI)

Útil si la IP del servidor o de GitHub está bloqueada por alguna fuente:

```bash
python -m observatorio.run --semestre 2026-II --corte inicio            # corrida completa (varias horas)
python -m observatorio.run --semestre 2026-II --corte inicio --prueba   # prueba: 3 términos, 1 ciudad, 20 ofertas por consulta
python -m observatorio.run --semestre 2026-II --corte inicio --run-id ID  # retomar una corrida interrumpida sin duplicar
python -m observatorio.run exportar --semestre 2026-II --corte inicio --salida observatorio.xlsx
```

Escribe en la base indicada por `DATABASE_URL` y aparece en el aplicativo igual que una corrida de GitHub Actions.

## GitHub Actions

1. *Settings → Secrets and variables → Actions*: secretos `DATABASE_URL` (obligatorio), `OPENROUTER_API_KEY` y `PROXIES` (opcionales);
   variable `OPENROUTER_MODELS` (opcional).
2. El workflow **Corrida del Observatorio** (`.github/workflows/corrida.yml`) recibe `semestre`, `corte`, `run_id`, `modo`.
   Se lanza desde el aplicativo, desde el MCP (admins) o a mano en *Actions → Run workflow*.
3. Trabajos: `preparar` → `extraer` (matriz por fuente y fragmento, hasta 6 en paralelo, ~5,5 h cada uno) + `cursos` →
   `consolidar` (limpieza, duplicados, clasificación, mini corrida si no se llega a 10 000, reporte y Excel como artefacto).
4. Si algo falla, vuelva a lanzar con el **mismo `run_id`**: continúa donde quedó.

Repositorio público ⇒ minutos de Actions gratuitos sin límite mensual. No se guardan datos en el repositorio.

## Vercel (front + API + MCP)

1. Importe el repositorio en Vercel (framework: *Other*). `vercel.json` ya define build del front (`web/dist`),
   la función Python `api/index.py` y las reescrituras de `/api/*` y `/mcp`.
2. Variables: `DATABASE_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GITHUB_TOKEN`, `GITHUB_REPO` (y opcionales).
3. En Google Cloud Console → credenciales del cliente OAuth → **Orígenes de JavaScript autorizados**: agregue el dominio de Vercel
   (y `http://localhost:5173` para desarrollo).
4. Antes del primer uso aplique migraciones contra Neon desde un computador: `python -m observatorio.run migrar`
   (o lance una corrida: el primer paso de Actions también migra).

Vercel no ejecuta las corridas (duran horas); solo las lanza en GitHub Actions y muestra el progreso.

## Servidor propio (migración desde Vercel/Neon)

```bash
cp .env.example .env                         # JWT_SECRET, GOOGLE_CLIENT_ID, GITHUB_TOKEN, GITHUB_REPO...
docker compose up -d --build                 # Postgres + aplicativo en http://SERVIDOR:8000 (front, /api, /mcp)
```

Para llevar los datos de Neon al servidor: `pg_dump "$NEON_URL" | docker compose exec -T db psql -U observatorio observatorio`.
Luego cambie el secreto `DATABASE_URL` de GitHub Actions para que apunte al servidor (debe ser accesible desde internet,
o ejecute las corridas con la CLI dentro del servidor: `docker compose run --rm app python -m observatorio.run --semestre ... --corte ...`).
Ponga el servidor detrás de HTTPS (Nginx/Caddy) y agregue el dominio en los orígenes autorizados de Google.

## Servidor MCP (para asistentes de IA)

URL: `https://SU-DOMINIO/mcp` (transporte *Streamable HTTP*). Sin autenticación expone solo herramientas de **lectura**:
`listar_cortes`, `valores_filtro`, `buscar_ofertas_empleo`, `ver_oferta`, `ranking_software`, `comparar_cortes`,
`resumen_corte`, `listar_catalogo`, `listar_ejecuciones`, `listar_cursos_tendencia`. No expone usuarios, validaciones ni configuración.

Los administradores generan un **token personal** en el aplicativo (*Tokens MCP*); con la cabecera
`Authorization: Bearer obs_...` aparecen además `lanzar_corrida(semestre, corte, modo)` y `estado_corrida(run_id)`.

Sin token (solo lectura):

```json
{ "mcpServers": { "observatorio-fce": { "url": "https://SU-DOMINIO/mcp" } } }
```

Con token de administrador:

```json
{ "mcpServers": { "observatorio-fce": { "url": "https://SU-DOMINIO/mcp",
  "headers": { "Authorization": "Bearer obs_SU_TOKEN" } } } }
```

Instrucciones para Claude, ChatGPT y Cursor en [docs/documentacion-tecnica.md](docs/documentacion-tecnica.md#servidor-mcp).

## Licencia

MIT. Datos: solo información pública de ofertas; no se guardan datos personales ni salarios.
