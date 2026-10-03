# Spec Delta

## Purpose

Define el posicionamiento vertical de la pila de toasts: ningún solape entre cards y gap de separación constante ante cualquier cambio de altura de cualquiera de ellas.

## ADDED Requirements

### Requirement: La pila nunca solapa

Las cards consecutivas de la pila SHALL mantener siempre el gap de separación (12 px). Cualquier cambio de altura de un toast — expandir o contraer el body con "Ver más", o el re-wrap por hover de un persistente — SHALL re-flowear las posiciones de todos los toasts que están debajo, antes de que se presente el siguiente frame.

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
