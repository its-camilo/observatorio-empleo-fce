# Manual de usuario — Observatorio de Empleo FCE

Para monitores de Gestión del Conocimiento (GC). No necesita saber programar.

## 1. Qué hace el aplicativo

Cada vez que se lanza una **corrida** el aplicativo:

1. Busca ofertas de empleo y de práctica de los **últimos 30 días** en LinkedIn, Indeed, Google Jobs y Computrabajo,
   con los términos de búsqueda de cada carrera, en Bogotá, las principales ciudades y remoto Colombia.
2. Limpia los datos, elimina las ofertas repetidas y **descarta las que no son de la FCE**.
3. Asigna cada oferta a una o varias carreras (Administración de Empresas, Contaduría Pública, Economía).
4. Detecta los **softwares** que pide cada oferta según el catálogo, más idiomas y habilidades blandas.
5. Si no llega a **10 000 ofertas** en el corte, hace sola una **mini corrida** con términos más variados.
6. Deja un **reporte** y los datos listos para el aplicativo, Excel y Power BI.

Cada corrida se marca con **semestre** (ej. 2026-II) y **corte** (inicio, mitad o final).

## 2. Ingresar

1. Abra el aplicativo y pulse **Iniciar sesión con Google** con su cuenta **@unal.edu.co**.
2. La primera vez su cuenta queda **pendiente**: pida a un administrador (uniic_bog@unal.edu.co o clagosm@unal.edu.co)
   que la apruebe en **Usuarios**. Luego vuelva a ingresar.

## 3. Lanzar una corrida (solo administradores)

1. Menú **Lanzar corrida** (visible solo para administradores).
2. Escriba el **semestre** (ej. `2026-II`), elija el **corte** y el **modo**:
   - **Completa**: la corrida real (puede tardar varias horas).
   - **Prueba**: pocas ofertas, termina en minutos; sirve para verificar que todo funciona.
3. Pulse **Lanzar** y confirme. Puede cerrar la página: la corrida sigue en GitHub Actions.
4. El panel de **progreso** se actualiza cada 15 segundos: consultas hechas por fuente, ofertas extraídas y procesadas, y un
   enlace a GitHub Actions.
5. Solo puede haber una corrida en marcha a la vez.

**Si la corrida queda “incompleta”**: lea los avisos del reporte. Normalmente una fuente pidió bajar el ritmo. Pida a Desarrollo
relanzarla con el mismo id (continúa sin duplicar) o simplemente lance el siguiente corte; los datos guardados no se pierden.

## 4. Revisar el reporte (Ejecuciones y reportes)

Para cada corrida verá: ofertas encontradas y guardadas **por fuente y por carrera**, **duplicados eliminados**, ofertas
**no relevantes** descartadas, total del corte frente a la meta, si hubo **mini corrida**, **duración** y los **errores
explicados en lenguaje sencillo** (por ejemplo, “LinkedIn está limitando las consultas… reintente más tarde”).

## 5. Consultar ofertas

Menú **Ofertas**: filtre por semestre, corte, carrera, fuente, ciudad, software, tipo de oferta, nivel, modalidad o texto.
Pulse una fila para ver la descripción completa y **qué texto exacto** hizo detectar cada software. El nombre de la fuente
abre la oferta original. Botones **Descargar CSV** y **Descargar Excel** (con los filtros de semestre y corte aplicados).

## 6. Rankings y comparación

- **Ranking**: por corte y carrera, el número y **porcentaje de ofertas** que piden cada software, ordenado de mayor a menor,
  con la variación en puntos porcentuales frente al corte anterior. A la derecha, el peso de cada grupo de software.
- **Comparación entre cortes**: elija corte A (anterior) y B (posterior). Cada software queda como **subió, bajó, igual,
  nuevo o desapareció**. Los avisos amarillos indican si cambiaron fuentes o términos entre cortes (compare con cuidado).

## 7. Catálogo de softwares y sinónimos (solo administradores editan)

- **Agregar un software**: nombre estándar, grupo y sinónimos separados por coma (ej. `EViews` · grupo estadístico · `eviews, e-views`).
- **Sinónimos**: todas las formas en que aparece (Power BI, PowerBI, PBI…). No importan mayúsculas ni tildes.
- Para palabras cortas o ambiguas (como **R** o **SAS**) marque *Distingue mayúsculas* y/o *Exige contexto* y escriba las
  **palabras de contexto** del software (ej. para R: python, sql, estadística). Así “R&D” o “Empresa X SAS” no cuentan.
- Use **Probar detección**: pegue el texto de una oferta y vea qué detectaría el catálogo actual.
- Los cambios se aplican desde la **próxima corrida**.

## 8. Términos de búsqueda

Lista por carrera. **Principal** = se usa en cada corrida. **Ampliado** = solo en la mini corrida automática.
Puede desactivar un término sin borrarlo. Cambiar términos cambia lo que se compara entre cortes: el reporte lo anota.

## 9. Términos no catalogados

Herramientas que se repiten en las ofertas y no están en el catálogo (ej. Alteryx, Snowflake). Revise la lista y elija
**Agregar** (con su grupo) o **Descartar**. Así se detectan herramientas nuevas en el mercado.

## 10. Validación (meta 90 %)

1. Menú **Validación** → elija el corte y el tamaño (30 por defecto) → **Nueva muestra**.
2. Para cada oferta, lea la descripción y compare con los **softwares detectados**.
3. Marque **Correcto** o **Incorrecto**; si quiere, anote softwares que faltaron o que sobran.
4. Arriba ve la **precisión**; la meta del documento es **90 %**. Comparta con Desarrollo los casos incorrectos
   para ajustar sinónimos o reglas.

## 11. Cursos en tendencia

Menú **Cursos**: cursos que muestran Coursera, edX y Platzi para los términos configurados (Excel, Power BI, IA…), con su
posición en el buscador, calificación y popularidad. Se actualizan con cada corrida.

## 12. Configuración (administradores)

Parámetros en formato JSON: fuentes (activar/desactivar, `max_por_particion` por término y ciudad, pausas), ciudades,
ventana de días, tipo de oferta, **`objetivo_ofertas_corrida`** (cuántas ofertas crudas recolectar por corrida, repartidas entre fuentes con más cupo en LinkedIn y consultando LinkedIn primero; también define la meta de relevantes para la mini corrida), mini corrida, duplicados,
IA, reglas de carrera, cursos. Si no está seguro, no cambie nada y consulte a Desarrollo.

## 13. Actualizar Power BI

Siga [powerbi/README.md](../powerbi/README.md) la primera vez. Después de cada corrida: abra el archivo de Power BI y pulse
**Inicio → Actualizar**. No necesita descargar nada.

## 14. Exportar a Excel / Drive

- Desde **Ofertas → Descargar Excel** (hojas Ofertas, Oferta_Software, Catalogo, Ejecuciones, Cursos y Ranking).
- O en GitHub Actions, en la corrida, sección *Artifacts* (Excel del corte).
- Guarde el archivo en la carpeta del Observatorio en el Drive de la UIFCE.

## 15. Asistentes de IA (MCP)

Cualquier persona puede consultar los datos públicos desde Claude, ChatGPT o Cursor agregando el servidor
`https://SU-DOMINIO/mcp`. Cualquier usuario aprobado puede generar un **token** en **Tokens MCP** (se muestra una sola vez;
revóquelo si se pierde): hereda su rol (consulta; los admins también ven estado y pueden lanzar corridas). Ver documentación técnica, sección 8.

## 16. Preguntas frecuentes

- **¿Por qué hay menos de 10 000 ofertas?** Las fuentes limitan cuántas dejan ver; el aplicativo hace una mini corrida y,
  si aun así no llega, lo dice en el reporte.
- **¿Por qué Google Jobs trae 0?** Google suele bloquear consultas desde servidores en la nube; las demás fuentes siguen.
- **¿Se guardan datos personales o salarios?** No. Se eliminan correos, teléfonos y salarios de las descripciones.
- **Encontré una oferta mal clasificada.** Anótela en Validación o avise a Desarrollo con su id (ej. `LI-123456`).
