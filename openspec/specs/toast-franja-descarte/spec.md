# toast-franja-descarte Specification

## Purpose

Define cuándo es visible la franja de descarte con la X de cierre en los toasts persistentes, y cómo se reparte el ancho de la columna de texto entre el contenido y la franja en cada estado de hover.

## Requirements

### Requirement: La franja y la X solo son visibles con hover

En un toast persistente, la franja de descarte (tinte y X) SHALL dibujarse únicamente mientras el puntero está sobre el card. Sin puntero sobre el toast no SHALL dibujarse ninguna parte de la franja. Los toasts no persistentes nunca SHALL dibujar la franja ni la X, con o sin hover.

#### Scenario: Persistente sin puntero encima
- **WHEN** un toast persistente está en pantalla y el puntero no está sobre él
- **THEN** no se dibuja ni el tinte de la franja ni la X (cero píxeles de la franja)

#### Scenario: El puntero entra al persistente
- **WHEN** el puntero entra al área del toast persistente
- **THEN** la franja con su X se hace visible en los 44 px del borde derecho

#### Scenario: El puntero sale del persistente
- **WHEN** el puntero deja el área del toast persistente
- **THEN** la franja y la X desaparecen en el redibujado inmediato

#### Scenario: Toast no persistente
- **WHEN** un toast con auto-expiración se muestra, con o sin hover
- **THEN** nunca se dibuja la franja de descarte ni la X

### Requirement: El estado de hover se resetea de forma confiable

El estado de visibilidad de la franja SHALL reflejar siempre la posición real del puntero. Si el puntero deja el toast por cualquier vía — moverse fuera, que el toast se desplace o redimensione bajo un puntero quieto (p. ej. al cerrarse otro toast de la pila y reflowar el stack) — el estado SHALL resetearse de modo que la X nunca quede visible sin puntero encima, ni quede oculta teniéndolo.

#### Scenario: Reflow de la pila bajo un puntero quieto
- **WHEN** un toast persistente con hover se desplaza porque otro toast de la pila se cerró y el puntero queda fuera de su nueva área
- **THEN** el toast deja de dibujar la franja en cuanto el puntero queda fuera

#### Scenario: Redimensionado bajo el puntero
- **WHEN** la ventana del toast se redimensiona mientras el puntero está quieto dentro de su área
- **THEN** el toast mantiene la franja visible y el card converge sin bucles de visibilidad

### Requirement: Sin hover el texto del persistente usa el ancho completo

Cuando el puntero no está sobre un toast persistente, su columna de texto SHALL ser la columna única del card: 240 px (el ancho con la imagen izquierda siempre presente). El espacio de la franja no SHALL reservarse de forma permanente.

#### Scenario: Columna sin hover
- **WHEN** un toast persistente renderiza su contenido sin puntero encima
- **THEN** la columna de texto mide 240 px y el texto wrappea a ese ancho

### Requirement: Con hover la franja reclama su ancho con re-wrap

Cuando el puntero está sobre un toast persistente, la columna de texto SHALL reducirse en los 44 px de la franja (196 px) y el contenido — cuerpo, título y barra "Ver más" — SHALL re-wrappearse dentro de la columna reducida. Ningún texto SHALL quedar dibujado debajo del tinte de la franja. Si el re-wrap cambia la altura requerida del card, el toast SHALL redimensionarse por la vía de redimensionado existente, sin que ningún bloque del card (fila de app, título, cuerpo, barra "Ver más") se solape ni desborde.

#### Scenario: Re-wrap al entrar el hover
- **WHEN** el puntero entra a un toast persistente cuyo cuerpo wrappeaba a 240 px
- **THEN** el cuerpo re-wrappea a 196 px y la franja cubre exactamente los 44 px liberados, sin texto bajo el tinte

#### Scenario: La barra "Ver más" respeta la columna con hover
- **WHEN** un persistente con body largo y colapsado entra en hover
- **THEN** la barra "Ver más" se acota a la columna reducida y no queda bajo la franja

#### Scenario: Transición de altura estable
- **WHEN** el re-wrap al entrar/salir el hover cambia el número de líneas del cuerpo
- **THEN** el card redimensiona su altura y al estabilizar no hay bloques solapados ni parpadeo de visibilidad

#### Scenario: Hover repetido converge
- **WHEN** el puntero entra y sale varias veces seguidas sobre el mismo persistente
- **THEN** el toast converge siempre al estado correcto de visibilidad y tamaño, sin oscilaciones
