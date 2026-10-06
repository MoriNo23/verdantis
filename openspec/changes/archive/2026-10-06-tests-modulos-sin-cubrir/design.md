# Design

## Context

Los tres módulos al 0% en la tabla de crapper. El criterio para decidir cuáles
se testean y cuál no: **¿el test puede afirmar algo real sobre el
comportamiento, o solo vendría a producir un número?**

| Módulo | Decisión | Por qué |
|---|---|---|
| `verdantis.py` | testear | La decisión de backend y el import perezoso son arquitectura documentada (AGENTS.md), no detalle. |
| `dashboard.py` | testear | Replay reinyecta el avatar persistido y reformatea hints: lógica con reglas. |
| `qt_fallback.py` | NO testear | Su camino es "no hay Wayland". Sin display de Qt solo se puede testear el import, y eso no afirma nada del render. |

## Goals / Non-Goals

**Goals:**
- Que la decisión de backend y el replay del dashboard tengan red de regresión.
- Cubrir el pitfall documentado: "importar PyQt6 al arrancar rompe".

**Non-Goals:**
- No se testea `qt_fallback` (razón arriba, y va en el docstring del test de
  entrada para que el próximo sepa por qué no está).
- No se prueba el HTML del dashboard renderizado (solo que se sirve y con el
  nombre de la app): es un template estático, probarlo con selectores es
  acoplarse al detalle.
- No se arranca el servidor real: se usa el test client de Flask (sin puerto,
  sin thread).

## Decisions

### D1 — Caracterización, no TDD

Estos tests cubren comportamiento EXISTENTE: pasan desde el primer run. No hay
RED que provocar (no hay comportamiento nuevo), y su valor no es probar que el
código hace lo que debería sino que SIGA haciéndolo. Es la misma distinción que
el change `bajar-complejidad-draw` hizo explícita con su fixture de píxeles.

### D2 — Los fakes viven en el test, el src no se toca

El daemon se finge con un objeto con `_manager` (notify/_active/_pending/
history); QApplication se finge por monkeypatch sobre `qt_fallback` (el
`from qt_fallback import …` de `main` se resuelve en el momento del call, así
que el monkeypatch aplica). `history_store.set_data_dir(tmpdir)` es la vía
oficial para no tocar `~/.local` — ya existe para esto.

### D3 — Lo que se afirma del import perezoso

Que después de correr el path daemon y el path Wayland, `"PyQt6" not in
sys.modules"`. Y que el path Qt sí lo carga. Eso convierte el pitfall de
AGENTS.md en un assert: si alguien sube el import, el test lo nombra.

## Risks / Trade-offs

- [El global `_daemon` del dashboard] → fixture que lo resetea a None; cada
  test declara el suyo.
- [La suite depende de Flask] → ya es dependencia del daemon que corre en
  producción; no se agrega nada.

## Migration Plan

1. `tests/test_entrada.py` → suite verde.
2. `tests/test_dashboard.py` → suite verde.
3. Cobertura: verificar que `verdantis.py` y `dashboard.py` salen del 0%.
4. Commit `test:` (sin bump de versión: `test:` no bumpea).

## Open Questions

- Ninguna bloqueante.
