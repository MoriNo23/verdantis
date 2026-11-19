# toast-franja-descarte Specification

## Purpose

Define el rail de descarte con el botón circular de cierre — en cualquier toast, persistente o con timer —, por qué el rail queda reservado siempre, y cómo el hover pausa el vencimiento para que el descarte manual sea alcanzable. El hover enciende el botón, nunca inunda el rail de rojo ni reacomoda la card.

## Requirements

### Requirement: El rail de descarte está reservado siempre

En cualquier toast — persistente o con auto-expiración —, el rail de descarte SHALL medir 28 px de ancho en el borde derecho y SHALL estar reservado también sin puntero encima: la columna de texto SHALL ser 212 px (360 − 14 − 80 − 12 − 28 − 14) en todos los estados. El cierre SHALL ser un botón circular de 24 px dentro del rail, con una X neutra de 10 px, usando los MISMOS tokens de superficie que los botones de acción: blanco al 7 % en reposo, 11 % en hover y 4 % al presionar, con brillo interior de 1 px y hundimiento de 2 px en pressed. El glifo SHALL ir del 70 % en reposo al 100 % en hover. La franja SHALL NO inundarse de rojo en ningún estado. El hit-rect de cierre SHALL ser el rail completo de alto completo (no solo el botón). El cierre por rail/botón es cierre manual del usuario: cierra el toast sin disparar la acción default ni abrir URL alguna.

#### Scenario: Reposo

- **WHEN** un toast está en pantalla y el puntero no está encima
- **THEN** la placa está al 7 % con la X al 70 %, no hay tinte en el rail y la columna de texto mide 212 px

#### Scenario: El puntero entra al rail

- **WHEN** el puntero entra a los 28 px del borde derecho
- **THEN** la placa sube al 11 % y la X al 100 %, sin mover ningún texto

#### Scenario: El puntero sale del rail

- **WHEN** el puntero deja el rail
- **THEN** la placa vuelve al 7 % y la X al 70 %, en el redibujado inmediato

#### Scenario: El hit-rect es el rail completo

- **WHEN** el usuario hace click en cualquier punto del rail, aunque no caiga sobre el botón circular
- **THEN** el toast se cierra como cierre manual (razón de usuario del spec 1.2)

#### Scenario: El descarte no dispara la acción

- **WHEN** el usuario cierra el toast por el rail/X
- **THEN** no se ejecuta la acción default ni se abre URL alguna por ese click

### Requirement: El hover no reacomoda la card

Con el puntero encima, el toast SHALL NOT cambiar el ancho de su columna de texto, ni el wrap del cuerpo, del título o de la barra "Ver más", ni el ancho del botón Copiar, ni la altura de la card. El hover SHALL limitarse a encender el botón circular, encender los estados hover de los botones y pausar el vencimiento. El ancho de columna SHALL ser el mismo en reposo, hover y pressed, de modo que la pila de toasts nunca se reacomode por el puntero.

#### Scenario: Puntero sobre el cuerpo

- **WHEN** el puntero entra al área de la card pero fuera del rail
- **THEN** ningún píxel del contenido cambia y el toast no se redimensiona

#### Scenario: Puntero sobre el rail

- **WHEN** el puntero entra al rail
- **THEN** solo cambia el tinte del rail y el alpha de la X; el texto y el alto quedan idénticos

### Requirement: El estado de hover se resetea de forma confiable

El estado de visibilidad del tinte del rail SHALL reflejar siempre la posición real del puntero. Si el puntero deja el toast por cualquier vía — moverse fuera, que el toast se desplace bajo un puntero quieto (p. ej. al cerrarse otro toast de la pila y reflowar el stack) — el estado SHALL resetearse de modo que el tinte nunca quede encendido sin puntero encima, ni apagado teniéndolo.

#### Scenario: Reflow de la pila bajo un puntero quieto

- **WHEN** un toast con el puntero encima se desplaza porque otro toast de la pila se cerró y el puntero queda fuera de su nueva área
- **THEN** el toast apaga el tinte del rail en cuanto el puntero queda fuera

#### Scenario: Redimensionado bajo el puntero

- **WHEN** la ventana del toast se redimensiona mientras el puntero está quieto dentro de su área
- **THEN** el toast mantiene el estado de hover correcto y el card converge sin bucles de visibilidad
