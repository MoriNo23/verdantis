# toast-copiar Specification

## Purpose

Define la acción local "Copiar" del toast: copiar un código de verificación (o el
texto del body) al portapapeles sin robar el foco de teclado a la app activa.

## Requirements

### Requirement: Copiar código de verificación sin falsos positivos

El toast SHALL detectar un código de verificación solo cuando un número de 4 a 8
dígitos esté acompañado por una palabra clave de verificación a ±40 caracteres.
Un número sin contexto (año, versión, mención de usuario) SHALL NOT considerarse
código.

#### Scenario: Código con palabra clave
- **WHEN** el body dice "Tu código de verificación es 482193"
- **THEN** el botón dice "Copiar código" y copia "482193"

#### Scenario: Año o versión no son código
- **WHEN** el body dice "Wyeth, 1991" o "b200148"
- **THEN** no se ofrece botón "Copiar código"

### Requirement: El botón solo existe cuando hay código

El toast SHALL dibujar la banda "Copiar código" solo si `_find_code` encontró un
código. Sin código SHALL NOT reservarse la banda ni mostrar "Copiar texto": en el
historial real solo 26 de 1000 notificaciones traen código, así que una banda fija
es peso visual sin uso y cambia el alto de casi todos los toasts.

#### Scenario: Toast sin código
- **WHEN** el body no contiene un código de verificación
- **THEN** el toast no muestra ninguna banda de copiar y su alto no la reserva

### Requirement: Copiar sin foco (compatibilidad con keyboard-mode=NONE)

El toast SHALL copiar con `wl-copy` en Wayland y `xclip`/`xsel` en X11, sin
adquirir foco de teclado. A diferencia del popup de Plasma (que usa `takeFocus`
para `QClipboard`), Verdantis mantiene `keyboard_mode=NONE`.

#### Scenario: Copiar en Wayland
- **WHEN** el usuario suelta el click sobre el botón Copiar en Wayland
- **THEN** se llama a `wl-copy` con el código y la app activa conserva el foco

### Requirement: El botón consume el click

El botón Copiar SHALL ejecutarse al soltar dentro de su rect y SHALL NOT emitir
`ActionInvoked` ni `xdg-open` ni cerrar el toast.

#### Scenario: Click en Copiar
- **WHEN** el usuario hace press y release dentro del botón Copiar
- **THEN** se copia al portapapeles y no se dispara ninguna acción del sender
