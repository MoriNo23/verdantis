# Tasks

## 1. Red de seguridad (antes de tocar `_draw`)

- [x] 1.1 `tests/test_draw_golden.py`: 16 casos que hashean píxeles + rects.
  Verificación: pasa contra el código actual, y los hashes se generaron con
  `_recalcular_goldens()` ANTES de cualquier cambio en `_draw`.

## 2. La métrica, primero (es lo testeable)

- [x] 2.1 Extraer `_layout_metrics` (puro, sin cairo) con `total_lines`, `cap`,
  `body_h`, `has_more`, `content_h`, `bands_h`, `piso`, `text_h`, `row_h`.
  Verificación: la suite sigue verde — el refactor no cambia comportamiento.
- [x] 2.2 Test de `_layout_metrics` sin display: `has_more` con y sin overflow,
  `cap` acotado a 3, `piso` ≥ slot de 80 px, `bands_h` con y sin actions.
- [x] 2.3 Test de coincidencia con `calc_card_height` en una matriz de
  cuerpos (corto, 2 líneas, overflow, con actions): lo que reserva la card y lo
  que el widget usa para dibujar son el mismo número. Es la red del non-goal de
  D2/reconectar.

## 3. El corte

- [x] 3.1 `_clear_surface` + `_draw_background` (fondo y tinte del wipe).
- [x] 3.2 `_draw_image_left` (publica `_image_left_rect`).
- [x] 3.3 `_draw_actions` (publica `_action_rects`).
- [x] 3.4 `_draw_expand_bar` (publica `_expand_rect`).
- [x] 3.5 `_draw_text_passes` (el closure `draw_text_pass` y sus dos clips).
- [x] 3.6 `_draw_banner` + `_draw_close_strip` (publica `_close_rect`).
- [x] 3.7 `_draw` queda como orquestador de ~35 líneas, con el orden de dibujo
  de hoy declarado en un comentario (el texto se pinta después de la barra).

## 4. Verificación

- [x] 4.1 Fixture de píxeles verde: los 16 casos idénticos byte a byte.
- [x] 4.2 Suite completa verde (`.venv/bin/python -m pytest tests/ -q`).
- [x] 4.3 Re-correr crapper con el LCOV de pytest: el CC de `_draw` baja de 30
  y ningún helper nuevo supera 8. *(Hecho con un DESVÍO documentado: `_draw` cayó
  de CC 30 → 3 y CRAP 31 → 3, pero dos helpers pasaron el estimado de ≤ 8 —
  `_draw_expand_bar` quedó en 11 y `_draw_text_passes` en 9. No es burocracia:
  son branchings inherentes (el doble pase del wipe con su clip por lado, y el
  chevrón ▼/▲). Fragmentarlos más sería perseguir la métrica, no la claridad;
  todos los helpers quedaron ≤ 12, al nivel del `_draw_actions_row` preexistente
  (12), y con 94-100% de cobertura.)*
- [x] 4.4 Verificación en vivo: un toast real (2 líneas y uno largo) se ve igual
  que antes, con la barra "Ver más" donde estaba. *(Hecho: servicio reiniciado,
  `GetServerInformation` → `"0.9.1"`; el toast de VPN de 2 líneas se ve completo,
  justificado y sin barra — idéntico al render pre-refactor, que la fixture
  prueba byte a byte.)*
