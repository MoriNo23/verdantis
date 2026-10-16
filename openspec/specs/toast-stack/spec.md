# toast-stack Specification

## Purpose

Define el posicionamiento vertical de la pila de toasts: ningún solape entre cards y gap de separación constante ante cualquier cambio de altura de cualquiera de ellas.

## Requirements

### Requirement: La pila nunca solapa

Las cards consecutivas de la pila SHALL mantener siempre el gap de separación (12 px). Cualquier cambio de altura de un toast — expandir o contraer el body con "Ver más", o el re-wrap por hover de un persistente — SHALL re-flowear las posiciones de todos los toasts que están debajo, antes de que se presente el siguiente frame. El hueco de un toast que entra SHALL quedar reservado ANTES de que su superficie se presente: un toast SHALL NOT presentarse, ni por un frame, en el hueco de otro toast que ya está en pantalla.

#### Scenario: Expandir con toasts debajo
- **WHEN** un toast con body largo se expande teniendo otros toasts apilados debajo
- **THEN** los de abajo bajan manteniendo el gap de 12 px, sin solaparse con el expandido

#### Scenario: Contraer devuelve el espacio
- **WHEN** un toast expandido se contrae
- **THEN** los toasts de abajo vuelven a subir a su posición, manteniendo el gap

#### Scenario: El re-wrap por hover también re-flowea
- **WHEN** un toast persistente cambia de alto porque el hover re-wrappea su columna
- **THEN** los toasts debajo se reposicionan igual que ante cualquier otro cambio de altura

#### Scenario: El reflow es estable
- **WHEN** un toast se expande y contrae repetidamente con otros apilados debajo
- **THEN** las posiciones convergen siempre al estado correcto, sin oscilaciones ni acumulación de error

#### Scenario: Un toast que entra no tapa al que ya estaba
- **WHEN** llega una notificación con la pila ocupada y su superficie se presenta
- **THEN** su primera presentación ya está en su hueco (debajo del último toast, con el gap de 12 px) y nunca se la ve, ni un frame, encima del toast de arriba

#### Scenario: El toast de arriba tampoco se mueve al entrar otro
- **WHEN** un toast nuevo entra debajo de los que ya están
- **THEN** los toasts de arriba conservan su posición (solo cambia el que entra)

### Requirement: La pila muestra dos toasts a la vez

El sistema SHALL presentar como máximo DOS toasts simultáneos. Toda notificación que llegue con la pila llena SHALL quedar pendiente y SHALL NOT presentarse hasta que se libere un hueco; al liberarse, SHALL entrar la primera de las pendientes sin que las demás pierdan su lugar en la cola (spec `toast-orden-llegada`). La capacidad SHALL ser la misma para cualquier `urgency`: ningún tipo de notificación SHALL ganar un hueco extra.

#### Scenario: Ráfaga mayor que la capacidad
- **WHEN** llegan 5 notificaciones en una ráfaga
- **THEN** se presentan 2 a la vez y las otras 3 quedan pendientes

#### Scenario: Se libera un hueco
- **WHEN** se cierra uno de los dos toasts visibles habiendo notificaciones pendientes
- **THEN** entra la primera de las pendientes y vuelven a quedar 2 visibles

#### Scenario: La capacidad no depende del tipo
- **WHEN** una ráfaga mezcla `low`, `normal` y `critical`
- **THEN** el límite sigue siendo 2 para todos, sin que ninguna gane un hueco extra
