# centro-notificaciones Specification

## Purpose

Dar acceso al historial archivado desde la bandeja del sistema: un ícono
StatusNotifierItem propio en el systray de KDE y una ventana GTK4 con las
últimas notificaciones como tarjetas, que reemplaza lo único que el applet de
Plasma no puede dar (su lista solo lee el modelo de SU daemon, inválido mientras
Verdantis es dueño de `org.freedesktop.Notifications`).

## Requirements

### Requirement: El ícono se registra en el systray del sistema

El daemon SHALL exportar `org.kde.StatusNotifierItem` en `/StatusNotifierItem`
y registrarse en `org.kde.StatusNotifierWatcher`. Las propiedades SHALL incluir
`Id`, `Category`, `Status`, `IconName`, `IconPixmap`, `Menu` y `ItemIsMenu`.
Sin watcher (o sin systray) el daemon SHALL seguir sirviendo notificaciones: la
bandeja es aditiva, nunca un requisito de arranque.

#### Scenario: Systray presente
- **WHEN** el daemon arranca en una sesión Plasma
- **THEN** el watcher lista el ítem y el ícono aparece junto al resto

#### Scenario: Systray ausente
- **WHEN** `StatusNotifierWatcher` no existe (sesión sin bandeja)
- **THEN** el ítem queda exportado, el daemon no falla y los toasts siguen

### Requirement: Click izquierdo abre el centro

`Activate` y `SecondaryActivate` SHALL abrir (o traer al frente) la ventana del
centro. La ventana SHALL crearse en el primer uso, no al arrancar: el daemon no
tiene ventanas visibles hasta que se pide el historial.

#### Scenario: Activar el ícono
- **WHEN** el usuario hace click izquierdo en el ícono
- **THEN** la ventana "Notificaciones" se muestra con el historial cargado

### Requirement: El menú del ícono ofrece abrir y limpiar

El ítem SHALL exponer un `com.canonical.dbusmenu` en `/MenuBar` con, como
mínimo, "Abrir historial" y "Limpiar historial". Los ids SHALL ser estables
entre llamadas (el host cachea el layout) y `Event("clicked")` SHALL ejecutar la
acción del ítem.

#### Scenario: Limpiar desde la bandeja
- **WHEN** se activa "Limpiar historial"
- **THEN** `history_store.clear()` borra registros e iconos, y el centro
  abierto se refresca

### Requirement: El centro lista el historial propio

La ventana SHALL leer `history_store.read()` y mostrar las últimas N (50)
notificaciones, la más reciente primero. Cada tarjeta SHALL mostrar app y
antigüedad relativa, título (o la app si no hay summary), body sin URLs y
acotado a 200 caracteres. Sin registros SHALL decir "sin notificaciones".

#### Scenario: Tarjeta desde un registro
- **WHEN** el registro dice app "Brave", summary "Código de verificación"
- **THEN** la tarjeta muestra esas dos líneas y "hace 5 min" si tiene 5 minutos

#### Scenario: Historial vacío
- **WHEN** no hay registros
- **THEN** la lista queda vacía y el encabezado dice "sin notificaciones"

### Requirement: Las tarjetas son de solo lectura

Activar una fila NO SHALL reproducir el toast ni abrir la URL archivada: el
centro es una vista del historial, no un replay. Reproducir sigue siendo
exclusivo del CLI (`verdantis replay`), que decide duración y filtros.

#### Scenario: Click en una tarjeta
- **WHEN** el usuario activa una fila del centro
- **THEN** no aparece ningún toast y no se abre ninguna URL

### Requirement: Foco y encabezado van por la identidad de marca

El centro SHALL conservar el anillo de foco de los botones (accesibilidad) pero
teñirlo con el acento `#80cbc4`, no con el azul de Adwaita por defecto. El
encabezado SHALL usar la misma escala visual del toast: título en negrita y
más grande que el resto de la ventana. El fondo de la ventana SHALL ser opaco
y distinto del de las filas para que la card se lea apoyada.

#### Scenario: Foco del botón Limpiar

- **WHEN** el botón "Limpiar" recibe el foco por teclado
- **THEN** su anillo es de 2 px en `#80cbc4` y el foco sigue siendo visible

#### Scenario: Jerarquía del encabezado

- **WHEN** se abre el centro
- **THEN** "Notificaciones" se lee en negrita y mayor tamaño que las etiquetas de las tarjetas

### Requirement: La ventana no retiene al daemon

Cerrar la ventana SHALL ocultarla, no destruirla ni terminar el daemon, y
Escape SHALL hacer lo mismo. El daemon SHALL seguir atendiendo Notify con la
ventana oculta.

#### Scenario: Cerrar el centro
- **WHEN** el usuario cierra la ventana o pulsa Escape
- **THEN** la ventana se oculta y el daemon sigue vivo en D-Bus
