# Spec Delta

## Purpose

Define la presencia, el contenido y la alineación del componente de imagen izquierda del toast (antes "avatar"): siempre visible en todos los toasts, con una cadena de contenido definida y con el bloque de texto alineado a su borde superior.

## ADDED Requirements

### Requirement: La imagen izquierda siempre está presente

El slot de imagen izquierda (80 px, clip circular) SHALL estar presente en todos los toasts, sin excepción. Su contenido se resuelve por prioridad: (a) la imagen de la notificación (icono del tab, `image-path` o archivo), (b) el icono de la app (`.desktop` exacto → tema de iconos), (c) un placeholder con la inicial del nombre de la app cuando ninguna fuente resuelve. El slot nunca queda vacío ni desaparece.

#### Scenario: Notificación de navegador con icono del tab
- **WHEN** llega una notificación de navegador con icono del tab (`image-data`)
- **THEN** la imagen izquierda muestra ese icono del tab

#### Scenario: App con .desktop o icono de tema
- **WHEN** la notificación no trae imagen pero la app resuelve por `.desktop` exacto o tema
- **THEN** la imagen izquierda muestra el logo de la app

#### Scenario: Nada resuelve
- **WHEN** la notificación no trae imagen y la app no resuelve por `.desktop` ni por tema
- **THEN** la imagen izquierda muestra el placeholder con la inicial del nombre de la app (el slot sigue presente)

#### Scenario: La imagen de la notificación gana siempre
- **WHEN** la notificación trae imagen Y la app también tiene icono resolvable
- **THEN** la imagen izquierda muestra la imagen de la notificación, nunca el icono de la app

### Requirement: El bloque de texto arranca al top de la imagen izquierda

La fila de app y el título SHALL arrancar a la altura del borde superior del slot de imagen izquierda, sin el centrado vertical del bloque de texto que hoy los deja hundidos. La imagen izquierda conserva su centrado vertical dentro de su fila; el cuerpo sigue inmediatamente a las filas alineadas, sin el respiro de la variante sin imagen.

#### Scenario: Fila de app al top del slot
- **WHEN** se renderiza un toast con contenido corto (el bloque de texto cabe holgado en la fila)
- **THEN** el borde superior de la fila de app coincide con el borde superior de la imagen izquierda (±1 px), sin el hundimiento del centrado vertical

#### Scenario: Sin respiro de la variante sin imagen
- **WHEN** se mide la distancia entre la fila de app y el título/body
- **THEN** es la misma en todos los toasts (no existe el gap extra de 18 px de la variante sin imagen)

### Requirement: El nombre de la app se centra en su icono

El texto de la fila de app SHALL tener su caja de tinta centrada verticalmente en el slot de 16 px del logo: una línea imaginaria por el centro del icono SHALL cortar el texto por su medio. El centrado SHALL calcularse sobre la caja de tinta real —no sobre la baseline ni con un desplazamiento fijo—, para que no dependa del tamaño de fuente ni de la escala de resolución.

#### Scenario: El texto se centra en el icono
- **WHEN** se renderiza un toast con logo de 16 px resuelto o sintetizado
- **THEN** el centro de la tinta del nombre de la app coincide con el centro del icono (±2 px)

#### Scenario: El centrado no depende de la fuente
- **WHEN** el nombre de la app tiene descendente ("Q", "J") o la escala de resolución cambia el tamaño de fuente
- **THEN** el centro de la tinta sigue coincidiendo con el centro del icono (±2 px)

### Requirement: La imagen izquierda no se pisa con la barra "Ver más"

El slot de imagen izquierda SHALL permanecer completamente visible: la barra "Ver más" es full-width por diseño (anti-misclick) y ocupa la banda inferior de la misma fila, así que el slot SHALL centrarse contra el bloque de TEXTO —excluyendo la barra— y no contra la fila entera. Ningún pixel del slot SHALL quedar bajo la banda de la barra.

#### Scenario: Con overflow el slot no queda bajo la barra
- **WHEN** un toast con overflow muestra su barra "Ver más" y el bloque de texto crece por encima del alto del slot
- **THEN** el borde inferior del slot queda por encima del borde superior de la barra y el círculo se dibuja completo

#### Scenario: Con contenido corto el slot no se sale de la fila
- **WHEN** el texto es más corto que el slot de 80 px
- **THEN** el slot se acota a la fila y no se desplaza hacia arriba ni hacia abajo

### Requirement: Columna de texto única

Todos los toasts SHALL usar la misma columna de texto de 240 px (360 − 14 − 80 − 12 − 14). La variante de columna ancha sin imagen desaparece, y las fuentes de título y cuerpo son las mismas para todos los toasts.

#### Scenario: Body al mismo ancho con placeholder que con imagen
- **WHEN** se comparan un toast con imagen del tab y un toast con placeholder (app sin icono)
- **THEN** el cuerpo de ambos wrappea a 240 px con las mismas fuentes

#### Scenario: La barra "Ver más" aterriza igual
- **WHEN** dos toasts con body largo (uno con imagen real, otro con placeholder) muestran su barra "Ver más"
- **THEN** la barra ocupa la misma posición relativa al contenido en ambos
