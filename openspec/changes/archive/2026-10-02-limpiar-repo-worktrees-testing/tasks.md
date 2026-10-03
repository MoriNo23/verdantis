# Tasks

## 1. Worktree de diseño (rama diseno-demos)

- [x] 1.1 Archivar `handoff-diseno-toast` en su propio root (`DISEÑO-DEMOS/openspec`), siguiendo el workflow de archivo: sync del delta `specs/tablero-diseno/spec.md` contra el main spec existente y move a `archive/2026-10-02-handoff-diseno-toast` — verificación: `openspec list` sin changes activos corriendo desde `DISEÑO-DEMOS/`, y `openspec validate --specs` verde ahí (specs `diseno-toast` y `tablero-diseno`).
- [x] 1.2 `git worktree add ../verdantis-diseno -b diseno-demos` — verificación: `git worktree list` muestra las dos entradas y la rama `diseno-demos` apunta a main.
- [x] 1.3 Mover `DISEÑO-DEMOS/` completo (untitled.free, herramientas/, openspec/ ya archivado, .opencode/) a `../verdantis-diseno/DISEÑO-DEMOS/` y commitearlo en la rama `diseno-demos` con `chore:` en español — verificación: `git status --short` en main ya no lista `DISEÑO-DEMOS/`, y `python3 DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py --self-test` corre DESDE `../verdantis-diseno` en verde (exit 0, xs=[40, 440, 840], columnas (332, 240, 288)).

## 2. Limpieza de disco en main (untracked/ignored, sin commits)

- [x] 2.1 Borrar de disco: `mutants/`, `render_out/`, `QA_REDLINE_REPORT_t3168d84a.md`, `QA_REGRESSION_RAWLOG_t467fbbb3.log`, `QA_REGRESSION_REPORT_t467fbbb3.md`, `QA_STAGGER_REPORT_t_fb4b5783.md`, `E2E_VERIFICATION.md`, `tests/qa_size_test.py`, `.pytest_cache/`, `src/__pycache__/`, `tests/__pycache__/` — verificación: `git status --ignored --short` queda solo con `.venv/`, `verdantis-logo` y lo que la suite regenere al correr; **no tocar** `verdantis-logo` ni `.venv/` (untracked = irreversible).

## 3. Limpieza tracked + AGENTS.md (commit chore en main)

- [x] 3.1 `git rm -r assets/` y `git rm tests/test_uv_migration.py tests/qa_verify_redline_offscreen.py tests/render_close_button.py tests/showcase-hover-close.html pyproject.toml`; actualizar el docstring histórico de `test_hover_close.py` que cita el showcase HTML — verificación: suite completa verde con el comando simplificado `.venv/bin/python -m pytest tests/ -q` (sin `--ignore`), y grep de `showcase-hover|test_uv_migration|qa_verify_redline|render_close_button` sin hits vivos en src/, tests/ ni AGENTS.md.

  **Notas**: la cita al showcase solo existía en la copia de `mutants/` (borrada en 2.1) — el `test_hover_close.py` vivo ya no la tiene. El borrado de `render_out/` expuso un bug latente: `test_close_render.py` escribía PNGs asumiendo el dir existente (fallaría igual en un clone fresco) — fix mínimo con `os.makedirs(..., exist_ok=True)`, mismo patrón que `test_e2e_real.py`. Suite: **240 passed** con `.venv/bin/python -m pytest tests/ -q` (los borrados no estaban colectados: uv siempre con `--ignore`, showcase/qa sin prefijo `test_`).
- [x] 3.2 AGENTS.md: eliminar la sección "Skills — stack GTK3/Wayland (CARGA OBLIGATORIA)" completa (las 7 skills no existen desde c7578b7; conservar la sección "Skill — input" de ydotool), quitar `--ignore=tests/test_uv_migration.py` del comando de suite y las menciones al test uv (la decisión bloqueada de uv queda como nota histórica sin referencia a archivo), agregar una línea indicando que el validador del tablero corre desde el worktree `../verdantis-diseno` — verificación: grep en AGENTS.md sin `CARGA OBLIGATORIA|py-313-pygobject-runtime|test_uv_migration` y la suite corre con el comando documentado.
- [x] 3.3 Commit `chore:` en español (p. ej. "chore: saca assets sin referencias, tests muertos y config de mutmut; AGENTS sin skills borradas") — verificación: `git log -1 --stat` con los 29 paths borrados + AGENTS.md y `git status --short` limpio.

  **Hecho**: commit `9af7705` — 30 archivos (28 borrados + AGENTS.md + el fix de `test_close_render.py`, −876 líneas). El conteo de la task decía "29 paths": son 28 borrados (23 assets + 4 tests + pyproject) + 2 modificados. `git status --short` queda solo con el change activo de openspec (se commitea al archivar).

## 4. Worktree de testing (rama refactor/testing)

- [x] 4.1 `git worktree add ../verdantis-testing -b refactor/testing` y mover la sesión de trabajo a ese directorio — verificación: `git worktree list` con las tres entradas; los tests corren desde ahí con el venv del checkout principal (`.venv` es gitignored y no viaja al worktree).
- [x] 4.2 Fusión dedup (design D5): inventario escrito de los casos de `test_dedup.py` y `test_notify_dedup.py`, portar todo caso único de `test_notify_dedup.py` a `test_dedup.py` (su docstring de reglas se mantiene como fuente), borrar `test_notify_dedup.py` — verificación: cada caso del inventario vive en el archivo final, suite verde, conteo de tests antes/después documentado en la task.

  **Inventario** (8 de notify_dedup): 6 duplicados (normalización case/whitespace, sender excluido, contenido distinto, suprimida-antes-de-mostrar, contenido distinto mostrado, fuera de ventana) ya cubiertos por tests equivalentes del survivor; 2 **únicos portados**: `test_duplicate_active_is_replaced_not_stacked` (reemplazo sobre toast YA activa) y `test_duplicate_suppressed_within_window_then_allowed_after` (secuencia con estado compartido). Sin referencias externas a ninguno de los dos archivos. Conteo: 240 → **234 passed** (−8 +2).
- [x] 4.3 Fold de `test_real_notification.py` (design D6): inventario de aserciones, portar las únicas del payload realista de navegador (url hint, banner, accent, kwargs reales) a `test_e2e_real.py`, borrar el test de ejemplo — verificación: las propiedades del payload siguen cubiertas en `test_e2e_real.py`, suite verde.

  **Inventario** (3 tests del ejemplo): (1) `manager_builds_popup` — los hints individuales ya estaban cubiertos por separado (desktop-entry/x-kde-urls en `test_dbus_contract`, urgency en `test_spec_gaps`, duration en `test_expire_timeout`), pero el **payload completo en un solo flujo** era único → portado como `test_e2e_realistic_browser_payload_flow` (recording `_show_popup` para asertar los kwargs reales del daemon + la info parseada); (2) `renders_and_expands` — solapa con `test_expand_layout`/`test_layout_consistency`, no portado; (3) `markup_no_crash` — solapa con `test_body_markup` (set_markup + `_extract_markup_url`), no portado. Conteo: 234 → **232 passed** (−3 +1).
- [x] 4.4 Consolidación de preámbulos (design D7): mover el `sys.path.insert` hacia `src/` a `conftest.py` (el `GDK_BACKEND` ya lo decide conftest), eliminar los preámbulos repetidos de los módulos conservando el orden "wayland_popup primero" entre los imports gi de cada módulo — verificación: suite completa verde y `grep -rln "sys.path.insert" tests/` solo en `conftest.py` y los helpers manuales `qa_*`/`render_*` que queden.

  **Notas**: 30 módulos + `render_helpers.py` sueltan el preámbulo (env setdefault + path insert + imports os/sys muertos); `test_version_constant.py` lo CONSERVA (declara que corre aislado) y `qa_sticky_notifications.py` es script manual — ambos fuera del strip por diseño. La v1 del strip colapsaba blank lines globalmente y rompía el estilo de 2 líneas entre defs → revertida y rehecha quirúrgicamente (solo las 2 líneas objetivo + imports huérfanos + un tidy puntual de `\n\n\nimport`→`\n\nimport`). AGENTS.md actualizado: conftest es el dueño documentado del env+path. Suite: **232 passed** (sin cambio de conteo, como corresponde a un refactor de preámbulo).
- [x] 4.5 Suite completa verde en el worktree y commit `test:` en español en la rama — verificación: `.venv` del principal + `pytest tests/ -q` con 0 failed, conteo final documentado en la task.

  **Hecho**: commit `37fa2b8` — suite **232 passed** en el worktree (venv del principal); conteo documentado en el mensaje del commit (240 → 232: dedup −8 +2, ejemplo −3 +1).
- [x] 4.6 Merge de `refactor/testing` a main (la rama parte del main post-chore, sin divergencia de terceros) — verificación: suite verde en main tras el merge, `git log` con el merge/commits, sin conflictos.

  **Hecho**: fast-forward limpio `9af7705` → `37fa2b8` (sin conflictos); suite en main: **232 passed**.

## 5. Cierre

- [x] 5.1 Verificación final: suite completa en main con el comando nuevo, `git status --short` limpio (solo lo regenerable), `git worktree list` con las 3 entradas (main, verdantis-diseno, verdantis-testing) y el conteo final de tests documentado (240 menos lo fusionado en 4.2/4.3) — verificación: 0 failed, estados listados en la task al completarla.

  **Estado final**: suite en main **232 passed** con `.venv/bin/python -m pytest tests/ -q` (240 → 232: dedup −8 +2, ejemplo −3 +1). `git status --short` → solo el change activo de openspec (se commitea al archivar); lo ignorado = caches/`render_out/` regenerados por la suite + `.venv/` + `verdantis-logo` (conservado a propósito). Worktrees: `main` 37fa2b8 · `../verdantis-diseno` cdacdf7 [diseno-demos, con DISEÑO-DEMOS/ trackeado] · `../verdantis-testing` 37fa2b8 [refactor/testing]. Nota: `diseno-demos` arranca de d36e5e3 y `src/` no cambió desde entonces — cuando cambie, `git merge main` en ese worktree y re-validar el tablero.
