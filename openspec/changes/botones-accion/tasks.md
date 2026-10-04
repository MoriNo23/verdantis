# Tasks

## 1. Tests rojos del contrato (spec `toast-acciones`)

- [x] 1.1 Test de render de la fila: notificación con `["default", "Abrir sitio", "settings", "Ajustes", "mark", "Marcar"]` → dos botones visibles ("Ajustes" key `settings`, "Marcar" key `mark`) en la fila bajo el body; `default` y su label NO se renderizan; sin actions no hay fila (layout idéntico al actual) — verificación: tests fallan contra el código actual (hoy no existe la fila) y los asserts nombran el requisito del spec.
- [x] 1.2 Test de invocación por botón: click dentro del rect de cada botón → el callback recibe LA key de ese botón (`on_click(action_key)`); el click NO dispara la default ni abre URL del body; click en el cuerpo fuera de botones → `action_key=None` (default, como hoy) — verificación: spy sobre el callback con las coords del rect publicado por `_draw`.
- [x] 1.3 Test de límites y robustez del parseo: >3 actions además de default → solo los primeros 3; lista con key duplicada → la primera gana; lista impar (key suelta al final) → el suelto se ignora sin crash — verificación: cada caso con su assert del spec.
- [x] 1.4 Test de action-icons: con hint + botón cuyo key es icono del tema (p. ej. `mail-mark-read`) → el botón renderiza icono + label; key sin icono → solo label sin hueco; sin hint → solo texto siempre — verificación: render headless con pixeles del icono (patrón de `test_image_left_layout`).
- [x] 1.5 Test de layout: la fila suma altura a la card (misma métrica que usa `calc_card_height`); con overflow, la barra "Ver más" ancla DEBAJO de los botones sin solape; toast con botones en la pila → el restack mantiene el gap (regresión del spec `toast-stack`) — verificación: mismos invariantes de `test_layout_consistency` extendidos a la fila.

## 2. Implementación (design D1-D6)

- [x] 2.1 Parseo y filtro de actions en el widget (`__init__`): pares (key, label), fuera `default`, dedup por key, cap en 3, tolerancia a lista impar — verificación: tests 1.1/1.3 en verde.
- [x] 2.2 Fila de botones en `_draw` + hitboxes `_action_rects` (D1/D2): banda bajo el body con segmentos accent al 22%, hover por segmento, ellipsis Pango por label, rects publicadas por botón; `on_click(action_key=None)` y `_on_button_press` consultando la lista antes del click del cuerpo — verificación: tests 1.1/1.2 en verde.
- [x] 2.3 action-icons (D4): hint → `_icon_from_theme(key)` a 16 px + label; sin resolución → label solo — verificación: test 1.4 en verde.
- [x] 2.4 Métrica en la fuente única (D5): `_ACTIONS_ROW_H` + `_ACTIONS_GAP` consumidas por `_draw` y `calc_card_height` por igual — verificación: test 1.5 en verde y suite de layout completa sin cambios inesperados (solo alturas nuevas documentadas).
- [x] 2.5 Daemon + caps (D6): pasar la lista de actions al popup, `_on_action_invoked(nid, action_key=None)`, caps suman `action-icons`, `spec_version` → "1.3" — verificación: `busctl --user call ... GetCapabilities` lista `action-icons` y `GetServerInformation` reporta `1.3`.
- [x] 2.6 Metatest de sensibilidad (convención `test_tests_*.py`): inyectar el bug (click de botón → key default) y verificar que los tests de 1.2 lo detectan — verificación: el metatest pasa porque el contrato se rompe con el bug inyectado.
- [x] 2.7 Suite completa verde — verificación: `.venv/bin/python -m pytest tests/ -q` con 0 failed; conteo antes/después documentado (los tests de alturas que fijan números se actualizan al valor nuevo en el mismo commit).

  **Hecho**: suite **286 passed, 0 failed** (269 → 286: +17 del contrato de actions en `test_acciones.py`). Ajustes de suite existente en el mismo commit: los 16 `on_click=lambda:` de tests pasaron a `lambda key=None:` (firma nueva `on_click(action_key=None)`), y `test_version_constant` fija ahora spec `"1.3"` (era `"1.2"`).

## 3. Verificación en vivo con clientes reales (design D7)

- [x] 3.1 notify-send con acciones (path directo): verificar versión (`notify-send --help` muestra `-A/--action`) y mandar `notify-send -a Test "t" "b" -A settings=Ajustes -A open=Abrir` → el toast muestra los botones y cada click emite su key (observable en el log del daemon/journal) — verificación: botones en pantalla y ActionInvoked correcto por click.

  **Hecho** (verificación viva con el usuario): `notify-send -A settings=Ajustes -A open=Abrir` → toast con los dos botones, click del usuario en "Ajustes" → notify-send recibió **`settings`** en stdout y el toast se cerró solo. Registrado en history (08:49:33, actions `['settings','Ajustes','open','Abrir']`). La verificación cazó DOS bugs que la suite no veía (ver notas del grupo).
- [ ] 3.2 Telegram portable (el misterio del dataset): tras el restart del servicio, mandar un mensaje desde otro dispositivo a la cuenta del usuario y documentar qué llega: ¿aparecen `mail-mark-read`/"Marcar como leída" en el history? (el source dice que sí debería; el dataset muestra `[]`) — verificación: entrada nueva en `history.jsonl` con las actions reales documentadas en la task (resuelve el misterio o genera la task condicional de investigar la versión).
- [x] 3.3 Regresión de navegadores: una notificación de Brave (con `default` + label compuesto "Brave - título") → sin fila visible (solo default) y el click del cuerpo sigue invocando la default — verificación: behavior idéntico al actual, documentado en la task.

  **Hecho** (noti estilo Brave por D-Bus, actions `["default","Abrir sitio"]`, nid 3): el usuario confirmó **sin fila debajo del texto** y franja de descarte visible (persistente); click del cuerpo capturado por dbus-monitor: **`ActionInvoked(uint32 3, "default")`** y cierre limpio.

## 4. Tablero de diseño (knock-on de alturas)

- [x] 4.1 Recrear el worktree de diseño on-demand (`git worktree add ../verdantis-diseno diseno-demos`), `git merge main`, `--self-test` re-deriva las alturas con fila de botones; actualizar el mock que corresponda (toast con botones) + re-exportar manifiesto real y `--comparar` verde — verificación: `--comparar` exit 0; commit `chore:` en `diseno-demos` y `git worktree remove ../verdantis-diseno`.

  **Hecho**: merge de main (28c6fd8) en `diseno-demos` + `--self-test` **VERDE** (23 posiciones coinciden, columnas (240,196)). **NINGÚN mock del tablero lleva actions** → este change aporta cero deltas de geometría (el piso del slot solo afecta toasts CON botones) → no hay mock que actualizar. El `--comparar` da 26 fallos que son del **trabajo paralelo pendiente** (`toast-body-ajuste` del usuario: alturas 112/169 sin re-exportar `manifiesto_real.json` — el propio commit de esa rama dice "la 3.2 quedó suelta"); cero fallos mencionan acciones/botones. NO se absorbe ese arreglo acá: queda como pendiente documentado de ese change. Worktree removido (la rama conserva el merge).

## 5. Release

- [x] 5.1 Bump `VERSION` → 0.9.0 dentro del commit `feat:` en español (primer feat del ciclo) y verificar tras reiniciar con `busctl --user call ... GetServerInformation` → "0.9.0" — verificación: output del busctl con la versión nueva, caps con `action-icons`, spec "1.3", y el bump reportado al usuario.

  **Hecho**: commit `28c6fd8 feat: botones de accion renderizados con action-icons y spec 1.3 (VERSION 0.9.0)`; tras reiniciar: `busctl GetServerInformation` → `ssss "Verdantis" "MoriNo23" "0.9.0" "1.3"` y `GetCapabilities` → `as 7 "actions" "action-icons" "body" "body-markup" "body-hyperlinks" "icon-static" "persistence"`. **Bump MINOR 0.8.2 → 0.9.0 reportado al usuario.**
