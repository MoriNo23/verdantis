# Proposal — Ellipsis del body tras el número exacto de líneas

## Why

El colapso del body presupuesta la altura del cap de líneas con la heurística `font_size × 1.6` (17.6 px/línea con la body font 11 actual), pero la línea real de Manrope mide **21 px** — el presupuesto siempre queda ~una línea corto y Pango corta antes: un body largo muestra 2 líneas + "..." en vez de 3, y **un body de exactamente 2 líneas muestra 1 sola línea + "..." SIN botón "Ver más"** (no hay overflow según el cap), dejando el resto del texto ilegible. La heurística era casi-exacta con la body 13 de la variante vieja; la columna única de 0.8.0 amplificó el error a 19% y lo volvió sistemático.

## What Changes

- **Presupuesto exacto en vez de heurística**: el cap de altura del layout (`set_height` + ellipsize) SHALL calcularse como `N × altura_real_de_línea` — la altura lógica de la línea medida del propio layout renderizado, no una aproximación por tamaño de fuente. La misma fórmula en `_draw_text` (dibujado) y `_body_metrics` (medición de altura de card): la medición y el dibujado no pueden divergir (regla de fuente única del repo).
- **Resultado observable**: el "..." cae al final de la línea que corresponde — 3 líneas completas cuando hay overflow (con su "Ver más"); un body de 2 líneas se muestra **completo**, sin "..." ni botón; un body de 1 línea ídem. El texto cabe exacto hasta el salto que le toca.
- **Validación empírica ya hecha** (exploración previa): con el presupuesto medido, el corte es exacto en N para caps 1/2/3/5, sin problemas de borde; con la heurística, cap=3 → 2 líneas y cap=2 → 1 línea (bug).
- **Knock-on de alturas**: los bodies con overflow pasan a reservar 3 líneas reales (63 px en vez de 42 px) → la altura de la card "body largo" cambia → el mock correspondiente del tablero de diseño se re-deriva (el validador ya lo detecta; worktree de diseño on-demand).
- Bump PATCH → **0.8.1** (`fix:`). TDD: test rojo primero (documenta el colapso a 1 línea), fix mínimo, suite verde.
- **BREAKING**: ninguno — sin API DBus, sin cambios de formato; solo el render deja de cortar de más.

## Capabilities

### New Capabilities
- `toast-body-colapso`: el colapso del body — número exacto de líneas visibles, dónde cae el ellipsis y la coherencia entre la altura reservada de la card y lo dibujado.

### Modified Capabilities

(ninguna — el colapso del body no está cubierto por ningún spec existente: franja, iconos, imagen-izquierda, orden-llegada y stack no lo tocan)

## Impact

- `src/wayland_popup.py`: `_body_metrics` (l.385) y `_draw_text` (l.901) — la fórmula del presupuesto del cap (misma en ambos); `calc_card_height` hereda la corrección vía `_body_metrics`, sin cambios propios.
- Alturas de card para bodies con overflow → tablero de diseño (mock body-largo + manifiestos re-derivados desde el worktree `diseno-demos`).
- Tests: nuevos del contrato (2 líneas completas / 3 + "..." al final de la tercera / coherencia medición-dibujado) + metatest de sensibilidad que inyecte la heurística vieja.
- Sin cambios de API DBus, daemon o resolución de iconos.
