# Tasks

## 1. Tests rojos del contrato (spec `toast-body-colapso`)

- [x] 1.1 Test "body de exactamente 2 líneas se muestra completo": construir un body que wrappee a exactamente 2 líneas (medido con `_count_body_lines` a la columna única de 240) y verificar por render headless que las 2 líneas se dibujan completas, sin "..." y sin `_expand_rect` — verificación: el test FALLA contra el código actual (hoy dibuja 1 línea + ellipsis, el caso ilegible reportado) y el assert nombra el requisito.
- [x] 1.2 Test "con overflow el ellipsis cae al final de la tercera línea": body de ≥6 líneas renderizado colapsado → medir por píxeles (o por líneas del layout interno) que se dibujan exactamente 3 líneas y que el "..." queda al final de la tercera (la altura del body dibujado = 3 × altura real de línea, no 2) — verificación: falla hoy con 2 líneas + "..." tras la segunda.
- [x] 1.3 Test de coherencia medición/dibujado: para un body con overflow, la altura que la card reserva para el body (`calc_card_height`/`desired_height`) coincide exactamente con lo dibujado (la barra "Ver más" ancla sin franja vacía ni solape) — verificación: cubre el scenario "Sin hueco ni solape" del spec; además corre con `font_scale` 0.85 y 1.0 (scenario de escala).

## 2. Fix mínimo (design D1/D2)

- [x] 2.1 Reemplazar la heurística `fs × 1.6` por el presupuesto medido en las dos funciones gemelas: `_body_metrics` (l.385) y `_draw_text` (l.901) usan `line_h = layout.get_line_readonly(0).get_pixel_extents()[1].height` y `set_height(int(max_lines * line_h) * Pango_SCALE)` — verificación: los tests de 1.x pasan en verde y `grep -n "1.6" src/wayland_popup.py` no queda con la heurística del cap.
- [x] 2.2 Metatest de sensibilidad (convención `test_tests_*.py`): inyectar la versión bugueada (la heurística `fs × 1.6` restaurada) y verificar que los tests de 1.x/2.1 la detectan — verificación: el metatest pasa porque el contrato se rompe con el bug inyectado.
- [x] 2.3 Suite completa verde con el comando documentado — verificación: `.venv/bin/python -m pytest tests/ -q` con 0 failed; conteo antes/después documentado (los tests de layout que fijan alturas de card con overflow se actualizan al valor exacto nuevo en el mismo commit).

## 3. Tablero de diseño (design D4, knock-on de alturas)

- [ ] 3.1 Recrear el worktree de diseño on-demand (`git worktree add ../verdantis-diseno diseno-demos`), `git merge main`, y re-derivar: `python3 DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py --self-test` regenera `manifiesto_esperado.json` con la altura nueva del caso "body largo" (3 líneas reales + barra) — verificación: self-test en verde con las alturas re-derivadas impresas.
- [ ] 3.2 Actualizar el mock "04 · Body largo + Ver más" del documento Lunacy a la altura re-derivada, re-exportar `manifiesto_real.json` y `--comparar` verde capa por capa — verificación: `--comparar` exit 0; commit `chore:` en `diseno-demos` y `git worktree remove ../verdantis-diseno` (la rama queda).

## 4. Release y verificación en vivo

- [ ] 4.1 Bump `VERSION` → 0.8.1 dentro del commit `fix:` en español y verificación en vivo tras reiniciar el servicio: una noti con body de 2 líneas se lee completa (sin "..." suelto) y una noti larga muestra 3 líneas con el "..." al final de la tercera — verificación: `busctl --user call ... GetServerInformation` → "0.8.1" y comportamiento observado en pantalla (dataset de `history.jsonl` para elegir bodies reales de cada caso).
