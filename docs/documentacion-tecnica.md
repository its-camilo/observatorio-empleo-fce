# Documentación técnica — Observatorio de Empleo FCE

Para el área de Desarrollo de la UIFCE. Explica cómo está armado el aplicativo, dónde vive cada requerimiento,
cómo agregar una fuente, qué hacer cuando una página cambia, los riesgos (en especial LinkedIn) y el servidor MCP.

## 1. Arquitectura

```
                 ┌──────────────────────── Vercel (o servidor propio con Docker) ─────────────────────────┐
 Navegador ──▶   │  web/ (React)  ──/api──▶  FastAPI (observatorio/api)  ──▶ Postgres (Neon o propio)    │
 Asistente IA ─▶ │                 ──/mcp──▶  Servidor MCP (observatorio/mcp_servidor.py)                 │
                 └───────────────┬────────────────────────────────────────────────────────────────────────┘
                                 │ workflow_dispatch (GITHUB_TOKEN)
                                 ▼
                 GitHub Actions: corrida.yml  ── escribe directo en Postgres (secreto DATABASE_URL)
                   preparar → extraer[fuente × fragmento] + cursos → consolidar
                 (o la CLI local: python -m observatorio.run --semestre ... --corte ...)
```

- **Fuente de verdad**: la base Postgres. Power BI lee las URL CSV de la API; Excel/CSV se descargan del aplicativo
  o del artefacto de cada corrida en Actions.
- **Corridas**: nunca en Vercel (límite de 60 s). La API registra la ejecución “en cola” y dispara el workflow con el
  mismo `run_id`; el progreso se calcula desde la tabla `particiones`, igual para Actions y para la CLI.

### Flujo de una corrida (`observatorio/orquestador.py`)

1. **preparar**: crea/retoma la fila de `ejecuciones` y las `particiones` (fuente × término × ciudad) a partir de los
   términos activos tipo *principal*, las ciudades y las fuentes activas de `config`. Emite la matriz de trabajos.
2. **extraer** (un trabajo por fuente y fragmento; las particiones se reparten por `id % fragmentos`): cada extractor
   devuelve ofertas crudas que se guardan en `ofertas_crudas` cada 25 ofertas. Los identificadores ya conocidos (en esta
   corrida o en el historial) no se vuelven a pedir. Un error en una consulta queda en `particiones.error` en lenguaje
   sencillo y se sigue con la siguiente; si la fuente bloquea 3 veces seguidas, el fragmento se detiene (lo pendiente se
   retoma al relanzar con el mismo `run_id`).
3. **cursos** (RF-19): Coursera, edX y Platzi → tabla `cursos`.
4. **consolidar** (`pipeline/procesar.py`, por bloques de 1 500): limpieza → filtro de Colombia y ventana de 30 días →
   duplicados en el bloque → duplicados contra el historial → clasificación (reglas, LLM para dudosas, respaldo) →
   se descartan no relevantes → softwares, idiomas, habilidades → guardado → no catalogados. Si el corte tiene menos
   ofertas que la meta (10 000), **mini corrida** con los términos *ampliado* (presupuesto de tiempo configurable) y
   se procesa de nuevo. Al final, el reporte (RF-15) queda en `ejecuciones`.

Reanudación: `particiones` hechas no se repiten; `ofertas_crudas` tiene restricción única `(id_ejecucion, fuente, id_fuente)`
y una marca `procesada`. Relanzar con el mismo `run_id` nunca duplica.

## 2. Requerimientos → archivos

| RF | Qué | Dónde |
|---|---|---|
| RF-01 Configuración | Parámetros editables sin código (tabla `config`), términos, catálogo | `parametros.py`, `db/semilla.py`, `datos/*.json`, `api/rutas/configuracion.py`, páginas Configuración/Términos/Catálogo |
| RF-02 LinkedIn | Búsqueda JobSpy + endpoint público de invitados; detalle con reintentos | `scraper/linkedin.py`, `scraper/http.py` |
| RF-03 Otras fuentes | Indeed (JobSpy), Computrabajo (requests + BeautifulSoup) | `scraper/jobspy_fuentes.py`, `scraper/computrabajo.py` |
| RF-04 Campos | Diccionario de datos sec. 9 | `db/modelos.py` (`Oferta`, `OfertaSoftware`, `Catalogo`, `Ejecucion`), `pipeline/limpieza.py` |
| RF-05 Softwares | Catálogo + sinónimos, palabra completa, reglas para ambiguos | `pipeline/software.py`, tablas `catalogo`/`sinonimos` |
| RF-06 Carrera | Reglas + LLM gratuito para dudosas; descarta no relevantes; hasta 5 carreras | `pipeline/clasificacion.py`, `pipeline/llm.py` |
| RF-07 Limpieza | Textos, ciudades, fechas, empresas; quita correos, teléfonos y salarios | `texto.py`, `pipeline/limpieza.py` |
| RF-08 Duplicados | Empresa + cargo + ciudad normalizados, fechas < 7 días, gana la descripción más larga; dentro y entre ejecuciones y fuentes | `pipeline/dedup.py`, `pipeline/procesar.py` |
| RF-09 Corte | Semestre, corte, fecha en cada ejecución y oferta | `orquestador.py` |
| RF-10 Historial | Base acumulada; nada se borra | Postgres |
| RF-11 Exportación | CSV y Excel (descarga) + artefacto Excel por corrida | `exportar.py`, `api/rutas/datos.py`, `corrida.yml` |
| RF-12 Ranking | Por carrera y corte, % y variación | `analisis.py` |
| RF-13 Comparación | Subió / bajó / igual / nuevo / desapareció + advertencias de comparabilidad | `analisis.py` |
| RF-14 Power BI | CSV públicos paginados + Power Query | `api/rutas/datos.py` (`/api/publico/*.csv`), `powerbi/` |
| RF-15 Reporte | Por fuente y carrera, duplicados, errores, duración | `orquestador.finalizar`, `run.imprimir_reporte`, página Ejecuciones |
| RF-16 Errores | Cada fuente/consulta independiente; mensajes sencillos | `scraper/http.explicar_error`, `orquestador.extraer` |
| RF-17 No catalogados | Términos frecuentes fuera del catálogo | `pipeline/no_catalogados.py`, página No catalogados |
| RF-18 Idiomas y blandas | Idioma + nivel; habilidades blandas | `pipeline/habilidades.py` |
| RF-19 Cursos | Coursera, edX, Platzi | `scraper/cursos.py`, tabla `cursos` |
| Aceptación 90 % | Muestra aleatoria y revisión de GC | `api/rutas/datos.py` (validación), página Validación |

## 3. Base de datos

Tablas del diccionario: `ofertas`, `oferta_software`, `catalogo` (+ `sinonimos`), `ejecuciones`. Otras: `terminos_busqueda`,
`usuarios`, `validaciones`, `no_catalogados`, `cursos`, `config`, `tokens_mcp` (solo hash SHA-256), y de trabajo:
`ofertas_crudas`, `particiones`, `llm_cache`.

- `ofertas.carrera` guarda una o varias carreras separadas por `; ` (la principal primero); `oferta_software.carrera` la copia.
  Para Power BI use `oferta_carrera.csv` (una fila por oferta y carrera).
- `id_oferta` = prefijo de la fuente + id de la fuente (`LI-`, `IN-`, `GO-`, `CT-`). Con `dedup.alcance = "corte"` se agrega
  `@semestre-corte` para permitir la misma oferta en varios cortes.
- Migraciones: `alembic/versions/`. Para un cambio de modelo: editar `db/modelos.py` →
  `alembic revision --autogenerate -m "descripcion"` → revisar → `python -m observatorio.run migrar`.
  **No cambie ni quite columnas existentes del diccionario**: Power BI depende de ellas. Agregue columnas al final.

## 4. Reglas de negocio

### Detección de softwares (RF-05)
- Cada sinónimo se busca como palabra completa, sin distinguir mayúsculas ni tildes; los espacios aceptan guion o nada
  (“Power BI” = “PowerBI” = “Power-BI”). Se reporta el texto tal como aparece.
- Opciones por sinónimo: **distingue mayúsculas** (`R`, `SAS`, `Word`, `Alegra`, `PBI`), **exige contexto** (alguna palabra de
  `catalogo.contexto` a ±120 caracteres) y **patrón de exclusión** (regex; p. ej. `S\.A\.S`, `R&D`, `excel in`).
- `SAS`: exige contexto estadístico y se excluye cuando va después de un nombre propio (“Contadores Asociados SAS”), “S.A.S.”, “ESP”.
- `R`: exige contexto (python, sql, stata, estadística, rstudio…) y excluye R&D, R.H., RRHH, (R), ®.
- El nombre de la empresa se borra del texto antes de buscar (Siigo S.A.S. publicando no cuenta como “Siigo”).
- Pruebe cambios en el aplicativo: Catálogo → *Probar detección*.

### Cargos operativos fuera del alcance

El observatorio prioriza ofertas de nivel analista/profesional o superior (no auxiliar/asistente administrativo de oficina).
Los patrones editables `exclusion_operativa_titulo` (tabla `config`) descartan el cargo **antes** de las reglas de carrera, para que
palabras amplias como `administrativ` no clasifiquen como Administración de Empresas un «Auxiliar Administrativo» encontrado en Computrabajo.
En bases ya pobladas: `python -m observatorio.run purga-reglas` (vista previa con conteos por motivo y ejemplos) y
`python -m observatorio.run purga-reglas --aplicar`. El alias `purga-operativa` ejecuta la misma lógica.

### Valor formativo (`requiere_software_o_habilidad`)

Con `config.requiere_software_o_habilidad = true` (por defecto), una oferta clasificada como relevante solo se guarda si
menciona software del catálogo (salvo Office genérico aislado) o una habilidad técnica cursable (`pipeline/valor_formativo.py`).
El LLM (`openrouter/free`) devuelve además `habilidades_tecnicas` y `tiene_habilidad_cursable`; si no hay LLM, aplican solo reglas y catálogo.

### Clasificación y relevancia (RF-06)
Puntaje por carrera = 3 × palabras fuertes del título + 2 × mención explícita de la carrera en la descripción +
mín(palabras débiles, 3) + 1 si el término de búsqueda es de esa carrera (`config.reglas_carrera`).
- Título con palabra específica de una carrera → relevante (principal = mayor puntaje; secundarias con palabra en el título o puntaje ≥ 3; máx. 5).
- Título en `exclusion_titulo` sin palabra específica (jefe/coordinador/gerente no cuentan) → no relevante.
- Sin señales → no relevante. Solo descripción/término → **dudosa** → LLM.
- Relevante por carrera pero sin software ni habilidad cursable → no se guarda (no cuenta para la meta).
- LLM (`pipeline/llm.py`): OpenRouter modelo fijo `openrouter/free`, ~12 req/min por defecto, reintentos 429, circuit breaker, caché por hash
  (1 000) y por corrida (600), 16 solicitudes/min, espera ante 429. Sin clave o sin cupo → **respaldo**: relevante si puntaje ≥ 3.
  El reporte muestra cuántas se clasificaron con LLM y cuántas por respaldo.

### Duplicados (RF-08)
Clave = empresa normalizada (sin S.A.S., Ltda, Colombia…) | cargo normalizado (sin marcas de género) | ciudad normalizada.
Duplicado si la clave coincide y las fechas difieren < 7 días (o falta alguna). Gana la descripción más larga; se unen los
términos de búsqueda. Empresas genéricas (“Importante empresa del sector”) añaden un hash del inicio de la descripción.
Alcance por defecto **global** (contra todo el historial); `dedup.alcance = "corte"` lo limita al mismo semestre y corte.

### Meta y mini corrida
Meta 10 000 ofertas únicas relevantes por corte (`config.meta_ofertas`). Si no se alcanza, la consolidación crea particiones
con los términos *ampliado* en LinkedIn, Indeed y Computrabajo con `mini_corrida.max_minutos` (240) y vuelve a procesar.
El reporte deja constancia si aun así no se llega.

## 5. Fuentes: cómo funcionan y qué hacer si cambian

| Fuente | Método | Archivo | Señales de que cambió |
|---|---|---|---|
| LinkedIn | JobSpy (búsqueda) + `jobs-guest/jobs/api/jobPosting/<id>` (detalle) | `scraper/linkedin.py` | ofertas sin descripción (`sin_detalle`), 0 tarjetas, HTTP 429/999 |
| Indeed | JobSpy `country_indeed="Colombia"` | `scraper/jobspy_fuentes.py` | 0 resultados en todas las consultas |
| Computrabajo | `co.computrabajo.com/trabajo-de-<término>[-en-<lugar>]?p=N` + página de detalle | `scraper/computrabajo.py` | `article.box_offer` vacío, descripción vacía |
| Coursera | GraphQL público del buscador | `scraper/cursos.py` | error de esquema GraphQL |
| edX | Índice público de búsqueda (Algolia) con la llave pública leída de edx.org (o `EDX_ALGOLIA_APP_ID/KEY`) | `scraper/cursos.py` | “no se encontró la llave pública” |
| Platzi | HTML de `platzi.com/buscar/?search=` | `scraper/cursos.py` | 0 cursos |

**Si una página cambia**: (1) mire el reporte de la ejecución (dice qué fuente y el tipo de error); (2) guarde el HTML actual
(`curl -A "Mozilla/5.0" URL > pagina.html`) y ajuste los selectores en el `parsear_*` del archivo de la fuente; (3) agregue un
caso a `tests/test_parsers.py` con HTML mínimo; (4) `pytest`; (5) relance la corrida con el mismo `run_id`. Mientras tanto,
desactive la fuente en Configuración → `fuentes` (las demás siguen).

### Agregar una fuente nueva
1. Cree `observatorio/scraper/<fuente>.py` con una clase que tenga `nombre` y `extraer(consulta, ya_existe)` que produzca
   `OfertaCrudaDatos` (ver `scraper/base.py`). Use `ClienteHttp` (pausas, reintentos, proxies). Nunca lea correos ni salarios.
2. Regístrela en `orquestador.crear_extractor`, `NOMBRES_FUENTE` y `pipeline/limpieza.PREFIJOS`.
3. Agréguela en `parametros.POR_DEFECTO["fuentes"]` y, si usa nombres de ciudad propios, en `ubicaciones`.
4. Pruebas de su lector en `tests/test_parsers.py`.

## 6. Riesgos y cumplimiento

### LinkedIn — términos de uso (riesgo principal)
- El Acuerdo de Usuario de LinkedIn **prohíbe la extracción automatizada** (scraping, bots) incluso sin iniciar sesión.
  Leer solo páginas públicas reduce el riesgo para cuentas (no se usa ninguna), pero **no lo elimina**: LinkedIn puede
  bloquear la IP (HTTP 429 o 999) temporal o permanentemente, y puede reclamar por el uso.
- La decisión de asumir este riesgo debe quedar por escrito por parte de la Unidad (sección 5.1 del documento).
- Mitigaciones implementadas: sin cuentas personales ni institucionales; solo información pública; pausas aleatorias
  (2,5–5 s por petición, más tras un 429); reintentos con espera exponencial y `Retry-After`; parada del fragmento tras
  3 bloqueos seguidos (sin insistir); no se vuelve a pedir el detalle de ofertas conocidas; límite por consulta
  (`max_por_particion`); proxies opcionales rotativos (`PROXIES`); modo local (CLI) para correr desde otra red;
  reanudación sin duplicar; varias fuentes para no depender solo de LinkedIn.
- Alternativa “oficial”: las API de LinkedIn para empleos (Job Posting/Talent Solutions) son solo para socios y no
  permiten consultar ofertas de terceros con fines de análisis; por eso no son viables para este caso.
- Riesgo operativo: el detalle exige ~1 petición por oferta; 10 000 ofertas ≈ 10 000+ peticiones, repartidas en 4
  trabajos paralelos de Actions (IPs distintas) durante varias horas.

### Otras fuentes
Indeed también restringe el scraping en sus términos; Computrabajo publica las ofertas abiertamente pero
aplica las mismas cautelas (pausas, sin login).

El objetivo de ofertas crudas por corrida se reparte con `config.distribucion_fuentes` y `config.distribucion_carreras` (porcentajes que suman 100).

### Datos personales y seguridad
- No se guardan nombres de reclutadores, correos ni teléfonos (se eliminan de la descripción) ni salarios.
- Secretos solo en variables de entorno / secretos de GitHub y Vercel. El repositorio es público: nunca suba `.env`.
- Tokens MCP: se muestran una sola vez y se guarda solo su hash; se pueden revocar.
- Inicio de sesión: Google Identity Services; el servidor verifica el ID token (firma, audiencia = `GOOGLE_CLIENT_ID`,
  correo verificado, dominio `@unal.edu.co`); sesión propia JWT (HS256, 12 h).

## 7. API

Documentación interactiva: `/api/docs`. Grupos principales:

- `/api/auth/*` (Google, sesión), `/api/usuarios` (admin), `/api/tokens-mcp` (cada usuario gestiona los suyos)
- `/api/catalogo`, `/api/sinonimos`, `/api/terminos`, `/api/no-catalogados`, `/api/config` (lectura: usuarios; escritura: admin)
- `/api/corridas` (solo admin: listar, ver progreso, lanzar), `/api/ofertas` (filtros, detalle), `/api/analisis/*` (cortes, resumen, ranking, comparar), `/api/dashboard`
- `/api/exportar/csv|excel` (sesión), `/api/publico/<tabla>.csv` (Power BI), `/api/validacion/*`, `/api/cursos`

Roles: **admin** (catálogo, términos, configuración, usuarios, lanzar corridas, validación manual, tokens MCP propios)
y **usuario** aprobado (**solo lectura y descarga**: ofertas, rankings, exportar, cursos; sin página ni API de corridas en vivo).
Tokens MCP de usuario: herramientas públicas de lectura; los de admin añaden `estado_corrida` y `lanzar_corrida`.
Las cuentas nuevas quedan **pendientes** hasta que un admin las aprueba.

## 8. Servidor MCP

`observatorio/mcp_servidor.py`, montado en `/mcp` dentro de la misma app FastAPI (funciona en Vercel y en Docker). Usa el
SDK oficial `mcp` (clase `MCPServer`) con transporte **Streamable HTTP sin estado** y respuestas JSON: cada solicitud crea
su propio gestor, sin sesiones en memoria, apto para funciones serverless. Solo remoto (no hay modo stdio).

- Herramientas públicas de solo lectura: `listar_cortes`, `valores_filtro`, `buscar_ofertas_empleo` (filtros carrera, semestre,
  corte, fuente, ciudad, software, texto, tipo; paginado, máx. 50 por página), `ver_oferta`, `ranking_software`,
  `comparar_cortes`, `resumen_corte`, `listar_catalogo`, `listar_ejecuciones`, `listar_cursos_tendencia`.
- Solo con token de un **admin** aprobado: `estado_corrida(run_id)` (progreso y reporte) y `lanzar_corrida(semestre, corte, modo)` (dispara GitHub Actions). El token hereda el rol de quien lo creó.
- Límites: 60 solicitudes/min por IP (`MCP_LIMITE_POR_MINUTO`; en Vercel cuenta por instancia, es un freno básico),
  descripciones recortadas a 2 000 caracteres, rankings ≤ 50, cursos ≤ 100, ejecuciones ≤ 50.
- Nunca expone `usuarios`, `validaciones`, `tokens_mcp`, `config` ni `llm_cache`.

### Token personal
Aplicativo → **Tokens MCP** → *Generar token* (se muestra una vez, formato `obs_...`). Se envía como
`Authorization: Bearer obs_...`. Revóquelo desde la misma página. Cualquier usuario aprobado puede crear tokens;
el token hereda su rol (lectura pública ampliada; solo admin añade corridas). Deja de servir si se revoca o el dueño pierde la aprobación.

### Conectarlo a asistentes

URL: `https://SU-DOMINIO/mcp`

- **Claude (web/escritorio, planes con conectores)**: *Configuración → Conectores → Agregar conector personalizado* → pegue la URL.
  Eso da acceso de solo lectura. Para las herramientas de admin con cabecera, use Claude Desktop con `mcp-remote`:
  ```json
  { "mcpServers": { "observatorio-fce": { "command": "npx",
      "args": ["-y", "mcp-remote", "https://SU-DOMINIO/mcp", "--header", "Authorization:Bearer ${OBS_TOKEN}"],
      "env": { "OBS_TOKEN": "obs_SU_TOKEN" } } } }
  ```
- **Claude Code**: `claude mcp add --transport http observatorio-fce https://SU-DOMINIO/mcp`
  (admin: agregue `--header "Authorization: Bearer obs_SU_TOKEN"`).
- **ChatGPT** (modo desarrollador / conectores personalizados, según el plan): *Configuración → Conectores → Crear* →
  URL `https://SU-DOMINIO/mcp`, autenticación **Ninguna** (solo lectura). ChatGPT no permite cabeceras fijas, por lo que las
  herramientas de admin se usan desde Claude, Cursor u otro cliente que sí las permita.
- **Cursor**: `~/.cursor/mcp.json` (o `.cursor/mcp.json` del proyecto):
  ```json
  { "mcpServers": { "observatorio-fce": { "url": "https://SU-DOMINIO/mcp" } } }
  ```
  Admin: agregue `"headers": { "Authorization": "Bearer obs_SU_TOKEN" }`.
- **Prueba manual**: `npx @modelcontextprotocol/inspector` → transporte *Streamable HTTP* → URL (y cabecera si es admin).

## 9. Pruebas y calidad

`pytest` cubre: normalización, duplicados, detección de softwares (incluye R y SAS ambiguos), clasificación, lectores HTML,
corrida de punta a punta con datos sintéticos, LLM simulado, API (Google simulado, dominio, pendientes, roles, workflow_dispatch
simulado, CSV públicos) y MCP (lectura pública, ocultamiento de herramientas de admin, token con hash y revocación, límite por IP).
`.github/workflows/pruebas.yml` corre las pruebas y el build del front en cada push.

## 10. Límites conocidos
- La meta de 10 000 depende de lo que LinkedIn deje leer ese día; el reporte indica si no se alcanzó.
- Google Jobs normalmente no responde desde la nube.
- El límite por IP del MCP es por instancia en Vercel.
- Respuestas de Vercel ≤ 4,5 MB: los CSV públicos están paginados; la descarga de Excel de un corte muy grande con
  descripciones puede superar ese límite en Vercel → use el artefacto Excel de la corrida en Actions, la CLI `exportar`,
  o el servidor propio.
