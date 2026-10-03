# Proposal — Ocultar la X sin hover y arreglar los iconos de app

## Why

La X de cierre de los toasts persistentes reserva **siempre** 44 px de columna de texto: el texto de un persistente se wrappea a 288 px (los estándar usan 332) aunque la franja ni se dibuje, y la X aparece en cuanto el puntero toca el card — que vive en la esquina superior derecha, justo por donde el mouse pasa seguido. Es espacio perdido y ruido visual permanente en las notificaciones que más tiempo quedan en pantalla.

El logo de 16 px de la fila de app se ve **cortado** en iconos no cuadrados (`_resample` hace center-crop del cuadrado central) y **desaparece** cuando la cadena de adquisición falla. Hay además una falla estructural visible en el código: el daemon normaliza `app_icon` a path-o-vacío (`app_icon_file`) antes de crear el popup, así que los nombres de icono "pelados" que mandan muchos senders (ej. `firefox`) nunca llegan al widget y el theme-lookup por `app_icon` es código muerto en la práctica.

## What Changes

- **X solo con hover (persistentes)**: la franja + X se dibujan únicamente mientras el puntero está sobre el toast; el estado sin hover queda garantizado y verificado (sin X "pegada" cuando el toast se mueve o la pila hace reflow).
- **Reclamo del espacio con wrap dinámico** (decisión del usuario): sin hover, la columna de texto del persistente usa el ancho completo (332 px, o 240 con avatar); con hover se reduce a 288 px y el texto re-wrappea — la franja nunca pisa texto. La transición de altura reutiliza la vía existente (`on_resize` → `_resize_card`), con verificación de que no oscilen los eventos enter/leave.
- **Sin cambios** en la barra "Ver más" + chevrón (siguen siempre visibles, decisión del usuario) ni en el avatar de 80 px (cover-crop circular por diseño).
- **Iconos 16 px — adquisición**: auditoría end-to-end documentada del camino del icono (DBus `Notify` → daemon `_local_path`/`os.path.exists` → widget) con senders reales; los hallazgos se corrigen. Primer hallazgo ya identificado en código: los nombres de tema pelados se pierden en la normalización del daemon.
- **Iconos 16 px — render**: contain (letterbox dentro del slot 16×16, preserva aspect ratio) en vez de center-crop — los iconos no cuadrados dejan de verse cortados.
- **Iconos 16 px — fallback**: placeholder genérico cuando ninguna fuente resuelve; el slot de la fila de app nunca queda vacío.
- Reglas que **no** se tocan: match EXACTO de `.desktop` (los PWA de Brave rompen con match difuso), interpolación HYPER, clip circular del avatar.
- **BREAKING**: ninguno — la API DBus, el protocolo freedesktop y el formato del historial no cambian.
- Versionado: bump MINOR → 0.7.0 (primer `feat:` del ciclo).

## Capabilities

### New Capabilities
- `toast-franja-descarte`: visibilidad de la franja/X de descarte en toasts persistentes (solo con hover) y ancho de la columna de texto (332 sin hover / 288 con hover, con re-wrap dinámico).
- `toast-iconos-app`: adquisición, render con aspect ratio y fallback del logo de 16 px de la fila de app.

### Modified Capabilities

(ninguna — este root de OpenSpec no tiene specs previos; los specs del tablero viven en el root separado de `DISEÑO-DEMOS/`)

## Impact

- **`src/wayland_popup.py`**: `_eff_text_width` y `_draw` (`strip_w` pasa a hover-only), `calc_card_height` (la resta de 44 px deja de colgar de `persistent` fijo — el caller ya pasa el ancho efectivo), cadena de `_app_icon_pb` en `__init__`, `_resample` (modo contain para el logo 16 px), `_on_enter`/`_on_leave` (re-cálculo de altura en la transición).
- **`src/verdantis_daemon.py`**: passthrough del `app_icon` crudo junto al path normalizado (si la auditoría lo confirma); `VERSION` → 0.7.0.
- **Tests**: cambian los que fijan el comportamiento actual (`test_persistent_reserves_strip_in_text_width`, `test_eff_text_width_shrinks_for_persistent`, `test_expand_strip_reserves_close_strip` en `tests/test_action_zones.py`); se agregan tests del nuevo comportamiento + metatests de sensibilidad (convención `test_tests_*.py`).
- **`DISEÑO-DEMOS`**: el validador del tablero (`herramientas/validar_geometria_tablero.py`) deriva las columnas de las constantes del código — debe seguir en verde; la columna "persistente 288" pasa a representar el estado con hover (nota semántica, sin editar el tablero).
- Sin cambios de API DBus, dependencias ni formato del historial/dashboard.
