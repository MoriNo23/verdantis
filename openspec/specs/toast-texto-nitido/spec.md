# toast-texto-nitido Specification

## Purpose

Define cómo el toast rasteriza el texto sobre su fondo con alpha para que el color de los glyphs sea fiel en cualquier equipo, sin depender de la configuración de antialiasing subpixel del sistema.

## Requirements

### Requirement: El texto se rasteriza con antialiasing en grises

El toast SHALL rasterizar TODO el texto del card (label de app, título, body —incluido el body con markup Pango— y los labels de los botones de acción) con antialiasing en grises, fijado de forma explícita en el contexto de Pango de cada layout. El antialiasing subpixel SHALL NOT aplicarse sobre el fondo translúcido del card: la cobertura de cada glyph no SHALL repartirse por canal de color.

Para que el resultado sea idéntico en cualquier equipo, la elección SHALL provenir del daemon y SHALL NOT quedar librada al antialiasing subpixel que el usuario tenga configurado en fontconfig (`rgba`).

#### Scenario: Texto sobre card translúcido sin franjas de color
- **WHEN** una notificación se renderiza con el fondo del card translúcido y el sistema tiene antialiasing subpixel configurado (fontconfig `rgba: rgb`)
- **THEN** los píxeles de borde de cada glyph tienen la misma proporción de rojo, verde y azul que su color de texto — sin franjas de color — y el texto conserva la paleta de su zona (light/dark del wipe)

#### Scenario: Ningún texto del card queda sin el antialiasing explícito
- **WHEN** un toast muestra label de app, título, body (con y sin markup) y botones de acción
- **THEN** los cuatro bloques se rasterizan con el antialiasing fijado por el daemon, no solo el body

#### Scenario: Un equipo con antialiasing en grises no se degrada
- **WHEN** el sistema ya renderiza con antialiasing en grises (fontconfig `rgba: none`)
- **THEN** el texto se rasteriza con la misma calidad y la misma posición que antes del cambio

### Requirement: El antialiasing no altera métricas ni paleta

Fijar el antialiasing SHALL NO cambiar las métricas del layout (alto del card, wrap del body, cap de líneas colapsadas, offsets de cada fila) ni los colores de texto por zona del wipe. El valor medido del alto del card SHALL seguir coincidiendo con el alto dibujado.

#### Scenario: Las métricas del layout no se mueven
- **WHEN** se compara el alto calculado del card y el alto dibujado antes y después de fijar el antialiasing, para el mismo cuerpo y ancho de columna
- **THEN** los valores son iguales y la suite de consistencia de layout pasa sin cambios

#### Scenario: La paleta del wipe no se mueve
- **WHEN** el frente del wipe cruza el bloque de texto
- **THEN** el color del texto en cada lado de la frontera es el mismo de antes del cambio (light afuera, dark adentro)
