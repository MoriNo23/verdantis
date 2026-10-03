# Design

## Context

Estado verificado en código (`main` = 332e2c0):

- `NotificationManager.notify` (línea ~422) encola `(nid, kwargs, urgency)` y
  llama **`_sort_pending()`** (línea 423), que ordena la cola por `urgency`
  descendente: `self._pending.sort(key=lambda item: item[2], reverse=True)`.
- `_close_id` vuelve a llamar `_sort_pending()` antes de drenar la cola cuando
  se libera un hueco.
- `_pump` (línea 240) saca **un** pendiente por tick de `STAGGER_MS` con
  `pop(0)`: la pila se revela de a uno (eso ya está bien y no se toca).
- La `urgency` además vive dentro de `WaylandPopup.__init__`: `low` (0) escala
  la duración ×0.7 y pone `_bg_alpha = 0.55`, `critical` (2) escala ×1.5 y
  `_bg_alpha = 1.0`. Eso es lo que la `urgency` DEBE seguir significando.
- El único test que fija el orden por tipo es
  `tests/test_notify_batching.py::test_critical_priority_shown_before_low`.
  Los demás de ese archivo (`test_burst_not_shown_all_at_once`,
  `test_burst_order_preserves_fifo_for_same_urgency`,
  `test_closing_frees_slot_and_drains_queue`) ya son neutrales respecto del
  orden por tipo, salvo el docstring del módulo ("respetando prioridad").
- `toast-stack` (spec pendiente en `layout-imagen-izquierda`) habla del gap de
  12 px: es otra cosa y no se toca acá.

## Goals / Non-Goals

**Goals:**

- La pila es una secuencia por orden de llegada, sin importar el tipo del
  toast: nada reordena la cola.
- La `urgency` conserva su significado de vida/opacidad del toast.
- El comportamiento viejo queda cubierto por tests actualizados, no borrado.

**Non-Goals:**

- No se agrupan toasts por app ni por tipo (el usuario pidió lo contrario:
  pila única).
- No se cambia `STAGGER_MS`, `MAX_VISIBLE` ni el reveal de a uno.
- No se toca la geometría del card ni el reflow de la pila (`toast-stack` /
  `layout-imagen-izquierda`).
- No se cambia la API DBus ni el `hints` que se acepta.

## Decisions

### D1 — FIFO estricto: se elimina el reordenamiento

`_sort_pending` desaparece y sus dos llamadas (en `notify` y en `_close_id`).
La cola queda como está: `append` al llegar, `pop(0)` al mostrar. Es el cambio
mínimo posible — no hay sorted-set, ni claves, ni "secciones".

*Alternativa rechazada*: "prioridad sólo para `critical`" (un
`if urgency == 2` al frente). seguiría siendo ordenar por tipo, que es
exactamente lo que el usuario pidió quitar.

### D2 — La `urgency` sigue viva donde sirve

No se toca la tupla `(nid, kwargs, urgency)` de `_pending` ni el bloque de
`WaylandPopup.__init__` que escala duración y alpha: la `urgency` deja de
reordenar, no de existir. La tupla conserva el tercer campo porque el drenado
y el historial la usan; sacarla sería refactorizar sin contrato que lo pida.

### D3 — Los tests viejos que fijan el tipo se actualizan, no se borran

`test_critical_priority_shown_before_low` pasa a afirmar el contrato nuevo
(orden de llegada con tipos mezclados). Los tests que ya eran neutrales siguen
intactos; sólo se toca el docstring del módulo que anuncia "respetando
prioridad (urgency)".

### D4 — El test del orden se hace con el manager real, sin ventanas

Se reutiliza el harness de `test_notify_batching.py` (scheduler falso +
`_show_popup` que construye el `WaylandPopup` real sin `prepare()`): el
comportamiento bajo test es la cola, no el render. Además se cubre el drenado
por cierre (`_close_id`), que es el segundo sitio donde hoy se reordena.

### D5 — Verificación en vivo, no sólo tests

`busctl`/ Notify con `urgency` 0/1/2 en secuencia y un burst mezclado: la pila
tiene que verse en orden de llegada, con las duraciones/opacidades distintas
que ya se veían. Es la única forma de confirmar que "se apilan bien
independientemente" en el escritorio real.

## Risks / Trade-offs

- [Un `critical` ya no salta la cola] → Es el pedido explícito del usuario. Se
  mitiga conservando su vida más larga y su opacidad plena, que es lo que
  comunica urgencia. Queda anotado como trade-off consciente, no como forgot.
- [Un `low` ya no se rezaga al final] → Ídem: llega y se apila donde le toca.
- [Cambio de comportamiento visible] → Por eso es un change con su propio
  delta de spec y tests rojos primero: el revert es un commit.

## Migration Plan

1. Rama `testing/pila-fifo` desde `main` en el worktree de testing; tests
   actualizados + nuevos, verificados rojos por la razón correcta.
2. Commit `test:` (la rama queda roja por diseño, como la de
   `layout-imagen-izquierda`).
3. Merge a `main`, implementación (borrar `_sort_pending` y sus llamadas),
   suite verde, bump PATCH, commit `fix:`.
4. Verificación en vivo (D5) + `busctl ... GetServerInformation`.
5. Rollback: `git revert` del commit `fix:`.

## Open Questions

- Ninguna bloqueante. La decisión de fondo (pila única por llegada) la tomó el
  usuario; queda como supuesto registered para vetar al revisar los artefactos:
  no habrá agrupación por app/tipo en ninguna versión de este change.