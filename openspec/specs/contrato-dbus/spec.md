# contrato-dbus Specification

## Purpose

Contrato D-Bus visible del daemon: razones concretas de `NotificationClosed` por cada path de cierre y versión de spec reportada por `GetServerInformation`. Un cliente externo (libnotify, KNotification, scripts) usa esto para distinguir vencido / cerrado por el usuario / pedido por `CloseNotification`.

## Requirements

### Requirement: NotificationClosed reporta la razón real del path de cierre

El daemon SHALL emitir `NotificationClosed(id: u, reason: u)` en todo cierre de una notificación viva en pantalla, con la razón del spec 1.2 correspondiente al path: expiración del timer → `1`; cierre por usuario (click del cuerpo, click de un botón de acción, franja de descarte) → `2`; llamada `CloseNotification` D-Bus → `3`. Cuando el path del cierre incluye una acción (click del cuerpo con acción default o click de un botón), el daemon SHALL emitir `ActionInvoked` ANTES de `NotificationClosed`.

El click del cuerpo sin acción `default` SHALL NOT emitir `ActionInvoked` con una action inventada: el daemon SHALL NOT emitir la primera action del sender por defecto. Con URL extraída, el click la abre con `xdg-open`; sin URL, solo cierra. La barra de expandir y la expansión del card no cierran la notificación y por tanto no emiten nada.

#### Scenario: Vencimiento por timer
- **WHEN** el timer de una notificación no crítica llega a 0 y el card se cierra solo
- **THEN** se emite `NotificationClosed(id, 1)`

#### Scenario: Click del cuerpo con acción default
- **WHEN** el usuario hace click en el cuerpo de un toast con acción default
- **THEN** se emite primero `ActionInvoked(id, key-default)` y después `NotificationClosed(id, 2)`

#### Scenario: Click del cuerpo abre URL sin default
- **WHEN** el usuario hace click en el cuerpo de un toast sin acción default pero con URL extraída
- **THEN** no se emite `ActionInvoked`, se abre la URL con `xdg-open` y se emite `NotificationClosed(id, 2)`

#### Scenario: Click del cuerpo con actions sin default y sin URL
- **WHEN** el usuario hace click en el cuerpo de un toast cuyo sender registró actions sin `default` y el body no trae URL
- **THEN** no se emite `ActionInvoked` (ninguna action del sender se ejecuta) y se emite `NotificationClosed(id, 2)`

#### Scenario: Click de un botón de acción
- **WHEN** el usuario hace click en el botón con key `settings`
- **THEN** se emite `ActionInvoked(id, "settings")` y después `NotificationClosed(id, 2)`

#### Scenario: Franja de descarte
- **WHEN** el usuario cierra un toast — persistente o con timer — por su franja vertical de descarte
- **THEN** se emite `NotificationClosed(id, 2)` sin `ActionInvoked`

#### Scenario: CloseNotification del bus
- **WHEN** un cliente llama `CloseNotification(id)`
- **THEN** se emite `NotificationClosed(id, 3)`

### Requirement: Reemplazo y dedup no emiten NotificationClosed

El daemon SHALL tratar estos paths como no-cierre y no emitir señal alguna por ellos: llegada con `replaces_id` (reemplazo in-place del card) y dedup por contenido dentro de su ventana de 10s.

#### Scenario: replaces_id
- **WHEN** llega una notificación con `replaces_id` apuntando a un card vivo y el card se actualiza en sitio
- **THEN** no se emite ninguna señal de cierre por la notificación reemplazada

#### Scenario: Dedup dentro de la ventana
- **WHEN** una notificación idéntica (misma app + resumen + body) llega dentro de 10s de la anterior y se deduplica
- **THEN** no se emite nada por la duplicada

### Requirement: GetServerInformation reporta spec_version 1.2

`GetServerInformation` SHALL devolver como cuarta posición la cadena `"1.2"`. Las tres primeras posiciones (nombre del server, vendor, versión del proyecto) no cambian con este change.

#### Scenario: Respuesta completa
- **WHEN** un cliente llama `GetServerInformation`
- **THEN** recibe `("Verdantis", "MoriNo23", <VERSION del proyecto>, "1.2")`
