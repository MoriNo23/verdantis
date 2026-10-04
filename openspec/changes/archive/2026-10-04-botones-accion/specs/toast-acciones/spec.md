# Spec Delta

## Purpose

Define el render y la interacción de los botones de acción del toast: la fila visible de acciones que manda el sender por D-Bus, sus zonas de click y la emisión de `ActionInvoked` con la key correcta de cada botón.

## ADDED Requirements

### Requirement: Los botones de acción se renderizan

Cuando una notificación trae actions (pares key/label) además de `default`, el toast SHALL renderizar sus botones visibles en una fila propia bajo el body, con el label localizado de cada acción. La fila SHALL mostrar como máximo 3 botones (los primeros); un toast sin actions (o solo con `default`) SHALL mostrar la fila en absoluto. La action `default` nunca se renderiza como botón — sigue siendo el click del cuerpo.

#### Scenario: Dos acciones visibles
- **WHEN** llega una notificación con actions `["default", "Abrir sitio", "settings", "Ajustes", "mark", "Marcar"]`
- **THEN** el toast muestra dos botones — "Ajustes" (key `settings`) y "Marcar" (key `mark`) — en la fila de acciones, y `default` no aparece como botón (su label viaja en el par pero nunca se renderiza)

#### Scenario: Sin acciones no hay fila
- **WHEN** llega una notificación sin actions (o solo con `default`)
- **THEN** el toast no dibuja la fila de botones y su layout es el actual

#### Scenario: Más de tres acciones
- **WHEN** la notificación trae más de 3 actions además de `default`
- **THEN** el toast renderiza los primeros 3 botones visibles

### Requirement: Cada botón emite su propia action key

El click en un botón SHALL emitir `ActionInvoked` con la key de ESE botón — no la default — y SHALL consumir el evento: no SHALL disparar el click del cuerpo (acción default / apertura de URL) ni el cierre por franja. El click del cuerpo fuera de los botones se mantiene exactamente como hoy.

#### Scenario: Click en un botón específico
- **WHEN** el usuario hace click en el botón "Ajustes" (key `settings`)
- **THEN** se emite `ActionInvoked(id, "settings")` y no se emite ninguna otra acción por ese click

#### Scenario: Los botones no abren la URL del cuerpo
- **WHEN** una notificación con hyperlink en el body muestra botones y el usuario hace click en uno de ellos
- **THEN** no se abre la URL del body — el botón consume el evento y emite solo su key

#### Scenario: El cuerpo sigue invocando la default
- **WHEN** el usuario hace click en el cuerpo del toast (fuera de botones, franja y barra "Ver más")
- **THEN** el comportamiento es el actual: la acción default del sender, sin cambios

### Requirement: action-icons con fallback a texto

Cuando la notificación incluye el hint `action-icons` y el server anuncia la capability, el toast SHALL intentar resolver el key de cada botón como nombre de icono del tema de iconos (icon naming spec) y renderizar ese icono junto al label — el label sigue visible como texto del botón y como fallback. Si el icono no resuelve, el botón SHALL mostrar solo su label de texto, sin huecos.

#### Scenario: Botón estándar con icono del tema
- **WHEN** llega una notificación con hint `action-icons` y un botón cuyo key es un icono del tema (p. ej. `mail-mark-read`)
- **THEN** el botón renderiza ese icono junto a su label

#### Scenario: Icono que no resuelve
- **WHEN** el hint `action-icons` está pero el key del botón no coincide con ningún icono del tema
- **THEN** el botón muestra su label de texto, idéntico a como se vería sin el hint

#### Scenario: Sin hint no hay iconos
- **WHEN** la notificación no manda el hint `action-icons`
- **THEN** los botones renderizan solo texto, aunque la capability esté anunciada

### Requirement: La fila de botones es parte del layout

La fila de botones SHALL sumar su altura a la card en la misma fuente de métricas que el resto del layout. Ningún bloque del card SHALL solaparse: la barra "Ver más" (cuando hay overflow) SHALL anclar debajo de los botones, y el toast redimensionado SHALL respetar la pila (sin solapes, gap constante).

#### Scenario: Body largo con botones
- **WHEN** un toast con overflow y botones se muestra colapsado
- **THEN** la barra "Ver más" queda debajo de la fila de botones, sin solaparse con ella ni con el body

#### Scenario: La pila respeta la card con botones
- **WHEN** un toast con botones convive con otros en la pila y cambia de alto (expandir/contraer)
- **THEN** las cards mantienen el gap constante, igual que ante cualquier otro cambio de altura
