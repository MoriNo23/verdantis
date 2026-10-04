# toast-body-colapso Specification

## Purpose
Define el colapso del body del toast: cuántas líneas completas se muestran, dónde cae el ellipsis y la coherencia entre la altura reservada de la card y lo efectivamente dibujado.

## Requirements

### Requirement: El ellipsis cae tras el número exacto de líneas del cap

Cuando el body excede el máximo de líneas visibles (3), el toast SHALL mostrar exactamente las primeras 3 líneas completas y el ellipsis ("...") SHALL caer al final de la tercera línea — nunca antes. El cálculo del límite SHALL usar la altura real de la línea del font renderizado, no una aproximación derivada del tamaño de fuente, para que ninguna fuente, escala de resolución o variante de layout corte de más.

#### Scenario: Body largo con overflow
- **WHEN** un body que wrappea a 6 líneas se muestra colapsado
- **THEN** se ven 3 líneas completas y el "..." cae al final de la tercera línea, con el botón "Ver más" presente

#### Scenario: El cap nunca corta una línea antes de tiempo
- **WHEN** el body desborda el cap y la altura real de línea es mayor que la aproximación por tamaño de fuente
- **THEN** el toast igual muestra las 3 líneas del cap (el presupuesto se mide de la línea real, no se estima)

#### Scenario: El ellipsis no aparece tras una sola línea
- **WHEN** el toast muestra un body colapsado con su cap de líneas
- **THEN** el "..." nunca aparece después de una línea cuando el cap es mayor — el texto cabe exacto hasta el salto que le corresponde

### Requirement: El body sin overflow se muestra completo

Un body que wrappea a 2 líneas o menos SHALL mostrarse completo: sin ellipsis, sin recorte y sin botón "Ver más". El botón solo aparece cuando el body realmente excede el cap.

#### Scenario: Body de exactamente dos líneas
- **WHEN** un body wrappea a exactamente 2 líneas
- **THEN** las dos líneas se muestran completas, sin "..." y sin botón "Ver más"

#### Scenario: Body de una línea
- **WHEN** el body cabe en una sola línea
- **THEN** se muestra entero, sin "..." ni botón

### Requirement: La altura de la card coincide con lo dibujado

La altura que la card reserva para el body colapsado SHALL calcularse con la misma fórmula que el dibujado del límite de líneas: la medición y el render usan el mismo presupuesto de altura por línea. Ninguna de las dos SHALL estimar por su cuenta.

#### Scenario: Sin hueco ni solape bajo el body colapsado
- **WHEN** un body con overflow se colapsa a las líneas del cap y la card muestra su barra "Ver más"
- **THEN** la barra ancla justo debajo del texto dibujado, sin franja vacía extra ni solape (la altura reservada es exactamente la dibujada)

#### Scenario: Coherencia en cualquier escala de resolución
- **WHEN** el toast se renderiza con una escala de fuente distinta (pantallas de baja resolución)
- **THEN** el cap sigue cortando en el número exacto de líneas y la altura reservada sigue coincidiendo con lo dibujado
