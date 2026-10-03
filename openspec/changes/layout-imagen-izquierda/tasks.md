# Tasks

## 1. Preparación (TDD por worktrees: B ya dejó la rama roja verificada)

- [ ] 1.1 Verificar el inventario rojo del change `tests-layout-imagen-izquierda` (la rama `testing/layout-imagen-izquierda` con sus tests fallando por las razones correctas) y mergearla a main como primer paso — verificación: el inventario del rojo de B está documentado en su tasks.md, y `git log` muestra el merge de la rama antes de cualquier commit de src.
- [ ] 1.2 Confirmar que la suite en main queda ROJA solo por los tests nuevos/renombrados de B (sin errores de colección ni imports) — verificación: corrida de `.venv/bin/python -m pytest tests/ -q` con los fallos listados coincidiendo con el inventario de B, uno por uno.

## 2. Pila sin solapes (spec `toast-stack`)

- [ ] 2.1 Wire del restack on-resize en el daemon: el `on_resize` del popup redimensiona (vía `_resize_card` actual) y luego ejecuta el restack de todos los activos (el mismo loop `set_stack_margin(i)` de `_close_id`) — verificación: los tests de B de "expandir con toasts debajo" y "reflow estable" pasan.
- [ ] 2.2 Verificar que el re-wrap por hover de un persistente también re-flowea (sin código extra: la puerta de resize de 0.7.0 + el wiring de 2.1) — verificación: el test de B de "re-wrap por hover también re-flowea" pasa.

## 3. Imagen izquierda siempre (spec `toast-imagen-izquierda`)

- [ ] 3.1 Placeholder 80 px como último eslabón de la cadena del slot (reusar `_make_placeholder_icon` + clip circular de `_make_circular`); el slot nunca queda `None` — verificación: tests de B "nada resuelve → placeholder con inicial" y "la imagen de la notificación gana siempre" pasan.
- [ ] 3.2 Eliminar la rama sin slot de `_draw` (`icon_size = 0`) y la variante ancha: `_eff_text_width` devuelve 240 siempre (196 con franja en hover persistente), `_rows_above_body` pierde el `_HR_GAP` condicional, fuentes unificadas título 11 / body 11 — verificación: tests de B de "columna única" y de actualización de 332/288→240/196 pasan.
- [ ] 3.3 Texto al top del slot: `ty = pad` (fuera el centrado del bloque), slot conserva su centrado en la fila; el piso `row_h = max(text_h, _ROW_MIN_H)` se mantiene — verificación: tests de B "fila de app al top del slot (±1 px)" y "sin respiro de la variante sin imagen" pasan.

## 4. Rename y docs

- [ ] 4.1 Rename en src: `_avatar_pb`→`_image_left_pb`, `_AVATAR_W`→`_IMAGE_LEFT_W`, `_AVATAR_GAP`→`_IMAGE_LEFT_GAP`, comentarios/docstrings sin "avatar" — verificación: `grep -rn "avatar" src/` sin hits y suite verde (los tests de B ya usan los nombres nuevos).
- [ ] 4.2 AGENTS.md: terminología imagen izquierda (sección "Iconos del tab" y donde mencione avatar) — verificación: `grep -n "avatar" AGENTS.md` sin hits vivos.

## 5. Integración, verificación viva y release

- [ ] 5.1 Suite completa verde en main con el comando documentado — verificación: `.venv/bin/python -m pytest tests/ -q` 0 failed (incluye todos los tests de B ya mergeados); conteo documentado en la task.
- [ ] 5.2 Bump `VERSION` → 0.8.0 dentro del commit `feat:` en español y verificación en vivo tras reiniciar el servicio: pila de toasts (expandir el de arriba mantiene el gap abajo), hover en persistente (re-flow + X visible), toast de app sin icono (placeholder con inicial) — verificación: `busctl --user call ... GetServerInformation` → "0.8.0" y comportamiento observado sin solapes.
- [ ] 5.3 Cerrar el ciclo de worktrees: archivar `tests-layout-imagen-izquierda` (sus tests ya viven en main verdes) y habilitar el change `actualizar-tablero-imagen-izquierda` (merge main → diseno-demos) — verificación: `openspec list` con solo los changes que corresponden y el A listo para ejecutar en su worktree.
