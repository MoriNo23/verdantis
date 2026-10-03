# Design

## Context

Convención TDD del repo: test rojo primero, fix después, suite verde al final. El contrato nuevo vive en los specs del change `layout-imagen-izquierda` (C); este change lo codifica en tests ANTES de que C exista, en el worktree de testing. La rama `refactor/testing` ya cumplió su ciclo (mergeada en 0.7.0) — no se reutiliza. Tests actuales que fijan el contrato viejo y van a cambiar: los asserts de columna 332/240/288 y 196 (`test_action_zones`, `test_franja_hover`), `test_avatar_fallback.py` + su metatest (identificadores "avatar"), `test_expand_layout`, `test_layout_consistency`.

## Goals / Non-Goals

**Goals:**

- Una rama `testing/layout-imagen-izquierda` con los tests del contrato nuevo fallando **por las razones correctas**, lista para que C la mergee.
- Cero pérdida de cobertura: cada test existente que fijaba lo viejo se actualiza al contrato nuevo (con rename de terminología), no se borra.
- Inventario del rojo documentado en la task: qué falla y por qué — es la "verificación" que habilita a C a empezar.

**Non-Goals:**

- Sin cambios en `src/` — este change no implementa.
- Sin merge a main — la rama la mergea C como primer paso.
- Sin specs propios (`skip_specs: true`): el contrato de producto lo lleva C.

## Decisions

### D1 — Rama nueva por ciclo de trabajo

`git worktree add`-style: en `../verdantis-testing` (ya existente) se crea `git checkout -b testing/layout-imagen-izquierda` desde main. *Alternativa rechazada*: reusar `refactor/testing` — ya está mergeada; una rama por ciclo mantiene el historial limpio y el review acotado.

### D2 — Un test por escenario del spec de C, con asserts que nombren el requisito

Los tests nuevos se mapean 1:1 con los scenarios de `toast-imagen-izquierda` y `toast-stack`: presencia/cadena del slot, top-alineación (±1 px, medido sobre render headless con `render_helpers`), columna única (wrap a 240/196 con `count_body_lines`/`_eff_text_width`), barra uniforme (render comparativo), restack on-resize (a nivel manager: expandir/contraer re-llama el reposicionamiento de todos los activos, con offsets = suma de alturas reales + gap — los popups fake registran las llamadas, headless). Los asserts citan el requisito en el mensaje para que el rojo sea auto-explicativo.

### D3 — Renames primero, tests nuevos después

Los renames de terminología (`test_avatar_fallback.py` → `test_image_left_fallback.py`, metatest `test_tests_avatar_fallback.py` → `test_tests_image_left_fallback.py`, `_avatar_pb` → `_image_left_pb` en todos los tests) se hacen primero y la suite se corre: el rojo de esa pasada es el esperado (src aún usa los nombres viejos). Después se agregan los tests nuevos del contrato. *Cuidado conocido*: los metatests importan de otros módulos de test (p. ej. `test_tests_franja_hover` importa de `test_franja_hover`) — los renames revisan esos imports.

### D4 — El rojo es deliberado y queda documentado

La suite de la rama NO pasa hasta que C implemente (así se diseñó). La task final documenta el inventario: lista de tests que fallan y la razón de cada uno (confirmación de que fallan por el contrato, no por imports rotos). Ese inventario es el artefacto de "verificación" que habilita a C.

## Risks / Trade-offs

- [Rama roja confunde a un tercero que la corra] → el proposal/design lo declara; el nombre de la rama y el mensaje del commit lo dicen explícitamente.
- [Un test nuevo pasa sin implementación (placebo)] → cada test nuevo se escribe contra el escenario del spec y se verifica que FALLA contra el código actual antes de cerrar la task (metatest de sensibilidad donde aporte: el repo ya tiene la convención `test_tests_*`).
- [Renames con renombre de imports cruzados] → pasada de grep por imports de tests tras el rename, suite corre para detectar `ImportError`.

## Migration Plan

1. Crear la rama en el worktree de testing (desde main).
2. Renames de terminología + corrida (rojo esperado por nombres viejos en src).
3. Tests nuevos por escenario + verificación individual del rojo correcto.
4. Inventario del rojo documentado + commit `test:` en la rama.
5. Entrega: C mergea la rama; este change se archiva cuando C está verde (la suite verde de main incluye estos tests).

## Open Questions

- Ninguna material. La mecánica fina del test de restack (spy de `set_stack_margin` a nivel manager) puede ajustarse durante la ejecución sin cambiar el alcance.
