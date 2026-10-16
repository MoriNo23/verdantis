# toast-orden-llegada Specification

## Purpose
Define el ORDEN en que se muestran y se apilan las notificaciones: una sola
secuencia por orden de llegada, sin que la `urgency` (el "tipo" del toast)
reordene la pila.

## Requirements

### Requirement: La pila se ordena por llegada

Las notificaciones pendientes de mostrar SHALL aparecer en el mismo orden en que
llegaron, con independencia de su `urgency`. Ningún aviso, drainage ni
reordenamiento por tipo SHALL mover una notificación delante de otra que llegó
antes. La cola pendiente SHALL tener un tope: cuando se supere, el daemon SHALL
descartar las notificaciones MÁS VIEJAS de la cola (nunca las recién llegadas) y
liberar su estado interno; las que quedan conservan el orden de llegada.

#### Scenario: Burst de tipos mezclados sale en orden de llegada

- **WHEN** llegan en secuencia un `normal`, un `critical`, un `low` y otro `normal`
- **THEN** se muestran en ese mismo orden, uno por tick, de arriba hacia abajo en la pila

#### Scenario: Un critical tardío no adelanta a la cola

- **WHEN** ya hay notificaciones en cola y llega una `critical`
- **THEN** aparece detrás de las que ya estaban esperando, no delante

#### Scenario: Un low no se rezaqa al final

- **WHEN** llega una notificación `low` después de otras
- **THEN** conserva su lugar en la secuencia (no se la mueve al final)

#### Scenario: Cerrar una activa no reordena el resto

- **WHEN** se cierra un toast y se libera un hueco de la pila
- **THEN** entra la siguiente notificación **por orden de llegada**, sin reordenar la cola por tipo


#### Scenario: Flood sobre el tope de la cola

- **WHEN** la cola pendiente ya tiene 20 notificaciones esperando y llega una más
- **THEN** se descarta la MÁS VIEJA de la cola (la recién llegada queda) y lo que queda sale en orden de llegada

### Requirement: La urgencia no reordena, solo define la vida del toast

La `urgency` SHALL seguir decidiendo la duración y la opacidad de cada toast
(`low` más corto y tenue, `critical` más largo y opaco) y SHALL NOT decidir su
posición en la pila.

#### Scenario: La urgencia sigue distinguiendo la vida del toast

- **WHEN** se envían una `low`, una `normal` y una `critical` en ese orden
- **THEN** cada una conserva su duración y su opacidad propias

#### Scenario: La urgencia no cambia la posición

- **WHEN** se envían una `low`, una `normal` y una `critical` en ese orden
- **THEN** la pila queda en ese mismo orden (la `critical` no salta ahead)
