# toast-urgencia-critical Specification

## Purpose

Definir el comportamiento de las notificaciones con `urgency=2` (critical, spec
freedesktop 1.2): no desaparecen solas y se reconocen en la pila.

## Requirements

### Requirement: Un critical no expira

Una notificación con `urgency=2` SHALL tener duración 0 (persistente), aunque
el sender haya mandado `expire_timeout > 0`. SHALL cerrarse solo por acción del
usuario (franja de descarte, botón o `CloseNotification`). La regla SHALL
aplicarse en el cálculo de duración del daemon, antes de cualquier holdback por
posición en la pila.

#### Scenario: Critical con timeout explícito

- **WHEN** llega un `Notify` con `urgency=2` y `expire_timeout=5000`
- **THEN** su duración efectiva es 0 y el toast sigue en pantalla pasado el timeout

#### Scenario: Normal y low conservan su timeout

- **WHEN** llega un `Notify` con `urgency=0` o `1` y `expire_timeout=5000`
- **THEN** su duración efectiva sigue siendo 5000 ms

#### Scenario: Resident sigue sin expirar

- **WHEN** llega un `Notify` con `resident=true` y urgencia normal
- **THEN** su duración es 0 (regla preexistente, no afectada por este cambio)

### Requirement: El critical lleva un rail de acento propio

El acento de un critical SHALL ser `#ef9a9a`, distinto del acento de identidad
`#80cbc4`, y SHALL NO poder ser sobrescrito por la hint `accent` del sender. El
card SHALL dibujar un rail vertical de 3 px con ese color en el borde izquierdo,
independientemente del wipe de tiempo (que en un persistente no se dibuja).

#### Scenario: Render de critical

- **WHEN** se renderiza un toast con `urgency=2`
- **THEN** el nodo GSK contiene el rail de acento y difiere del mismo toast con `urgency=1`

#### Scenario: La app no cambia el color del critical

- **WHEN** un critical trae `hints["accent"]="#123456"`
- **THEN** el acento efectivo sigue siendo `#ef9a9a`
