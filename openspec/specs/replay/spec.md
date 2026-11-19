# replay Specification

## Purpose

Interacción del toast reproducido desde el historial (`verdantis replay`): como el replay no pasa por el bus ni tiene sender, el click abre la URL archivada con `xdg-open`, no emite señales D-Bus y no re-archiva el registro. La affordance de click solo existe cuando hay URL que abrir.

## Requirements

### Requirement: `image-data` sin path también se archiva

Cuando un `Notify` trae `image-data` en `hints` pero no hay `image-path` ni
`app_icon` en disco, el daemon SHALL convertir esos bytes a PNG y guardarlos en
el directorio de iconos como `avatar_file`. El replay SHALL mostrar esa imagen
archivada igual que muestra un favicon copiado de `/tmp`. El archivo SHALL
respetar `MAX_ICON_BYTES` y un fallo de conversión NO SHALL romper el `Notify`.

#### Scenario: Replay de image-data sin path

- **WHEN** llega un `Notify` con `image-data` de 2x2 RGBA y sin path de archivo
- **THEN** el registro archivado tiene `avatar_file` apuntando a un PNG y el replay lo usa como imagen izquierda

#### Scenario: image-data inválido

- **WHEN** los bytes de `image-data` no forman una imagen válida
- **THEN** `Notify` responde normalmente y `avatar_file` queda vacío

### Requirement: El click abre la URL archivada

El toast reproducido cuyo registro archiva una URL SHALL abrirla con `xdg-open` al hacer click en el cuerpo, y cerrarse por ese click. Si el registro no archiva URL, el click del cuerpo no tiene efecto. Los botones de acción renderizados por fidelidad al registro no ejecutan la acción del sender original (no hay sender): su click no tiene efecto y no muestran affordance de click (spec `toast-acciones`).

#### Scenario: Click con URL archivada

- **WHEN** se reproduce un registro con URL archivada y el usuario hace click en el cuerpo
- **THEN** la URL se abre con `xdg-open` y el toast se cierra

#### Scenario: Click sin URL archivada

- **WHEN** se reproduce un registro sin URL y el usuario hace click en el cuerpo
- **THEN** no ocurre nada: el toast permanece y no se abre URL alguna

#### Scenario: Click en un botón de acción reproducido

- **WHEN** el registro traía actions, el toast reproduce sus botones y el usuario hace click en uno
- **THEN** no se ejecuta acción alguna del sender original y el toast permanece en pantalla

#### Scenario: Igual en el fallback X11

- **WHEN** un registro con URL archivada se reproduce por el branch de fallback X11
- **THEN** el click en el cuerpo abre la URL con `xdg-open` igual que en Wayland

### Requirement: El replay no emite señales ni re-archiva

Reproducir un registro — con o sin clicks — SHALL NOT emitir señal D-Bus alguna (`ActionInvoked`, `NotificationClosed`) ni agregar registros al historial: el replay reconstruye el toast directo desde `history.jsonl`, sin pasar por el daemon.

#### Scenario: El historial queda intacto

- **WHEN** se reproduce un registro y se hace click en el toast reproducido
- **THEN** la cantidad de registros del historial no cambia y ningún registro nuevo se escribe

#### Scenario: Sin señales al bus

- **WHEN** un toast reproducido se cierra por click, franja o vencimiento
- **THEN** no se emite `ActionInvoked` ni `NotificationClosed` por ese toast
