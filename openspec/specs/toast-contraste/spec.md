# toast-contraste Specification

## Purpose

Contraste del texto del card: la legibilidad sobre el fondo translúcido del toast queda verificada de forma automatizada, con los colores reales del código y contra el fondo efectivo del card — no contra negro puro.

## Requirements

### Requirement: El texto del card mantiene contraste AA

El texto del card SHALL mantener contraste AA de WCAG contra el fondo efectivo del toast: ratio ≥ 4.5:1 para el texto de cuerpo, títulos y labels de acciones, y ≥ 3:1 para el texto grande. El fondo efectivo SHALL calcularse compositando el color del card con su alpha real sobre el fondo de referencia `#1e1e2e` (no negro puro). La verificación SHALL ser un test automatizado que lee los colores del código y recalcula los ratios: cualquier cambio de color que rompa un ratio SHALL fallar la suite.

#### Scenario: Texto del card sobre el fondo efectivo

- **WHEN** el toast renderiza cuerpo, título, fila de app y labels de acciones con su paleta actual
- **THEN** cada bloque de texto cumple su ratio (≥ 4.5:1 texto normal, ≥ 3:1 texto grande) contra el fondo compositado

#### Scenario: Un color que rompe el ratio falla la suite

- **WHEN** un color de texto o del fondo cambia y el ratio de algún bloque cae por debajo de AA
- **THEN** el test de contraste falla e identifica el bloque que rompe

#### Scenario: La medición no usa negro puro

- **WHEN** el test calcula el ratio de un bloque
- **THEN** lo mide contra el color del card compositado con su alpha sobre `#1e1e2e`, no contra negro puro
