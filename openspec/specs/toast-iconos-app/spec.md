# toast-iconos-app Specification

## Purpose

Define cómo el toast obtiene, escala y garantiza el logo de 16 px de la fila de app para cualquier sender, incluido el render sin recortes y el fallback visible cuando ninguna fuente resuelve.

## Requirements

### Requirement: El logo se resuelve desde cualquier fuente del sender

El toast SHALL mostrar el logo de 16 px de la fila de app cuando la notificación provee cualquiera de estas fuentes, en este orden: (a) `hints["desktop-entry"]` resuelto a un `.desktop` con `Icon=` (fuente canónica del spec y la que usa Plasma vía `KService::serviceByDesktopName`); (b) un archivo de icono existente — path plano o URI `file://` — en `app_icon`; (c) un nombre de icono "pelado" resoluble en el tema de iconos (hicolor/Breeze) en `app_icon`; (d) un `.desktop` que matchee EXACTO por `app_name`. La normalización que hace el daemon del `app_icon` (path-o-vacío) no SHALL descartar los nombres de tema. La resolución de tema SHALL usar la firma de GTK4 (`lookup_icon(nombre, fallbacks, size, scale, direction, flags)`), nunca la de GTK3.

#### Scenario: app_icon con nombre de tema pelado
- **WHEN** un sender manda `app_icon="firefox"` (nombre de icono del tema, sin archivo asociado)
- **THEN** la fila de app muestra el logo resuelto del tema por ese nombre

#### Scenario: app_icon como URI de archivo
- **WHEN** un sender manda `app_icon` como `file:///tmp/...` apuntando a un archivo existente
- **THEN** la fila de app muestra ese archivo como logo

#### Scenario: Resolución por app_name en el tema
- **WHEN** la resolución por `app_icon` falla pero `app_name` resuelve en el tema de iconos
- **THEN** la fila de app muestra el icono del tema por `app_name`

#### Scenario: desktop-entry con app_name localizado

- **WHEN** un sender manda `app_name="Correo"` y `hints["desktop-entry"]="thunderbird"`
- **THEN** el logo es el del `.desktop` thunderbird, aunque "Correo" no matchee ningún archivo

#### Scenario: lookup de tema en GTK4

- **WHEN** el `.desktop` dice `Icon=thunderbird` y el icono está en hicolor
- **THEN** se resuelve con la firma GTK4 de `lookup_icon` y se muestra escalado a 16/80 px

#### Scenario: Match exacto de .desktop
- **WHEN** `app_name` matchea exactamente un `.desktop` con campo `Icon=`
- **THEN** la fila de app muestra ese icono

### Requirement: El nombre de app toma el tono del icono

La fila de app SHALL colorearse con el promedio de los píxeles opacos del icono
resuelto (`_icon_tint`), con un piso de luminancia WCAG de 0,25 para mantener
contraste AA sobre la card. Si el icono no resuelve o es transparente, SHALL
usarse el color base `_TXT_APP_L`. El tono SHALL aplicarse tanto en la zona clara
como en la del wipe.

#### Scenario: Icono azul oscuro

- **WHEN** el icono resuelto es mayormente azul y poco luminoso
- **THEN** el nombre de app se ve azul claro, legible y del mismo color que el icono

#### Scenario: Sin icono

- **WHEN** no hay ni `app_icon` ni `desktop-entry` resoluble
- **THEN** el nombre de app conserva el color de texto base

### Requirement: Los iconos no cuadrados no se cortan

El logo de 16 px SHALL renderizarse preservando el aspect ratio: el icono completo se escala dentro del slot 16×16 con bandas transparentes (letterbox), sin center-crop del cuadrado central. La imagen izquierda de 80 px conserva su cover-crop circular por diseño y queda fuera de este requisito.

#### Scenario: Icono panorámico
- **WHEN** el icono fuente es no cuadrado (p. ej. 32×16)
- **THEN** se dibuja completo dentro del slot 16×16, con bandas transparentes, sin perder los extremos laterales

#### Scenario: Icono cuadrado
- **WHEN** el icono fuente ya es cuadrado
- **THEN** ocupa el slot 16×16 completo, igual que antes del cambio

### Requirement: Fallback visible cuando ninguna fuente resuelve

Cuando ninguna fuente resuelve el logo, la fila de app SHALL dibujar un placeholder genérico en el slot del icono — el slot nunca queda vacío — y el layout de la fila SHALL ser estable: el texto de la app conserva el mismo desplazamiento con logo resuelto o con placeholder.

#### Scenario: Sender desconocido sin icono
- **WHEN** llega una notificación de una app sin archivo, sin `.desktop` exacto y sin icono en el tema
- **THEN** la fila de app muestra el placeholder genérico en el slot del logo

#### Scenario: Layout estable con placeholder
- **WHEN** se compara la fila de app con logo resuelto vs. con placeholder
- **THEN** el texto de la app arranca en el mismo desplazamiento horizontal en ambos casos

### Requirement: La regla de match exacto de .desktop se conserva

La resolución por `.desktop` SHALL seguir siendo de match EXACTO (stem/WMClass/Name) y no SHALL reintroducirse match difuso por substring: los PWA de navegador (`brave-<appid>.desktop`) capturarían el nombre genérico del navegador y mostrarían el icono/nombre de la web app equivocada.

#### Scenario: Navegador con PWAs instalados
- **WHEN** llega una notificación de un navegador (p. ej. `app_name="Brave"`) teniendo PWAs instalados
- **THEN** el logo de la fila es el del navegador y nunca el de un PWA

### Requirement: El logo se mantiene nítido al reescalar

El reescalado del logo hacia el slot de 16 px (reducción o ampliación) SHALL conservar la interpolación de alta calidad existente; una regresión a interpolación de menor calidad no SHALL pasar la suite.

#### Scenario: Favicon pequeño agrandado
- **WHEN** un icono fuente más chico que 16 px se escala al slot
- **THEN** el render conserva la nitidez medida por la suite (energía de borde en el nivel actual)
