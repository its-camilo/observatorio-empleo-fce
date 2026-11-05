# Power BI — conexión al Observatorio (RF-14)

El aplicativo publica las tablas del diccionario de datos como CSV en URLs públicas
(opcionalmente protegidas con `CSV_TOKEN`). Power BI las lee con **Obtener datos → Web**
y se actualiza con **un clic** (Inicio → Actualizar) después de cada ejecución.

| Tabla | URL | Contenido |
|---|---|---|
| Ofertas | `/api/publico/ofertas.csv` | Una fila por oferta (sin descripción por defecto; agregue `descripcion=true` si la necesita) |
| Oferta–Software | `/api/publico/oferta_software.csv` | Una fila por software detectado en una oferta |
| Oferta–Carrera | `/api/publico/oferta_carrera.csv` | Una fila por oferta y carrera (las ofertas pueden tener varias carreras) |
| Catálogo | `/api/publico/catalogo.csv` | Software, grupo, sinónimos, activo |
| Ejecuciones | `/api/publico/ejecuciones.csv` | Trazabilidad de cada corrida |
| Cursos | `/api/publico/cursos.csv` | Cursos en tendencia (módulo opcional) |

Parámetros: `pagina` (1, 2, …), `tamano` (máx. 20 000, por defecto 5 000), `semestre`, `corte`, `token`.
Las respuestas están paginadas para no superar el límite de tamaño de Vercel (4,5 MB por respuesta).

## Opción recomendada: consultas listas (paginación automática)

1. Abra Power BI Desktop → **Inicio → Transformar datos**.
2. **Nueva consulta → Consulta en blanco → Editor avanzado**. Cree una consulta por bloque de
   [`consultas.pq`](consultas.pq), con el nombre indicado en cada comentario (`Parametros`, `LeerTabla`,
   `Ofertas`, `OfertaSoftware`, `OfertaCarrera`, `Catalogo`, `Ejecuciones`, `Cursos`).
3. En `Parametros` cambie `BaseUrl` por la dirección del aplicativo (y `Token` si se configuró `CSV_TOKEN`).
4. Si pregunta por la autenticación, elija **Anónimo** y nivel de privacidad **Organizativo**.
5. **Cerrar y aplicar**.

## Opción rápida (sin código, una página de datos)

**Obtener datos → Web →** `https://SU-DOMINIO/api/publico/ofertas.csv?tamano=20000`.
Sirve mientras el histórico tenga menos de 20 000 filas por tabla; después use la opción recomendada.

## Modelo (relaciones)

- `Ofertas[id_oferta]` 1 → * `OfertaSoftware[id_oferta]`
- `Ofertas[id_oferta]` 1 → * `OfertaCarrera[id_oferta]` (filtro de carrera: use `OfertaCarrera[carrera]`)
- `Catalogo[software]` 1 → * `OfertaSoftware[software]`
- `Ejecuciones[id_ejecucion]` 1 → * `Ofertas[id_ejecucion]`

Medidas sugeridas (DAX):

```DAX
Ofertas totales = DISTINCTCOUNT(Ofertas[id_oferta])
Ofertas con software = CALCULATE(DISTINCTCOUNT(OfertaSoftware[id_oferta]))
% de ofertas = DIVIDE([Ofertas con software], CALCULATE([Ofertas totales], REMOVEFILTERS(OfertaSoftware)))
```

## Páginas sugeridas (sección 10.2 del documento)

1. **Resumen general**: tarjetas de total de ofertas; barras por fuente, carrera (`OfertaCarrera`), ciudad, tipo de oferta y modalidad; top 10 de `OfertaSoftware[software]` por `[% de ofertas]`.
2. **Ranking por carrera**: tabla con software, grupo, `[Ofertas con software]` y `[% de ofertas]`, segmentador por carrera.
3. **Por grupo de software**: barras apiladas de `OfertaSoftware[grupo_software]` por carrera.
4. **Comparación entre semestres**: matriz software × (semestre, corte) con `[% de ofertas]`; formato condicional para ver subidas y bajadas. El aplicativo también calcula “subió / bajó / nuevo / desapareció” en *Rankings y comparación*.
5. **Prácticas vs. empleo**: mismo ranking con segmentador `Ofertas[tipo_oferta]`.
6. **Detalle**: tabla con cargo, empresa, ciudad, carrera, fuente y `url` (categoría de datos: URL web).

Filtros mínimos: semestre, corte, carrera, fuente, ciudad, tipo de oferta, nivel de experiencia y grupo de software.

> Un archivo `.pbit` es opcional: cuando el dashboard esté armado, guárdelo como plantilla
> (Archivo → Exportar → Plantilla de Power BI) en esta carpeta para reutilizarlo cada semestre.
