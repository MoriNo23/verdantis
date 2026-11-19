# toast-badge-pendientes Specification

## Purpose

Hacer visible la cola de entrada: con dos toasts en pantalla, el resto de las
notificaciones esperan sin señal visual. Una franja compacta debajo de la pila
informa cuántas hay pendientes, sin alterar el orden ni la capacidad.

## Requirements

### Requirement: Badge de pendientes

Cuando haya una o más notificaciones en `_pending`, el daemon SHALL mostrar una
franja layer-shell debajo de la pila con el texto `+N notificación(es) en espera`
(singular para 1, plural para el resto). Con la cola vacía SHALL ocultarla. El
badge SHALL ubicarse debajo de la última card respetando el `STACK_GAP`, usar el
mismo acento `#80cbc4` y NO SHALL tomar foco de teclado (`keyboard_mode=NONE`,
`focusable=False`).

#### Scenario: Ráfaga con la pila llena

- **WHEN** llegan 5 notificaciones y se muestran 2
- **THEN** el badge indica "+3 notificaciones en espera" debajo de la pila

#### Scenario: La cola se vacía

- **WHEN** entran las pendientes hasta vaciar la cola
- **THEN** el badge se oculta

#### Scenario: Cierre en cola actualiza el badge

- **WHEN** se cierra por D-Bus una notificación que todavía estaba pendiente
- **THEN** el contador del badge baja en uno

### Requirement: El badge no cambia la semántica de la cola

El badge SHALL ser solo informativo: la cola sigue siendo FIFO por llegada, con
capacidad fija de 2 toasts visibles y sin reordenamiento por `urgency` (specs
`toast-orden-llegada` y `toast-stack`). El badge SHALL NO ser clickeable ni
emitir `ActionInvoked`.

#### Scenario: Mezcla de urgencias

- **WHEN** la cola mezcla `low`, `normal` y `critical`
- **THEN** el badge cuenta el total y el orden de entrada no cambia
