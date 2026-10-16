# toast-franja-descarte Specification

## Purpose

Define cuándo es visible la franja de descarte con la X de cierre — en cualquier toast, persistente o con timer —, cómo se reparte el ancho de la columna de texto entre el contenido y la franja en cada estado de hover, y cómo el hover pausa el vencimiento para que el descarte manual sea alcanzable.

## Requirements

### Requirement: La franja y la X solo son visibles con hover

En cualquier toast — persistente o con auto-expiración —, la franja de descarte (tinte y X) SHALL dibujarse únicamente mientras el puntero está sobre el card. Sin puntero sobre el toast no SHALL dibujarse ninguna parte de la franja. Con hover, la franja SHALL medir 80 px de ancho en el borde derecho, la X SHALL dibujarse a ~24 px centrada en la franja, y el hit-rect de cierre SHALL ser la franja completa de alto completo (no solo el glyph de la X). El cierre por franja/X es cierre manual del usuario: cierra el toast sin disparar la acción default ni abrir URL alguna.

#### Scenario: Persistente sin puntero encima

- **WHEN** un toast persistente está en pantalla y el puntero no está sobre él
- **THEN** no se dibuja ni el tinte de la franja ni la X (cero píxeles de la franja)

#### Scenario: El puntero entra al persistente

- **WHEN** el puntero entra al área de un toast persistente
- **THEN** la franja con su X se hace visible en los 80 px del borde derecho

#### Scenario: El puntero sale del persistente

- **WHEN** el puntero deja el área del toast persistente
- **THEN** la franja y la X desaparecen en el redibujado inmediato

#### Scenario: Toast no persistente

- **WHEN** un toast con auto-expiración se muestra con el puntero sobre él
- **THEN** se dibuja la franja con su X igual que en un persistente; sin puntero encima, no se dibuja nada de la franja

#### Scenario: El hit-rect es la franja completa

- **WHEN** el usuario hace click en cualquier punto de los 80 px de la franja, aunque no caiga sobre el glyph de la X
- **THEN** el toast se cierra como cierre manual (razón de usuario del spec 1.2)

#### Scenario: El descarte no dispara la acción

- **WHEN** el usuario cierra el toast por la franja/X
- **THEN** no se ejecuta la acción default ni se abre URL alguna por ese click

### Requirement: El estado de hover se resetea de forma confiable

El estado de visibilidad de la franja SHALL reflejar siempre la posición real del puntero. Si el puntero deja el toast por cualquier vía — moverse fuera, que el toast se desplace o redimensione bajo un puntero quieto (p. ej. al cerrarse otro toast de la pila y reflowar el stack) — el estado SHALL resetearse de modo que la X nunca quede visible sin puntero encima, ni quede oculta teniéndolo.

#### Scenario: Reflow de la pila bajo un puntero quieto

- **WHEN** un toast con hover se desplaza porque otro toast de la pila se cerró y el puntero queda fuera de su nueva área
- **THEN** el toast deja de dibujar la franja en cuanto el puntero queda fuera

#### Scenario: Redimensionado bajo el puntero

- **WHEN** la ventana del toast se redimensiona mientras el puntero está quieto dentro de su área
- **THEN** el toast mantiene la franja visible y el card converge sin bucles de visibilidad

### Requirement: Sin hover el texto del persistente usa el ancho completo

Cuando el puntero no está sobre un toast — persistente o con timer —, su columna de texto SHALL ser la columna única del card: 240 px (el ancho con la imagen izquierda siempre presente). El espacio de la franja no SHALL reservarse de forma permanente.

#### Scenario: Columna sin hover

- **WHEN** cualquier toast renderiza su contenido sin puntero encima
- **THEN** la columna de texto mide 240 px y el texto wrappea a ese ancho

### Requirement: Con hover la franja reclama su ancho con re-wrap

Cuando el puntero está sobre un toast, la columna de texto SHALL reducirse en los 80 px de la franja (160 px) y el contenido — cuerpo, título y barra "Ver más" — SHALL re-wrappearse dentro de la columna reducida. Ningún texto SHALL quedar dibujado debajo del tinte de la franja. Si el re-wrap cambia la altura requerida del card, el toast SHALL redimensionarse por la vía de redimensionado existente, sin que ningún bloque del card (fila de app, título, cuerpo, barra "Ver más") se solape ni desborde.

#### Scenario: Re-wrap al entrar el hover

- **WHEN** el puntero entra a un toast cuyo cuerpo wrappeaba a 240 px
- **THEN** el cuerpo re-wrappea a 160 px y la franja cubre exactamente los 80 px liberados, sin texto bajo el tinte

#### Scenario: La barra "Ver más" respeta la columna con hover

- **WHEN** un toast con body largo y colapsado entra en hover
- **THEN** la barra "Ver más" se acota a la columna reducida y no queda bajo la franja

#### Scenario: Transición de altura estable

- **WHEN** el re-wrap al entrar/salir el hover cambia el número de líneas del cuerpo
- **THEN** el card redimensiona su altura y al estabilizar no hay bloques solapados ni parpadeo de visibilidad

#### Scenario: Hover repetido converge

- **WHEN** el puntero entra y sale varias veces seguidas sobre el mismo toast
- **THEN** el toast converge siempre al estado correcto de visibilidad y tamaño, sin oscilaciones

### Requirement: El hover pausa el vencimiento del toast

Mientras el puntero está sobre un toast con auto-expiración, el avance del wipe SHALL congelarse: el tiempo restante no se consume con el hover. Al salir el puntero, el vencimiento SHALL reanudarse desde el tiempo restante, sin reiniciar la duración completa ni vencer instantáneamente. Los persistentes no cambian: nunca vencen, con o sin hover.

#### Scenario: El hover congela el wipe

- **WHEN** el puntero está sobre un toast con timer
- **THEN** el frente del tinte del wipe no avanza mientras dure el hover

#### Scenario: Al salir reanuda con el tiempo restante

- **WHEN** el puntero sale del toast tras un hover largo
- **THEN** el wipe retoma el avance desde donde se congeló, sin reiniciar la duración ni vencer en el acto

#### Scenario: La X es alcanzable antes de vencer

- **WHEN** el hover entra cuando el toast estaba por vencer
- **THEN** el toast permanece en pantalla bajo el puntero hasta que el usuario lo cierra o retira el cursor

#### Scenario: El persistente no cambia

- **WHEN** un toast persistente queda con hover indefinidamente
- **THEN** no vence ni cambia su comportamiento de vencimiento (nunca expira)

### Requirement: La franja y la X muestran estados interactivos

La franja y la X SHALL mostrar estado pressed mientras el botón está presionado sobre ellas: el tinte SHALL intensificarse respecto del estado hover durante la presión. El cierre SHALL ejecutarse al soltar el botón dentro de la franja; soltar fuera de la franja SHALL cancelar el cierre y restaurar el estado de hover.

#### Scenario: Pressed visible durante la presión

- **WHEN** el usuario presiona la X o la franja sin soltar
- **THEN** el tinte de la franja se intensifica respecto del hover

#### Scenario: Soltar dentro cierra

- **WHEN** se presiona dentro de la franja y se suelta dentro de ella
- **THEN** el toast se cierra como cierre manual (razón de usuario)

#### Scenario: Arrastrar fuera cancela

- **WHEN** se presiona la franja, se arrastra fuera del card y se suelta
- **THEN** el toast no se cierra y la franja vuelve a su estado de hover
