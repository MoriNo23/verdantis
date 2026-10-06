# Proposal — Bajar la complejidad de `_draw`

## Why

`crapper` (CRAP = `CC² × (1 − cobertura)³ + CC`) mide `_draw`
(`NotificationWidget._draw`, 338 líneas) con **CC 30** y CRAP 31. Con 90% de
cobertura el riesgo no es un agujero de tests: es **mantenibilidad**. Es el
método más largo y más condicional del archivo más tocado del repo, y este
ciclo ya lo tocó tres veces (cap del body, ajuste al margen, botones de
acción) — cada una de pie sobre las mismas 338 líneas.

`_draw` mezcla ocho responsabilidades: clear de superficie, fondo y wipe,
cálculo de layout, slot de imagen izquierda, dos pasadas de texto, fila de
botones, barra "Ver más", banner inferior y franja de descarte.

## What Changes

- **BREAKING**: ninguno. Refactor puro: cero cambio de comportamiento, cero
  píxeles, cero rects.
- `_draw` pasa a ser un orquestador de ~35 líneas que delega en helpers, uno
  por responsabilidad, **en el mismo orden de dibujo de hoy**.
- La métrica de layout (`total_lines`/`cap`/`body_h`/`has_more`/`piso`/
  `bands_h`/`row_h`) se extrae a `_layout_metrics`, que es **puro** (no toca
  cairo) y por lo tanto testeable sin display.

## Capabilities

### Modified Capabilities

Ninguna: el render no cambia. `skip_specs: true`.

## Impact

- `src/wayland_popup.py`: `_draw` de 338 a ~35 líneas; CC 30 → ~4 en el
  orquestador y ≤ 8 por helper.
- `tests/test_draw_golden.py`: fixture nueva de 16 casos (píxeles + rects).
- Los tests que leen `_expand_rect`, `_image_left_rect`, `_close_rect` y
  `_action_rects` siguen pasando sin tocarse: ese es el contrato.
