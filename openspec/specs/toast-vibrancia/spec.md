# toast-vibrancia Specification

## Purpose

Define la vibrancia oscura y la profundidad física del toast dibujado con GSK:
gradiente de fondo, hairline, sombra en cascada entre los dos toasts visibles y
botones que se hunden al presionarse. La vibrancia se simula con alpha y
gradiente — GSK no expone backdrop blur real en una layer-shell — sin abandonar
la identidad propia (acento, wipe, slot de imagen de 80 px).

## Requirements

### Requirement: La card tiene profundidad física

La card SHALL dibujarse como un objeto con volumen: fondo en gradiente vertical
de `rgba(58, 60, 74, 0.90)` (arriba) a `rgba(30, 30, 44, 0.94)` (abajo), con
radio de 14 px. El render SHALL construirse con nodos GSK (clip redondeado +
gradiente lineal); el pipeline de dibujo SHALL NOT usar cairo.

#### Scenario: Fondo en gradiente con radio propio

- **WHEN** se renderiza cualquier toast
- **THEN** su fondo es el gradiente vertical definido, dentro de un clip de radio 14 px, sin cairo en el pipeline de dibujo

#### Scenario: El gradiente no rompe la legibilidad

- **WHEN** el texto se apoya sobre el gradiente en su punto más claro y en el más oscuro
- **THEN** ambos extremos mantienen el contraste AA exigido por `toast-contraste`

### Requirement: La card lleva un hairline de 1 px

El borde de la card SHALL ser un hairline de 1 px en `rgba(255, 255, 255, 0.13)`,
dibujado como un rectángulo redondeado de 1 px mayor que la card, con la card
inset 1 px. El hairline SHALL NOT engrosarse ni volverse opaque en ningún estado.

#### Scenario: Hairline presente en todos los estados

- **WHEN** el toast está en reposo, en hover, bajo el wipe o expandido
- **THEN** el hairline conserva su grosor de 1 px y su color `rgba(255, 255, 255, 0.13)`

### Requirement: La sombra cae en cascada entre los dos toasts

Cada card SHALL proyectar una sombra exterior `rgba(0, 0, 0, 0.52)` con
desplazamiento vertical de 8 px, blur de 18 px y spread 0. Con dos toasts
visibles, la sombra de la card superior SHALL caer sobre la card inferior a
través del gap de 12 px, reforzando la lectura de profundidad de la pila sin
modificar el gap ni el orden (`toast-stack`).

#### Scenario: Sombra en cascada con la pila llena

- **WHEN** hay dos toasts apilados con el gap de 12 px
- **THEN** la sombra de la card superior es visible sobre el borde superior de la inferior, sin solapar las cards ni cambiar sus posiciones

#### Scenario: La sombra no altera el reflow

- **WHEN** un toast se expande, se contrae o entra uno nuevo
- **THEN** la sombra se reposiciona con su card y el gap de 12 px permanece intacto

### Requirement: Los botones se hunden al presionarse

El fill de los botones de acción SHALL ser una superficie blanca translúcida
neutra —7 % en reposo, 11 % en hover y 4 % en pressed— con radio de 8 px y un
brillo interior de 1 px al 6 % en reposo/hover. El acento `#80cbc4` SHALL NOT
usarse como fill de botón: al 18 % sobre el gradiente producía un gris verdoso
(`#41575F`) que choca con el gris azulado de la card. En pressed SHALL añadirse
una sombra interior de 2 px arriba (negro al 28 %) que hunda el botón, sin
desplazar la fila ni cambiar sus métricas. La ejecución de la acción SHALL seguir
las reglas de `toast-acciones`.

#### Scenario: Reposo, hover y pressed

- **WHEN** un botón pasa de reposo a hover y luego a pressed sin soltar
- **THEN** su fill pasa de 7 % a 11 % a 4 % de blanco, y en pressed aparece la sombra interior de 2 px que lo hunde

#### Scenario: El hundimiento no mueve el layout

- **WHEN** un botón está presionado
- **THEN** la fila de acciones conserva su altura y la card no cambia de tamaño

### Requirement: El alpha nunca baja de 0.90

El alpha efectivo de la card SHALL ser como mínimo 0.90 en todo punto del
gradiente. Este piso SHALL conservarse para garantizar el contraste AA de
`toast-contraste`; SHALL NOT reducirse para intensificar el efecto translucent.

#### Scenario: Piso de alpha en todo el gradiente

- **WHEN** se inspeccionan ambos stops del gradiente de fondo
- **THEN** ninguno tiene alpha menor a 0.90

### Requirement: La identidad del toast se conserva

La vibrancia SHALL NOT reemplazar los elementos de identidad: el acento
`#80cbc4`, la franja de wipe de tiempo y el slot circular de imagen de 80 px en
todos los toasts permanecen iguales. El wipe SHALL seguir tiñendo con el acento
al 15-18 % y el slot SHALL seguir resolviendo imagen → icono de app → inicial.

#### Scenario: Identidad intacta bajo el nuevo render

- **WHEN** se compara un toast con vibrancia contra un toast anterior
- **THEN** el acento, el wipe y el slot de 80 px siguen presentes con el mismo comportamiento

### Requirement: La vibrancia es simulada, no un backdrop blur real

GSK SHALL NOT exponer backdrop blur del fondo detrás de una superficie
layer-shell. El efecto SHALL lograrse únicamente con composición de alpha y
gradiente; el producto SHALL NOT prometer equivalencia pixel con el Notification
Center de macOS ni con cualquier otro efecto de blur del compositor.

#### Scenario: Sin blur real en Wayland

- **WHEN** un toast se muestra sobre contenido arbitrario del escritorio
- **THEN** su apariencia es el gradiente con alpha definido, sin muestrear ni desenfocar lo que hay detrás
