# Proposal — La pila se apila por llegada, sin identificar el tipo de toast

## Why

El usuario observes dos cosas en vivo que son un solo defecto de orden:

1. Los toasts **no se apilan como llegaron**: la pila se ordena por "tipo"
   (urgency), así que un `critical` que llega tarde adelanta a los que ya
   estaban en cola y un `low` se va al final. Verificado contra el manager real
   (`_sort_pending`, `src/verdantis_daemon.py:253-256`, invocada en cada
   `notify`):

   ```
   llega A normal  urg=1 -> cola: [A normal]
   llega B critical urg=2 -> cola: [B critical, A normal]      ← adelanta a A
   llega C low      urg=0 -> cola: [B critical, A normal, C low]
   llega D normal  urg=1 -> cola: [B critical, A normal, D normal, C low]
   se muestran: B critical, A normal, D normal, C low             ≠ orden de llegada
   ```

2. Por eso **las de un mismo tipo aparecen juntas** y las de otro tipo quedan
   al final: la pila "separa por tipos" en vez de apilar lo que llega.

El pedido es explícito: *"que se apilen sin identificar que es tipo de toast"*.
La pila debe ser una sola secuencia por orden de llegada; la `urgency` puede
seguir significando cuánto vive y cómo se ve cada toast, pero NADIE puede
usarla para reordenar la pila.

Hoy el único spec que toca esta área (`toast-stack`, dentro de
`layout-imagen-izquierda`) habla del **gap de 12 px** entre cards, no del orden.
Por eso esto es un change aparte y no untask suelta dentro de aquel.

## What Changes

- La cola de entrada pasa a ser **FIFO estricto por llegada**: se elimina el
  reordenamiento por `urgency` (`_sort_pending`) tanto en `notify` como en el
  drenado de `_close_id`.
- `urgency` deja de afectar el **orden** y sigue affecting lo que ya afectaba:
  duración (0.7× / 1.5× / escala de `critical`) y opacidad del card.
- Tests: se actualiza el test que fija el comportamiento viejo
  (`test_notify_batching.py::test_critical_priority_shown_before_low`) y se
  agregan los del contrato nuevo (orden de llegada con tipos mezclados,
  `critical` tardío que no adelanta, `low` que no se rezaqa, drenado por cierre
  sin reordenar).
- Sin cambios en la geometría del toast, en el stagger de aparición
  (`STAGGER_MS`: la pila sigue revelando de a uno) ni en la API DBus.

## Capabilities

### New Capabilities

- `toast-orden-llegada`: el orden en que se muestran y se apilan las
  notificaciones (independiente de la `urgency`).

### Modified Capabilities

(ninguna — la geometría de la pila sigue siendo responsabilidad de
`toast-stack`, en el change `layout-imagen-izquierda`)

## Impact

- `src/verdantis_daemon.py`: `_sort_pending` y sus dos llamadas.
- `tests/test_notify_batching.py`: el test de prioridad pasa a ser de orden de
  llegada; tests nuevos en el mismo archivo (o en uno nuevo si queda más legible).
- `openspec/specs/`: capability nueva `toast-orden-llegada` al archivar.
- Bump PATCH de `VERSION` (es un `fix:` de comportamiento, no una feature).
- Coordinación: este change NO toca `src/wayland_popup.py` ni los tests de
  layout, así que convive con `layout-imagen-izquierda` (que sigue siendo el
  merge grande de main). Se implementa **antes** de C para que el tablero de
  diseño (A) reciba una pila estable.