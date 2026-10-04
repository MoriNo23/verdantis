# Tasks

## 1. Tests rojos del contrato (spec `toast-body-colapso`)

- [x] 1.1 Test "body de exactamente 2 líneas se muestra completo": construir un body que wrappee a exactamente 2 líneas (medido con `_count_body_lines` a la columna única de 240) y verificar por render headless que las 2 líneas se dibujan completas, sin "..." y sin `_expand_rect` — verificación: el test FALLA contra el código actual (hoy dibuja 1 línea + ellipsis, el caso ilegible reportado) y el assert nombra el requisito.
- [x] 1.2 Test "con overflow el ellipsis cae al final de la tercera línea": body de ≥6 líneas renderizado colapsado → medir por píxeles (o por líneas del layout interno) que se dibujan exactamente 3 líneas y que el "..." queda al final de la tercera (la altura del body dibujado = 3 × altura real de línea, no 2) — verificación: falla hoy con 2 líneas + "..." tras la segunda.
- [x] 1.3 Test de coherencia medición/dibujado: para un body con overflow, la altura que la card reserva para el body (`calc_card_height`/`desired_height`) coincide exactamente con lo dibujado (la barra "Ver más" ancla sin franja vacía ni solape) — verificación: cubre el scenario "Sin hueco ni solape" del spec; además corre con `font_scale` 0.85 y 1.0 (scenario de escala).

## 2. Fix mínimo (design D1/D2)

- [x] 2.1 Reemplazar la heurística `fs × 1.6` por el presupuesto medido en las dos funciones gemelas: `_body_metrics` (l.385) y `_draw_text` (l.901) usan `line_h = layout.get_line_readonly(0).get_pixel_extents()[1].height` y `set_height(int(max_lines * line_h) * Pango_SCALE)` — verificación: los tests de 1.x pasan en verde y `grep -n "1.6" src/wayland_popup.py` no queda con la heurística del cap.
- [x] 2.2 Metatest de sensibilidad (convención `test_tests_*.py`): inyectar la versión bugueada (la heurística `fs × 1.6` restaurada) y verificar que los tests de 1.x/2.1 la detectan — verificación: el metatest pasa porque el contrato se rompe con el bug inyectado.
- [x] 2.3 Suite completa verde con el comando documentado — verificación: `.venv/bin/python -m pytest tests/ -q` con 0 failed; conteo antes/después documentado (los tests de layout que fijan alturas de card con overflow se actualizan al valor exacto nuevo en el mismo commit).

## 2b. Ajuste al margen (spec `toast-body-ajuste`, design D4bis)

- [x] 2b.1 Test "el renglón se justifica hasta el margen": el hueco del corte
  (23-43 px medidos en vivo) no debe quedar — criterio calibrado por la propia
  línea (el hueco final no puede ser más ancho que el espacio más ancho del
  mismo renglón, porque el espacio del corte no se estira igual y medir contra
  el margen exacto fallaría por antialiasing). Verificación: falla con el
  código actual (hueco de 23 px a font 11 y 13 px a font 9) y en las dos
  escalas (`font_scale` 0.85 y 1.0).
- [x] 2b.2 Test de que el hueco existía de verdad (premisa): la referencia sin
  `set_justify` tiene un renglón con ≥20 px de hueco, para que el assert del
  margen no sea un placebo.
- [x] 2b.3 Implementación: `layout.set_justify(True)` en las dos gemelas
  (`_body_metrics` y `_draw_text`), wrap sigue siendo `WORD_CHAR`. La misma
  línea en las dos, como el presupuesto.
- [x] 2b.4 Metatest de sensibilidad (`test_tests_body_wrap.py`): inyecta la
  versión sin `set_justify` (misma técnica de recompilar el fuente sustituyendo
  una línea) y verifica que el contrato queda en rojo; más el smoke de que la
  versión real sí justifica.
- [x] 2b.5 Verificación en vivo: el body de xat se ve con los 3 renglones
  llenando el margen, sin palabras partidas y con el "..." al final del tercero.

## 3. Tablero de diseño (design D4, knock-on de alturas)

- [x] 3.1 Recrear el worktree de diseño on-demand (`git worktree add ../verdantis-diseno diseno-demos`), `git merge main`, y re-derivar: `python3 DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py --self-test` regenera `manifiesto_esperado.json` con la altura nueva del caso "body largo" (3 líneas reales + barra) — verificación: self-test en verde con las alturas re-derivadas impresas.
- [ ] 3.2 Actualizar el mock "04 · Body largo + Ver más" del documento Lunacy a la altura re-derivada, re-exportar `manifiesto_real.json` y `--comparar` verde capa por capa — verificación: `--comparar` exit 0; commit `chore:` en `diseno-demos` y `git worktree remove ../verdantis-diseno` (la rama queda). **TRASPASADA al change `actualizar-tablero-ellipsis-body`** (rama `diseno-demos`): el agente perdió a mitad del trabajo el servidor MCP de Lunacy —las 14 tools salieron del catálogo y los procesos `Lunacy -mcp` murieron—, sin poder editar el `.free` ni re-exportar el manifiesto. Lo aplicado de esta tarea (worktree + merge + `--self-test` verde + `TABLA_DISSENY` refrescada + `manifiesto_esperado.json` regenerado) está en el commit `7b4c7df` de `diseno-demos`; lo que falta es la edición del documento, que sigue con la geometría vieja (`--comparar` en rojo con 26 fallos nombrados, todos listados en el handoff de ese change).

## 4. Release y verificación en vivo

- [x] 4.1 Bump `VERSION` → 0.8.1 dentro del commit `fix:` en español y verificación en vivo tras reiniciar el servicio: una noti con body de 2 líneas se lee completa (sin "..." suelto) y una noti larga muestra 3 líneas con el "..." al final de la tercera — verificación: `busctl --user call ... GetServerInformation` → "0.8.1" y comportamiento observado en pantalla (dataset de `history.jsonl` para elegir bodies reales de cada caso). *(Hecho: bump a 0.8.1 en `c8649b6`; tras reiniciar el servicio `GetServerInformation` → `"0.8.1"`; en vivo el body real de ProtonVPN (`Conexión «pvpn-routed-killswitch» activada.`, 2 líneas) se leyó completo sin "..." ni botón "Ver más", y el de xat mostró 3 renglones con el "..." al final del tercero. El wrap justificado de 2b.5 subió la versión a 0.8.2 después, en su propio commit.)*
