# Design

## Context

Ver `proposal.md` (Why/What). Estado actual verificado que condiciona el diseño:

- **El validador del tablero importa el código del daemon**: `DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py` resuelve `RAIZ = ../../` (dos niveles arriba de `herramientas/`) y añade `RAIZ/src` al path para importar `wayland_popup` — la geometría "esperada" se DERIVA de las constantes del código. Cualquier reubicación de `DISEÑO-DEMOS/` que no conserve un `src/` de verdantis a dos niveles rompe el validador.
- **`DISEÑO-DEMOS/` es un root de OpenSpec propio** con su `openspec/config.yaml`, 2 changes archivados y 1 activo (`handoff-diseno-toast`, completo: 4/4 artefactos, tasks 15/15 `[x]`, delta en `specs/tablero-diseno/spec.md`, main specs `diseno-toast` y `tablero-diseno` ya existen ahí). También lleva `.opencode/skills/` con las 6 skills del workflow openspec — viajan con la carpeta.
- **`conftest.py` ya es el dueño del `GDK_BACKEND`**: decide `wayland` si hay `WAYLAND_DISPLAY`, `offscreen` si no. Los `os.environ.setdefault("GDK_BACKEND", "offscreen")` de cada módulo son no-ops cuando conftest ya seteó (corre antes que los módulos). Los `sys.path.insert` sí están repetidos módulo por módulo.
- **Pitfall del orden de import**: importar `wayland_popup` PRIMERO fija Gdk 3.0; un `gi.repository.Gdk` suelto carga 4.0 y crashea. Cualquier consolidación de preámbulos debe respetar el orden de imports DENTRO de cada módulo.
- **`render_out/` se regenera**: tests de la suite escriben PNGs de evidencia ahí (`test_close_x_*.png` se reescribieron en la última corrida) — borrarlo es cosmético.
- **`assets/` está trackeado** (reversible con git); **`verdantis-logo` NO** (untracked + gitignored: borrarlo es permanente).
- **El worktree de diseño necesita branch propio** (git no permite la misma rama en dos worktrees) y hoy no existe ninguno (`git worktree list` → solo main).

## Goals / Non-Goals

**Goals:**

- Checkout principal = solo runtime (`src/`, `tests/`, `openspec/`, docs) — sin la carpeta de diseño, sin basura.
- El validador del tablero sigue corriendo verde sin cambios de código: desde el worktree de diseño.
- Suite verde en CADA paso (main, rama de testing, y tras el merge); sin pérdida de casos de test en las fusiones (inventario antes de borrar).
- Todo lo borrado del árbol tracked es recuperable (`git revert`); lo untracked solo se borra si es regenerable o claramente desechable.

**Non-Goals:**

- No se toca `src/` (ni una línea del daemon) — sin restart del servicio, sin bump de versión.
- No se purgan metatests ni tests vivos: la poda es solo de archivos muertos/obsoletos y duplicación.
- No se decide el destino de `verdantis-logo` (queda donde está, ignorado).
- No se remueven los worktrees al terminar: el de diseño es permanente; el de testing se conserva mientras sirva (removable con `git worktree remove`).

## Decisions

### D1 — Rama de diseño = repo completo basado en main, no orphan

`git worktree add ../verdantis-diseno -b diseno-demos` desde main crea un checkout con TODO el repo (incluido `src/`) en la rama nueva; `DISEÑO-DEMOS/` se commitea ahí. `RAIZ = ../../` del validador resuelve al root del worktree → `src/wayland_popup.py` presente → `--self-test` sigue verde sin tocar una línea. Cuando `src/` cambie en main: `git merge main` dentro del worktree y re-validar. *Alternativa rechazada*: rama huérfana solo con `DISEÑO-DEMOS/` — `RAIZ` dejaría de apuntar a un repo y el validador moriría; además `--comparar` necesita los manifiestos Y el código juntos.

### D2 — Archivar `handoff-diseno-toast` ANTES del movimiento

El change está completo pero sin archivar; moverlo "colgando" deja el root de DISEÑO-DEMOS con un change activo cuyo changeRoot cambia de path. Se archiva primero (workflow de archivo estándar: sync del delta `specs/tablero-diseno/spec.md` contra el main spec existente + move a `archive/2026-10-02-handoff-diseno-toast`), y el movimiento lleva el root ya cerrado. *Alternativa rechazada*: archivar después del move — funciona pero obliga a re-resolver el root desde el path nuevo a mitad de un paso físico.

### D3 — Disciplina tracked vs untracked al borrar

Tracked (`assets/`, 4 archivos de tests, `pyproject.toml`) → `git rm` + commit `chore:` (recuperable). Untracked regenerable o desechable (`mutants/`, `QA_*`, `render_out/`, `qa_size_test.py`, caches) → `rm` directo. Untracked NO regenerable (`verdantis-logo`) → se queda. Los caches (`__pycache__`, `.pytest_cache`) se borran sabiendo que vuelven al correr la suite — es higiene de disco, no una promesa de permanencia.

### D4 — El refactor de tests ocurre en su worktree y mergea a main

Rama `refactor/testing` desde main en `../verdantis-testing`. Todo el trabajo de poda/fusión/consolidación pasa ahí; main solo recibe el resultado final ya verde. Durante el apply, la sesión de trabajo pasa a ese directorio (session_move) y vuelve a main para el merge final. *Alternativa rechazada*: hacerlo directo en main — mezcla la poda (que puede irse de largo) con el tronco, y el usuario pidió worktree explícito.

### D5 — Fusión dedup: sobrevive `test_dedup.py`

`test_dedup.py` (español, documenta las reglas de normalización y mide sobre el pipeline real) absorbe todo caso único de `test_notify_dedup.py` (su patrón de scheduler fake no aporta nada que los metatests y `test_e2e_real` no cubran con el scheduler GLib real). El task exige inventario de casos de ambos archivos ANTES de borrar — nada se pierde silenciosamente. *Alternativa rechazada*: conservar ambos — dos suites del mismo feature divergen en reglas documentadas y ya difieren en lenguaje (es vs en).

### D6 — `test_real_notification.py` se pliega en `test_e2e_real.py`

Es un test "de EJEMPLO" demostrativo (manager→popup→widget con payload realista de Firefox), no un regression test con bug documentado. Sus aserciones únicas (kwargs reales del payload de navegador: url hint, banner, accent) se portan a `test_e2e_real.py`, que ya es el hogar natural del camino end-to-end. Si el inventario no encuentra aserciones únicas, se borra directo. `test_e2e_real.py` se conserva: su scheduler GLib real con timing es el único test de integración temporal de batching/dedup.

### D7 — Consolidación de preámbulos: conftest absorbe env + sys.path

`conftest.py` ya decide el `GDK_BACKEND` (los `setdefault` por módulo son no-ops) — se le suma el `sys.path.insert` hacia `src/` y se eliminan ambos preámbulos de los módulos. La regla "wayland_popup PRIMERO entre los imports gi" NO se toca: es orden de imports dentro de cada módulo, no env. Verificación: suite completa verde (los crashes de Gdk 4.0 serían inmediatos y ruidosos).

### D8 — mutmut fuera: `pyproject.toml` entero + `mutants/`

`pyproject.toml` solo contiene `[tool.mutmut]`; `mutants/` (su output) es del 15 de agosto; no hay CI ni corrida registrada desde entonces; la función "¿el suite detecta bugs inyectados?" la cumplen los metatests de sensibilidad (`test_tests_*.py`, convención desde 3774c62). El binario queda en `.venv` (inerte, sin config). *Alternativa rechazada*: conservarlo "por si vuelve" — es un archivo de configuración muerto que el próximo contribuyente tiene que leer para descubrir que no se usa.

### D9 — AGENTS.md: poda de la sección de skills muertas

La sección "Skills — stack GTK3/Wayland (CARGA OBLIGATORIA)" lista 7 skills que c7578b7 borró — es documentación que miente (hizo perder tiempo real en esta misma sesión). Se elimina completa (incluida la "Regla:"), se conserva la sección de `ydotool-uinput` (viva), se saca `--ignore=tests/test_uv_migration.py` del comando de suite y las menciones al test uv (la decisión bloqueada de uv queda como nota histórica sin referencia a archivo), y se agrega una línea de dónde corre el validador del tablero (worktree de diseño) para que el próximo cambio de layout no lo busque en main.

## Risks / Trade-offs

- [Fusión dedup pierde un caso silenciosamente] → El task exige inventario escrito de casos de ambos archivos antes de borrar + conteo de tests documentado; la suite falla si un caso portado diverge.
- [Consolidación de conftest rompe el orden de import Gdk 3.0] → Solo se mueven env + `sys.path` (ambos previos a cualquier import de módulo); el orden "wayland_popup primero" vive dentro de cada módulo y no se toca; la suite es el detector inmediato.
- [La rama `diseno-demos` diverge de main y el tablero valida contra un src viejo] → Merge periódico de main hacia la rama + correr `--self-test` tras cada merge; el validador es exactamente el que detecta la divergencia código↔tablero.
- [Borrar untracked es irreversible] → Solo se borra lo regenerable o desechable (mutants, QA de agosto, render_out); `verdantis-logo` se preserva explícitamente.
- [El worktree de testing queda huérfano/duplicado tras el merge] → El task de cierre verifica `git worktree list` (3 entradas esperadas) y la suite en main; el worktree se conserva a propósito (D4/Non-Goals).
- [Menos tests = menos red de seguridad] → La poda es de archivos muertos (verifican cosas inexistentes) y duplicados; el conteo final se documenta en el task y la suite sigue verde.

## Migration Plan

1. Archivar `handoff-diseno-toast` en su root (D2).
2. Crear worktree de diseño + mover y commitear `DISEÑO-DEMOS/` ahí (D1).
3. Limpieza de disco en main (D3).
4. Borrados tracked + AGENTS.md en un commit `chore:` en main (D3/D9).
5. Worktree de testing: poda/fusión/consolidación en rama, suite verde, commit `test:`, merge a main (D4–D7).
6. Verificación final en main y conteo documentado.
- Rollback: los borrados tracked se revierten con `git revert` de los commits `chore:`/`test:`; el movimiento de `DISEÑO-DEMOS/` se revierte removiendo el worktree y devolviendo la carpeta (o simplemente `git -C ../verdantis-diseno checkout` — la carpeta es untracked en main, su fuente de verdad pasa a ser la rama `diseno-demos`).

## Open Questions

- Ninguna que bloquee: las cuatro decisiones de la exploración quedaron cerradas con las opciones recomendadas (D1 rama completa, D2–D7 según inventario, D8 mutmut fuera, nombres `../verdantis-diseno` + `../verdantis-testing` con ramas `diseno-demos` y `refactor/testing`). Si al revisar los artefactos querés revirar alguna (p. ej. conservar `test_real_notification.py` como ejemplo vivo), decilo antes del apply — el cambio de decisión solo retoca tasks.md.
