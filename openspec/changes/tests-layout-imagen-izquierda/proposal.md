# Proposal — Tests del contrato de imagen izquierda y pila (TDD, worktree de testing)

## Why

El contrato del change `layout-imagen-izquierda` (slot siempre presente, texto alineado al top, columna única, pila sin solapes, rename de terminología) necesita sus tests **rojos antes de implementar** — es la convención TDD del repo. Este change los escribe y verifica en el worktree de testing, en una rama propia que **no se mergea a main** hasta que `layout-imagen-izquierda` esté implementado y la suite vuelva verde.

## What Changes

- Rama nueva `testing/layout-imagen-izquierda` en el worktree `../verdantis-testing` (la `refactor/testing` ya cumplió su ciclo y quedó mergeada).
- Tests NUEVOS (rojos contra el código actual) para cada requisito del contrato:
  - **Pila sin solapes**: expandir/contraer un toast con otros debajo mantiene el gap (sin solape); el re-wrap por hover de un persistente también re-flowea a los de abajo.
  - **Slot siempre presente**: notificación con imagen → esa imagen gana; app con `.desktop`/tema → icono de app; nada resuelve → placeholder 80×80 con la inicial; el slot nunca desaparece.
  - **Texto alineado al top**: el top de la fila de app coincide con el top del slot (±1 px), sin el hundido de `(row_h − text_h)/2`.
  - **Columna única**: body de un toast sin imagen resuelta wrappea a 240 px igual que uno con imagen; persistente con hover → 196 px.
  - **Barra "Ver más" uniforme**: misma posición relativa con imagen real, icono de app o placeholder.
- Tests EXISTENTES actualizados al contrato nuevo: renombrado de identificadores/archivos (`test_avatar_fallback.py` → `test_image_left_fallback.py` + su metatest `test_tests_avatar_fallback.py`), referencias a `_avatar_pb`/`_AVATAR_W` → imagen izquierda, alturas/columnas esperadas actualizadas (332/288 mueren).
- Inventario del rojo documentado en la task: qué tests fallan, por qué, y confirmación de que fallan **por las razones correctas** (no por imports rotos ni bugs del test).
- La suite de la rama queda ROJA por diseño — main no la recibe hasta que el change C la vuelva verde.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

(ninguna — este change declara `skip_specs: true`: es trabajo de tests; los specs de producto los define y lleva `layout-imagen-izquierda`)

## Impact

- `tests/` en la rama `testing/layout-imagen-izquierda` (worktree de testing): archivos nuevos + renames + actualizaciones de contratos existentes.
- Sin cambios en `src/` — este change no implementa.
- Coordinación: `layout-imagen-izquierda` (main) mergea esta rama como primer paso de su implementación y la vuelve verde; `git worktree list` sigue con las 3 entradas.
- Sin bump de versión (`test:` no bumpea).
