# entrada-fallback Specification

## Purpose

Define qué hace el one-shot de verdantis cuando no puede renderizar con layer-shell: qué backend lo reemplaza (X11 con ventana GTK posicionable), qué pasa en sesión Wayland sin layer-shell (error limpio, no un toast mal puesto), y que Qt queda fuera del proyecto por completo.

## Requirements

### Requirement: El one-shot elige backend por tipo de sesión

El one-shot SHALL renderizar con layer-shell Wayland cuando exista `WAYLAND_DISPLAY`, y SHALL usar el fallback X11 (ventana GTK común, sin layer-shell) cuando no exista.

#### Scenario: Sesión Wayland
- **WHEN** se invoca el one-shot con `WAYLAND_DISPLAY` definido y el render layer-shell funciona
- **THEN** se renderiza con WaylandPopup y no se crea ninguna ventana de fallback

#### Scenario: Sesión X11
- **WHEN** se invoca el one-shot sin `WAYLAND_DISPLAY`
- **THEN** se renderiza con el fallback X11 (ventana GTK común), sin cargar Qt

### Requirement: El fallback X11 posiciona el toast en la esquina pedida

La ventana de fallback SHALL ubicarse en la esquina indicada (`--corner`), dentro del workarea del monitor (respetando paneles), con margen `--margin`, y SHALL mantenerse visible sobre otras ventanas (keep-above).

#### Scenario: Esquina superior derecha en X11
- **WHEN** el one-shot corre en X11 con `--corner top-right` y margen 16
- **THEN** el toast queda anclado a la esquina superior derecha del workarea, a 16 px de los bordes

#### Scenario: Esquina con paneles
- **WHEN** el X11 tiene un panel que reduce el workarea en el borde de la esquina elegida
- **THEN** el toast no queda debajo del panel: se posiciona dentro del workarea disponible

### Requirement: En Wayland sin layer-shell el one-shot falla limpio

Si hay sesión Wayland pero el render layer-shell no está disponible (GTK no soporta layer-shell o la inicialización falla), el one-shot SHALL terminar con código de salida distinto de 0 y un mensaje por stderr que identifique la causa, y SHALL NOT mostrar ningún toast de fallback en esa sesión.

#### Scenario: GNOME o compositor sin layer-shell
- **WHEN** `WAYLAND_DISPLAY` está definido pero el compositor no implementa layer-shell
- **THEN** el one-shot imprime en stderr un mensaje que indica la falta de layer-shell y termina con exit code distinto de 0, sin mostrar ninguna ventana

#### Scenario: No hay toast mal posicionado
- **WHEN** falla el render layer-shell en una sesión Wayland
- **THEN** no se crea ninguna ventana toplevel sin posición definida

### Requirement: El proyecto no depende de Qt

Ningún path de verdantis (one-shot, daemon, entry point) SHALL importar PyQt6 ni depender de Qt. El módulo de fallback Qt y la dependencia pip correspondiente SHALL haber sido eliminados.

#### Scenario: Ningún path carga Qt
- **WHEN** se ejecuta el one-shot (Wayland o X11) o se levanta el daemon
- **THEN** ningún módulo `PyQt6` aparece en `sys.modules` como consecuencia de ese run

### Requirement: El flag --force-fallback fuerza el branch X11

El one-shot SHALL aceptar `--force-fallback` para seleccionar directamente el branch X11 de fallback, con el mismo papel de prueba que tenía `--force-qt`.

#### Scenario: Forzar fallback en headless
- **WHEN** se invoca el one-shot con `--force-fallback` en un entorno sin display real
- **THEN** se ejecuta el branch de fallback X11 (la ventana se construye contra el display que GTK resuelva, y si no hay display emite el error correspondiente)
