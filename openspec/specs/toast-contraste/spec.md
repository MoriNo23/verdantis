# toast-contraste Specification

## Purpose

Contraste del texto del card: la legibilidad sobre el fondo translúcido del toast queda verificada de forma automatizada, con los colores reales del código y contra el fondo efectivo del card — no contra negro puro.

## Requirements

### Requirement: El texto del card mantiene contraste AA

El texto del card SHALL mantener contraste AA de WCAG contra el fondo efectivo del toast: ratio ≥ 4.5:1 para el texto de cuerpo, títulos y labels de acciones, y ≥ 3:1 para el texto grande. El fondo del card es un gradiente vertical de `rgba(58, 60, 74, 0.90)` a `rgba(30, 30, 44, 0.94)`; el fondo efectivo SHALL calcularse compositando CADA stop del gradiente con su alpha real (piso mínimo 0.90, spec `toast-vibrancia`) sobre el fondo de referencia `#1e1e2e` (no negro puro). La verificación SHALL ser un test automatizado que lee los colores del código y recalcula los ratios en ambos extremos del gradiente: cualquier cambio de color que rompa un ratio SHALL fallar la suite.

#### Scenario: Texto del card sobre el fondo efectivo del gradiente

- **WHEN** el toast renderiza cuerpo, título, fila de app y labels de acciones con su paleta actual sobre el gradiente con alpha
- **THEN** cada bloque de texto cumple su ratio (≥ 4.5:1 texto normal, ≥ 3:1 texto grande) contra el fondo compositado, tanto en el stop superior como en el inferior

#### Scenario: Un color que rompe el ratio falla la suite

- **WHEN** un color de texto o del fondo cambia y el ratio de algún bloque cae por debajo de AA
- **THEN** el test de contraste falla e identifica el bloque que rompe

#### Scenario: La medición no usa negro puro

- **WHEN** el test calcula el ratio de un bloque
- **THEN** lo mide contra cada stop del gradiente compositado con su alpha sobre `#1e1e2e`, no contra negro puro

#### Scenario: Bajar el alpha por debajo del piso rompe el contraste

- **WHEN** el alpha de algún stop del gradiente baja de 0.90
- **THEN** el test de contraste falla y señala el stop y el bloque afectado
