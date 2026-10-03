# Proposal — Limpiar el repo y separar diseño/testing en worktrees

## Why

El repo acumuló peso muerto verificable: 5.2 MB de imágenes en `assets/` sin una sola referencia en código/docs, cuatro archivos de tests que verifican diseños o decisiones que ya no existen (el pill 28×28 reemplazado por la franja de 44 px, la migración a uv bloqueada, el showcase del pill viejo, un espejo manual del render), un `pyproject.toml` que solo configura mutmut (sin uso desde agosto), basura de disco de QA de agosto, y una sección de AGENTS.md que exige 7 skills borradas en c7578b7. Además, `DISEÑO-DEMOS/` (496 K, untracked) mezcla dos workstreams en el checkout principal, y la suite tiene duplicación (dos suites paralelas del mismo feature de dedup, un test "de ejemplo"). Ahora es el momento: el árbol está limpio tras 0.7.0 y la suite verde en 240.

## What Changes

- **Limpieza de disco** (untracked/ignored, sin commits): `mutants/`, `render_out/` (se regenera en cada corrida de la suite), `QA_*.md`/`QA_*.log`, `E2E_VERIFICATION.md`, `tests/qa_size_test.py`, `.pytest_cache/`, `__pycache__/`. **No se toca** `verdantis-logo` (untracked: borrarlo sería permanente y es el logo del proyecto) ni `.venv/`.
- **Borrados tracked** (reversibles por git): `assets/` (23 archivos, 5.2 MB, cero referencias), `tests/test_uv_migration.py` (nunca corre; documenta la decisión bloqueada que ya vive en AGENTS), `tests/qa_verify_redline_offscreen.py` (verifica el pill 28×28 que no existe desde v0.4.0), `tests/render_close_button.py` (espejo manual de `_draw` que se pudrió con los rediseños), `tests/showcase-hover-close.html` (showcase del pill viejo; solo lo cita un docstring histórico), `pyproject.toml` (solo contiene `[tool.mutmut]`; los metatests de sensibilidad cubren esa función hoy).
- **AGENTS.md**: fuera la sección "Skills — stack GTK3/Wayland (CARGA OBLIGATORIA)" (7 skills inexistentes desde c7578b7; se conserva la sección de `ydotool-uinput`), fuera `--ignore=tests/test_uv_migration.py` del comando de suite y las menciones al test uv, nota de que el validador del tablero corre desde el worktree de diseño.
- **Worktree de diseño**: rama `diseno-demos` basada en main (repo completo) en `../verdantis-diseno`; `DISEÑO-DEMOS/` se commitea ahí y desaparece del checkout principal. Pre-movimiento: archivar `handoff-diseno-toast` en su propio root (está completo: 4/4 artefactos, tasks 15/15 `[x]`).
- **Worktree de testing**: rama `refactor/testing` en `../verdantis-testing`: fusión de `test_dedup.py` + `test_notify_dedup.py` (dos suites del mismo feature), fold de `test_real_notification.py` (test "de EJEMPLO") dentro de `test_e2e_real.py`, consolidación del preámbulo env/`sys.path` en `conftest.py` (que ya es el dueño del `GDK_BACKEND`). Merge a main con la suite verde.
- **Se mantienen** (con razón, no por inercia): metatests `test_tests_*` (convención del repo), `qa_sticky_notifications.py` (herramienta manual para mandar persistentes), `fixtures/notify-tester` (fuente de la página de test del 8766), `test_e2e_real.py` (scheduler GLib real + timing).
- `skip_specs: true`: todo esto es higiene/tooling/docs — el comportamiento observable del daemon no cambia, así que no hay deltas de specs.
- Commits en español conventional (`chore:` para limpieza, `test:` para el refactor); **sin bump de versión** (`chore`/`test` no bumpean).
- **BREAKING**: ninguno — `src/` no se toca; la suite sigue verde en cada paso (240 → ~230 tests tras las fusiones, conteo documentado).

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

(ninguna — el cambio declara `skip_specs: true` en `.openspec.yaml`: no hay cambio de comportamiento a nivel specs)

## Impact

- **git**: 2 ramas nuevas (`diseno-demos`, `refactor/testing`), 2 worktrees (`../verdantis-diseno`, `../verdantis-testing`), primer commit de `DISEÑO-DEMOS/` en su rama; el checkout principal queda sin esa carpeta.
- **`DISEÑO-DEMOS/openspec`**: archivo del change `handoff-diseno-toast` (sync de su delta a sus specs propios + move a archive) — ocurre dentro de su root, antes del movimiento.
- **`tests/`**: ~6 archivos menos y los preámbulos repetidos consolidados; el validador del tablero sigue andando porque la rama de diseño incluye `src/` (importa `wayland_popup.py` con `RAIZ = ../../`).
- **AGENTS.md, `pyproject.toml`** (eliminado), `assets/` (eliminado).
- **`src/` sin cambios** — el daemon, la API DBus y el servicio no se tocan; sin restart ni bump.
