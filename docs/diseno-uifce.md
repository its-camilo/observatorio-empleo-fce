# Sistema de diseño — Capacitación interna "Inteligencia Artificial Generativa"

Guía de línea gráfica y colorimetría extraída de la portada de la capacitación interna (periodo 2026-2S) de la Unidad de Informática, Facultad de Ciencias Económicas, Universidad Nacional de Colombia. Sirve como base para dar el mismo estilo a una página web.

---

## 1. Concepto visual

- **Sensación:** institucional, tecnológica y amable. Un marco azul sólido contiene una "tarjeta" blanca muy limpia, con mucho aire, titulares enormes y una ilustración de robot en estilo vectorial plano con contorno oscuro.
- **Composición:** centrada y simétrica. Jerarquía vertical clara: etiqueta de periodo (arriba a la izquierda) → título gigante → subtítulo de color brillante → autor y cargo → ilustración protagonista → etiqueta de área (abajo a la derecha).
- **Textura:** patrón de puntos de medios tonos ("halftone") en azul claro que se desvanece sobre el blanco, a modo de ondas suaves en los costados y detrás de la ilustración. Aporta profundidad sin ensuciar.
- **Esquinas:** la tarjeta blanca tiene esquinas muy redondeadas (aprox. 40 px sobre 1912 px de ancho, es decir, cerca del 2 % del ancho). Todo el lenguaje es suave, sin ángulos duros.

---

## 2. Paleta de color

Los códigos son hexadecimales, muestreados directamente de la imagen.

### Colores principales

| Rol | Nombre | Código | Uso |
|---|---|---|---|
| Marco y pie | Azul institucional | `#4574B9` | Fondo general de la página, barra superior, franja inferior (pie de página), botones secundarios |
| Titulares y etiquetas | Azul marino profundo | `#042361` | Título principal, etiquetas de periodo y de área, texto de mayor jerarquía, enlaces |
| Acento | Cian eléctrico | `#44D3FE` | Subtítulo, palabra clave dentro de pantallas o tarjetas oscuras, líneas decorativas, estados activos |
| Superficie | Blanco | `#FEFEFE` | Tarjeta principal de contenido, fondo de secciones |

### Colores de apoyo

| Rol | Nombre | Código | Uso |
|---|---|---|---|
| Texto secundario | Gris azulado | `#525C76` | Nombre del autor, cargo, párrafos, metadatos |
| Textura | Azul niebla | `#AFC6E4` | Patrón de puntos de medios tonos, bordes sutiles, fondos de tarjetas secundarias |
| Contraste oscuro | Negro puro | `#000000` | Pantallas, bloques de énfasis, contorno de la ilustración |
| Ilustración, cuerpo | Crema suave | `#EAE9CB` | Rellenos de ilustraciones, tarjetas cálidas, fondos de citas |
| Ilustración, articulaciones | Gris grafito | `#5B5B5B` | Detalles de ilustración, iconos secundarios |
| Alerta / destacado | Amarillo señal | `#F4CB18` | Único toque cálido: botón de llamada a la acción, insignias, indicadores. Usar con mucha moderación |

### Proporción de uso recomendada

- Blanco: 45 %
- Azul institucional: 25 %
- Azul marino profundo: 12 % (principalmente texto)
- Cian eléctrico: 8 %
- Gris azulado, azul niebla y crema: 8 %
- Negro y amarillo: 2 %

### Variables de estilo sugeridas

```css
:root {
  --color-primario:        #4574B9;
  --color-primario-oscuro: #042361;
  --color-acento:          #44D3FE;
  --color-superficie:      #FEFEFE;
  --color-texto:           #042361;
  --color-texto-suave:     #525C76;
  --color-textura:         #AFC6E4;
  --color-negro:           #000000;
  --color-crema:           #EAE9CB;
  --color-grafito:         #5B5B5B;
  --color-destacado:       #F4CB18;

  --radio-tarjeta: 40px;
  --radio-boton:   999px;
  --sombra-suave:  0 8px 30px rgba(4, 35, 97, 0.12);
}
```

### Combinaciones con buen contraste

- Azul marino `#042361` sobre blanco `#FEFEFE`: excelente, apto para texto de cualquier tamaño.
- Gris azulado `#525C76` sobre blanco: bueno para texto de párrafo.
- Cian `#44D3FE` sobre negro `#000000`: excelente (como en la pantalla del robot).
- Cian `#44D3FE` sobre blanco: **solo para texto grande y en negrita** (como el subtítulo). No usarlo para párrafos.
- Blanco sobre azul institucional `#4574B9`: aceptable para texto grande o en negrita; para texto pequeño preferir el azul marino como fondo.
- Texto del pie (cursiva, blanco con ligera transparencia) sobre azul institucional: usar tamaño pequeño pero legible.

---

## 3. Tipografía

La imagen usa sans serif geométricas y humanistas, con una jerarquía de peso muy marcada. Equivalencias gratuitas en Google Fonts:

| Elemento | Estilo observado | Fuente sugerida | Peso |
|---|---|---|---|
| Título principal (MAYÚSCULAS) | Sans serif geométrica, ultra negrita, ligeramente compacta, interlineado muy ajustado | **Montserrat** (alternativa: Poppins) | 800 – 900 |
| Subtítulo | Sans serif redondeada de display, negrita, en minúsculas | **Ubuntu** (alternativa: Nunito) | 700 |
| Nombre del autor | Sans serif humanista, seminegrita | **Fira Sans** (alternativa: Source Sans 3) | 600 |
| Cargo y párrafos | Misma familia, peso regular | **Fira Sans** | 400 |
| Etiquetas (periodo, área) | Sans serif geométrica negrita, compacta | **Montserrat** | 700 – 800 |
| Pie de página | Humanista condensada en cursiva | **Fira Sans Condensed** | 400 cursiva |

### Escala tipográfica sugerida (escritorio)

| Nivel | Tamaño | Notas |
|---|---|---|
| Título principal | `clamp(3rem, 8vw, 7rem)` | Mayúsculas, interlineado 0.95, espaciado entre letras -0.01em |
| Subtítulo | `clamp(1.75rem, 3.5vw, 3rem)` | Color cian, minúsculas con inicial mayúscula |
| Encabezado de sección | `2rem` | Azul marino, peso 800 |
| Autor | `1.5rem` | Gris azulado, peso 600 |
| Cargo y párrafo | `1.125rem` | Gris azulado, interlineado 1.6 |
| Etiqueta | `1.5rem` | Mayúsculas, azul marino |
| Pie de página | `0.95rem` | Cursiva, blanco |

---

## 4. Estructura y maquetación

### Marco general

- El fondo de toda la página es azul institucional `#4574B9`.
- El contenido vive dentro de una **tarjeta blanca** con esquinas redondeadas, separada del borde por un margen azul de unos 2 % del ancho (en pantallas pequeñas, 12 px).
- Debajo de la tarjeta queda una **franja azul de pie de página** (aprox. 12 % de la altura de la composición) con texto institucional a la izquierda y logotipos a la derecha, separados por una línea vertical delgada y clara.

### Zonas de la portada (héroe)

1. **Esquina superior izquierda:** etiqueta de periodo (ejemplo: "2026-2S") en azul marino, negrita.
2. **Centro superior:** título principal gigante, centrado, en azul marino.
3. **Debajo del título:** subtítulo en cian, centrado y pegado al título.
4. **Bloque de autoría:** nombre en seminegrita y cargo en regular, ambos en gris azulado, centrados.
5. **Centro inferior:** ilustración del robot sosteniendo una pantalla negra con la palabra clave en cian. Se corta por el borde inferior de la tarjeta, como si "asomara".
6. **Esquina inferior derecha:** etiqueta de área o categoría en dos líneas, mayúsculas, azul marino, alineada a la derecha.
7. **Fondo:** ondas de puntos de medios tonos en azul niebla, a ambos lados y detrás de la ilustración.

### Cuadrícula

- Contenedor máximo: 1200 – 1280 px, centrado.
- 12 columnas, separación de 24 px.
- Secciones con relleno vertical generoso (96 – 128 px en escritorio, 56 – 72 px en móvil).

---

## 5. Componentes

### Botón principal
- Fondo azul marino `#042361`, texto blanco, forma de píldora (`border-radius: 999px`), relleno 14 × 32 px, peso 700.
- Al pasar el cursor: fondo cian `#44D3FE` con texto azul marino y ligera elevación.

### Botón de llamada a la acción destacado
- Fondo amarillo señal `#F4CB18`, texto azul marino, misma forma de píldora. Solo uno por pantalla.

### Botón secundario
- Borde de 2 px en azul institucional, fondo transparente, texto azul institucional. Al pasar el cursor: relleno azul niebla.

### Tarjetas de contenido
- Fondo blanco, esquinas de 24 – 32 px, borde de 1 px en azul niebla, sombra suave azulada.
- Título en azul marino negrita, texto en gris azulado.
- Variante cálida: fondo crema `#EAE9CB` con contorno oscuro fino, para ilustraciones.

### Bloque "pantalla" (énfasis)
- Fondo negro, borde crema de 8 px con esquinas redondeadas, palabra clave grande en cian. Úsalo para cifras, términos clave o frases destacadas.

### Etiquetas e insignias
- Mayúsculas, azul marino, sin fondo (como "2026-2S") o con fondo cian claro para estados.

### Navegación
- Barra superior sobre el marco azul: logotipo a la izquierda, enlaces en blanco con peso 600; el enlace activo lleva un subrayado cian de 3 px.
- En móvil: menú tipo hamburguesa, panel desplegable con fondo azul institucional.

### Pie de página
- Franja azul institucional a todo el ancho. Izquierda: nombre de la facultad, de la unidad y de la sede, en cursiva blanca, tres líneas. Derecha: logotipos de la unidad y de la universidad en blanco, separados por una línea vertical fina.

---

## 6. Ilustración e iconografía

- **Estilo:** vectorial plano, contorno negro fino y uniforme (2 – 3 px), rellenos sólidos, sin degradados ni sombras duras.
- **Paleta de ilustración:** crema `#EAE9CB`, grafito `#5B5B5B`, negro, cian `#44D3FE` y un único detalle amarillo `#F4CB18`.
- **Personaje:** robot amigable con manos expresivas levantadas que enmarcan una pantalla; transmite cercanía, no frialdad tecnológica.
- **Iconos:** de línea gruesa y terminaciones redondeadas, en azul marino o cian, mismo grosor de trazo que la ilustración.
- **Recorte:** las ilustraciones pueden salirse del borde inferior de la tarjeta para dar sensación de profundidad.

---

## 7. Efectos y movimiento

- **Textura de puntos:** generarla con un degradado radial repetido (`radial-gradient(circle, #AFC6E4 1.5px, transparent 1.6px)` con tamaño de 8 px) y una máscara de degradado para que se desvanezca hacia el blanco. Colocarla en los costados y detrás de la ilustración.
- **Entrada de secciones:** aparición suave hacia arriba (24 px, 500 ms, curva `ease-out`).
- **Ilustración:** flotación vertical muy ligera (±6 px, 4 s, infinita). Las manos pueden tener un pequeño balanceo.
- **Interacciones:** transiciones de 200 – 250 ms en color y elevación. Evitar rebotes agresivos.
- **Accesibilidad:** respetar la preferencia de movimiento reducido del sistema.

---

## 8. Reglas de uso

**Sí**
- Mucho espacio en blanco y titulares enormes.
- Un solo color de acento protagonista (cian) y un solo toque cálido (amarillo).
- Esquinas redondeadas en todo: tarjetas, imágenes, botones.
- Mantener el marco azul y la tarjeta blanca como identidad constante en todas las páginas.

**No**
- No usar cian como color de texto pequeño sobre fondo blanco.
- No mezclar más de dos pesos tipográficos en un mismo bloque.
- No añadir degradados, sombras duras ni colores fuera de la paleta.
- No usar el amarillo para fondos grandes.
- No colocar texto largo sobre el patrón de puntos sin una capa blanca de apoyo.

---

## 9. Adaptación a pantallas pequeñas

- Tarjeta blanca con margen azul de 12 px y esquinas de 24 px.
- Título principal en dos líneas centradas; subtítulo debajo.
- Ilustración reducida al 80 % del ancho, recortada en el borde inferior.
- Etiquetas de periodo y de área pasan a una fila superior e inferior, centradas.
- Pie de página apilado: texto institucional arriba, logotipos debajo.

---

## 10. Resumen rápido para quien programe

1. Fondo de página: `#4574B9`.
2. Tarjeta principal: `#FEFEFE`, radio 40 px, centrada.
3. Títulos: Montserrat 800, `#042361`, mayúsculas.
4. Subtítulo y acentos: Ubuntu 700, `#44D3FE`.
5. Texto corrido: Fira Sans 400, `#525C76`.
6. Textura de puntos `#AFC6E4` en los costados y detrás de la ilustración.
7. Ilustración plana con contorno negro y detalle amarillo `#F4CB18`.
8. Pie de página: franja `#4574B9` con texto en cursiva blanca y logotipos a la derecha.
