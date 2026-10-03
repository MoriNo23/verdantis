# Tasks

## 1. Rama y renames (worktree de testing)

- [x] 1.1 En `../verdantis-testing`, crear la rama `testing/layout-imagen-izquierda` desde main (la `refactor/testing` ya está mergeada, no se reusa) y mover la sesión de trabajo a ese directorio — verificación: `git branch --show-current` en el worktree y `git worktree list` con las 3 entradas.
- [x] 1.2 Renames de terminología en tests: `test_avatar_fallback.py` → `test_image_left_fallback.py`, `test_tests_avatar_fallback.py` → `test_tests_image_left_fallback.py`, referencias `_avatar_pb`/`_AVATAR_W`/`_AVATAR_GAP` → imagen izquierda en todos los archivos de tests, revisando los imports cruzados de los metatests — verificación: `grep -rn "avatar" tests/` sin hits y la suite corre (roja por src con nombres viejos, sin `ImportError` ni errores de colección).

## 2. Tests del contrato nuevo (rojos, uno por escenario del spec de C)

- [x] 2.1 Pila sin solapes (`toast-stack`): expandir/contraer un toast con otros debajo re-llama el reposicionamiento de todos los activos con offsets = alturas reales + gap (spy sobre el restack a nivel manager con popups fake); el re-wrap por hover de un persistente dispara lo mismo; expandir/contraer repetido converge — verificación: cada test FALLA contra el código actual por la razón correcta (el restack on-resize no existe), documentado en el assert.
- [x] 2.2 Slot siempre presente (`toast-imagen-izquierda`): con imagen del tab gana sobre el icono de app; app con `.desktop` exacto → logo de app; nada resuelve → placeholder 80×80 con la inicial (render headless con `render_helpers`: píxeles opacos en el slot y la inicial legible); el slot nunca mide 0 — verificación: cada caso falla hoy (el slot desaparece cuando nada resuelve) y lo documenta el assert.
- [x] 2.3 Texto al top: render con contenido corto → el top de la fila de app coincide (±1 px) con el top del slot; la distancia app→título/body es la misma en todos los casos (muere el gap de 18 de la variante sin imagen) — verificación: falla hoy con el hundido `(row_h − text_h)/2`.
- [x] 2.4 Columna única: `_eff_text_width` = 240 siempre (196 en persistente con hover); body de un toast con placeholder wrappea igual que uno con imagen real; la barra "Ver más" aterriza a la misma altura relativa en ambos — verificación: falla hoy con 332/288; actualizar los tests existentes que fijan las columnas viejas (`test_action_zones`, `test_franja_hover`).

## 3. Inventario del rojo y entrega

- [x] 3.1 Inventario del rojo documentado: corrida completa de la suite listando cada test que falla y la razón (mapeada al requisito del spec de C que codifica) — verificación: cada fallo del inventario corresponde a un escenario del spec, sin falsos positivos (imports/colección); es el artefacto que habilita a C a empezar.
- [x] 3.2 Commit `test:` en español en la rama con el mensaje que declara que la suite está ROJA por diseño hasta que `layout-imagen-izquierda` la vuelva verde — verificación: `git log -1` en `testing/layout-imagen-izquierda` y la rama queda lista para el merge de C (task 1.1 de ese change).

---

# Inventario del rojo (task 3.1)

Corrida de la rama `testing/layout-imagen-izquierda` contra el código actual
(`main` = 332e2c0, la rama no toca `src/`):

```
.venv/bin/python -m pytest tests/ -q   →  28 failed, 218 passed (246 recogidos), 0 errores
```

**Sin falsos positivos**: ningún error de colección ni `ImportError`; los 28
fallos son asserts (o el `AttributeError` del rename, que es el rojo
esperado de la task 1.2 y lo describe la design D3). Los 28 mapean 1:1 con un
requisito del spec de C.

## G1 — RENAME: el slot todavía se llama `_avatar_pb` (10 tests)

Razón: `AttributeError: 'NotificationWidget' object has no attribute
'_image_left_pb'`. Es el rojo que la task 1.2 pide (los tests ya usan la
terminología nueva; falta el rename de `src`, task 4.1 de C / D5).

| Test | Requisito que codifica |
| --- | --- |
| `test_image_left_fallback.py::test_image_left_falls_back_to_desktop_icon` | "La imagen izquierda siempre está presente" (cadena, eslabón 2) |
| `test_image_left_fallback.py::test_image_left_fallback_pwa_youtube` | ídem (match exacto de Name en PWAs) |
| `test_image_left_fallback.py::test_image_left_sender_icon_beats_fallback` | "La imagen de la notificación gana siempre" |
| `test_image_left_fallback.py::test_image_left_fallback_image_data_beats_desktop` | ídem (image-data) |
| `test_image_left_fallback.py::test_image_left_fallback_unknown_app_placeholder` | "Nada resuelve" → placeholder 80×80 (**además** G3) |
| `test_icon_resolution.py::test_notificationwidget_image_left_falls_back_without_sender_image` | cadena, eslabón 2 (+ píxel de procedencia) |
| `test_icon_resolution.py::test_notificationwidget_placeholder_slot_when_nothing_resolves` | "Nada resuelve" → placeholder (**además** G3) |
| `test_icon_resolution.py::test_imagedata_becomes_image_left_tab_icon` | image-data → slot, no banner |
| `test_tests_image_left_fallback.py::test_metatest_image_left_test_detects_missing_fallback` | metatest de sensibilidad del rename |
| `test_tests_icon_resolution.py::test_buggy_version_breaks_resolution` | metatest: el bug no puede dejar el slot con el icono de la app |

## G2 — COLUMNA ÚNICA 240 / 196 con hover (7 tests)

Razón: hoy `_eff_text_width()` devuelve 332 (288 con franja) cuando no hay slot
resuelto. Requisito: "Columna de texto única" (D4) + `toast-franja-descarte`
("Sin hover el texto del persistente usa el ancho completo" = 240).

| Test | Razón medida |
| --- | --- |
| `test_action_zones.py::test_persistent_text_width_reserves_strip_only_on_hover` | `332 ≠ 240` |
| `test_action_zones.py::test_eff_text_width_shrinks_for_persistent` | `332 ≠ 240` |
| `test_franja_hover.py::test_con_hover_el_texto_re_wrappea_a_196` | `332/288 ≠ 240/196` |
| `test_tests_franja_hover.py::test_metatest_bug_detecta_la_reserva_permanente` | el metatest fija la columna de hover en 196 |
| `test_tests_franja_hover.py::test_metatest_la_version_real_distingue_los_dos_estados` | ídem (240 → 196) |
| `test_image_left_layout.py::test_columna_unica_240_y_196_con_hover` | `332 ≠ 240` |
| `test_image_left_layout.py::test_el_body_wrapea_igual_con_placeholder_que_con_imagen` | `240 vs 332` + alto 152 vs 170 (fuentes 11/13 sin unificar) |
| `test_image_left_layout.py::test_la_barra_ver_mas_aterriza_igual` | barra en `(14,128,346,156)` vs `(14,102,346,130)` |

## G3 — SLOT SIEMPRE PRESENTE (placeholder, D2) (2 tests)

Razón: con nada resuelto el slot queda en `None` y el layout salta a la
variante ancha. Requisito: "La imagen izquierda siempre está presente",
scenario "Nada resuelve".

| Test | Razón medida |
| --- | --- |
| `test_image_left_layout.py::test_nada_resuelve_cae_al_placeholder_con_la_inicial` | `slot is None` (y la columna es 332) |
| `test_image_left_layout.py::test_el_slot_nunca_queda_vacio` | sin tinta en la caja del slot (`y=None`) |

## G4 — TEXTO AL TOP DEL SLOT (D3) (2 tests)

Razón: `ty = pad + (row_h − text_h) / 2` hunde el bloque de texto. Requisito:
"El bloque de texto arranca al top de la imagen izquierda".

| Test | Razón medida |
| --- | --- |
| `test_image_left_layout.py::test_la_fila_de_app_arranca_al_top_del_slot` | fila de app en y=23, slot en y=15 (Δ=8 px > 1) |
| `test_image_left_layout.py::test_sin_respiro_de_la_variante_sin_imagen` | distancias `{imagen: 27, logo de app: 27, placeholder: 45}` |

## G5 — MUERE EL RESPIRO DEL HR (D4) (1 test)

| Test | Razón medida |
| --- | --- |
| `test_layout_consistency.py::test_rows_above_body_single_source` | `60 ≠ 42` (el +18 condicional de `has_avatar`) |

## G6 — PILA SIN SOLAPES (D1, spec `toast-stack`) (5 tests)

Razón: `set_stack_margin` sólo se llama al mostrar y al cerrar; el camino
`on_resize` redimensiona la propia ventana y no mueve a los demás.

| Test | Razón medida |
| --- | --- |
| `test_stack_reflow.py::test_expandir_reposiciona_todos_los_activos` | 0 reposicionamientos al expandir |
| `test_stack_reflow.py::test_offsets_de_alturas_reales_mantienen_el_gap` | márgenes `[16,136,256]` con alturas reales `[566,152,108]`; el spec pide `[16,594,758]` |
| `test_stack_reflow.py::test_contraer_devuelve_el_espacio` | al expandir, los de abajo no se mueven |
| `test_stack_reflow.py::test_el_rewrap_por_hover_tambien_reflowea` | 0 reposicionamientos al re-wrappear por hover |
| `test_stack_reflow.py::test_expandir_y_contraer_repetido_converge` | ciclo 0 sin reposicionamiento |

## Evidencia de satisfiabilidad (no forma parte del commit)

Para descartar que los tests fueran imposibles de poner verdes, se aplicó una
simulación **temporal y descartada** de D1–D5 sobre `src/` en este worktree
(placeholder 80 en la cadena, columna única 240/196, `ty = pad`, sin `_HR_GAP`,
rename `_image_left_pb`, y el wiring del restack on-resize con offsets
acumulados): **246 passed, 0 failed**. Después se revirtió `src/` con
`git checkout -- src/`; la rama no toca `src/` (verificable con
`git diff main --stat -- src/`, vacío).

## Notas de coordinación para C

- **Shims tolerantes a la firma**: `test_layout_consistency._rows` y
  `test_action_zones._calc_card_height` pasan el 3er argumento / el kwarg
  `has_avatar` si la firma lo acepta y reintentan sin él si no (un `TypeError`
  que no sea de firma se propaga). Sirven para que el rojo sea el del VALOR y
  no el de una firma que cambió: si C borra el parámetro, los tests siguen
  verdes igual.
- **Accesor tolerante al nombre**: `test_image_left_layout._slot_pb` acepta
  `_image_left_pb` o `_avatar_pb`. Los tests miden el contrato (el slot existe,
  mide 80, dibuja la tinta correcta); el rename sigue forzado por
  `test_image_left_fallback.py`, que sí usa el nombre nuevo.
- **Tests existentes actualizados** (no borrados) porque fijaban el contrato
  viejo: columnas 332/288 → 240/196 (`test_action_zones`,
  `test_franja_hover`, `test_tests_franja_hover`), el +18 del HR
  (`test_layout_consistency`), `test_franja_hover.SHORT` acortada a `"Una
  linea corta."` (la anterior ya wrappeaba a 2 líneas en la columna de 196, y el
  test de la franja exige un cuerpo que NO re-wrappee), y
  `test_placeholder_icono._region_texto` empieza ahora después del slot de 80 px
  (si no, el placeholder y el logo inyectado se comparan como si fueran texto).
- **Excepción de terminología**: `test_history_store.py` conserva
  `avatar_source` / `avatar_file`. Son claves de PERSISTENCIA (las escribe
  `verdantis_daemon`, las lee el dashboard y nombran `n<id>_avatar.png` en
  disco), no vocabulario del layout: el mapa de renames de D5 no las cubre y
  renombrarlas dejaría esos tests rojos por un rename de esquema que C no tiene
  en su lista de tareas. El resto del término "avatar" desaparece de `tests/`.