# Diseño — GTK4 + GSK y vibrancia oscura (v0.15.0)

Fecha: 2026-11-18. Estado: aprobado por el usuario (modo goal).

## Contexto y decisión

El render actual es GTK3 + cairo en un `Gtk.DrawingArea`. El usuario pidió (1) migrar a
GTK4 con renderer GSK puro y (2) que la card y los botones dejen de verse planos:
"estilo Mac" con profundidad. Auditoría del entorno: Debian 13.7, kernel 6.12,
KDE Plasma 6 en Wayland, GTK 4.18.6, `gtk4-layer-shell` 1.0.4 disponible por apt.
Qt6/Kirigami/Qt Test están instalados pero se descartan: son para apps de escritorio,
no para un daemon layer-shell, y su look choca con "carácter propio" de PRODUCT.md.

## Arquitectura

- **Toolkit**: GTK 4.18 + GSK. Sin cairo en el pipeline de dibujo.
- **Layer shell**: `Gtk4LayerShell` 1.0.4 (gir). Cargar `libgtk4-layer-shell.so.0`
  con `ctypes.CDLL(..., mode=ctypes.RTLD_GLOBAL)` ANTES de `import gi`, si no
  `is_supported()` da False por el orden de linking con libwayland. Verificado en vivo.
  API idiomática: `init_for_window`, `set_layer`, `set_namespace`, `set_anchor`,
  `set_margin`, `set_exclusive_zone`, `is_layer_window`, `is_supported`.
  No existe `try_force_commit` (se elimina).
- **Widget**: `NotificationWidget` pasa de `Gtk.DrawingArea` a `Gtk.Widget` con
  `do_snapshot(self, snapshot)` + `do_measure(...)`. GTK4 no tiene señales
  `draw`/`button-press-event`: se usan `Gtk.EventControllerMotion` y
  `Gtk.GestureClick` vía `add_controller`.
- **Main loop**: GTK4 eliminó `Gtk.main()`/`Gtk.main_quit()`/`Gtk.init_check()`.
  Usar `GLib.MainLoop` en ambos popups; el daemon sigue con GLib.
- **Texto**: Pango sin PangoCairo. Layouts con `Pango.Context` +
  `PangoCairo.font_map_get_default()` (solo el font map, no el context de cairo),
  dibujados con `Gtk.Snapshot.append_layout(layout, Gdk.RGBA)`. GSK resuelve el AA;
  se retira `_FONT_OPTIONS`/`_create_layout(cr)` de la ruta de dibujo.
- **Medición**: `calc_card_height` y `_body_metrics` ya son headless con Pango; se
  reutilizan. La única fuente de métricas sigue siendo `wayland_popup`.

## Mapa de nodos GSK

| Elemento actual (cairo) | Nodo GSK |
|---|---|
| fondo redondeado | `Gsk.RoundedClipNode` + `append_color`/`append_linear_gradient` |
| sombra de la card (NUEVO) | `append_outset_shadow` (radio, blur 18, dy 8) |
| hairline (NUEVO) | rounded rect 1 px más grande en color borde + card 1 px inset |
| wipe de tiempo | `Gsk.ClipNode` con fill del acento al 15% |
| texto dos pasadas claro/oscuro | dos `Gtk.Snapshot.new()` → `to_node()` → `Gsk.ClipNode` |
| imagen circular | `Gdk.Texture.new_for_pixbuf` + `RoundedClipNode(radio=size/2)` |
| botones / barra "Ver más" | `append_color` redondeado + `append_layout` + borde interior |
| X / chevrón / franja | `append_color` + `append_stroke`/rects rotados con `TransformNode` |

## Tokens visuales (vibrancia oscura)

- Fondo: gradiente `rgba(58,60,74,0.90)` → `rgba(30,30,44,0.94)` (vertical).
- Borde hairline: `rgba(255,255,255,0.13)`, 1 px; card inset 1 px.
- Sombra: `rgba(0,0,0,0.52)`, dy 8, blur 18, spread 0.
- Radio card: 14; radio botones: 8.
- Botón: fill acento 18% + brillo interior 1 px al 6%; hover 30%; pressed 40% con
  sombra interior (se "hunde"). Etiqueta centrada por caja de tinta.
- Pila de 2 toasts: sombra en cascada entre cards (detalle "Mac" + refuerzo R1/R2).
- Se conservan acento `#80cbc4`, franja de wipe y slot circular de 80 px.
- Contraste: alpha nunca baja de 0.90 (spec `toast-contraste`, AA 4.5:1).

## Límites

- GSK no expone blur del fondo detrás de una layer-shell: la vibrancia es simulada
  con alpha + gradiente. No se promete equivalencia pixel con Notification Center.
- `_puntero_en_card` usaba `Gdk.Window.get_device_position` (no existe en Gdk4).
  Se reemplaza por coords del último `EventControllerMotion` + el `dy` conocido del
  reflow. Riesgo: si el puntero nunca entró al card, se trata como fuera.
- `Gdk.Cursor.new_from_name(name, fallback)` en GTK4 (sin display) y
  `Gtk.Widget.set_cursor` en vez de `Gdk.Window.set_cursor`.
- `Gtk.IconTheme.get_for_display` en vez de `get_for_screen`.
- Font scaling: `Gdk.Display.get_monitors()` en vez de `Gdk.Screen.get_width()`.
- X11 fallback se migra a GTK4 (sin layer-shell); se mantiene el branch.

## Verificación

- Suite pytest headless existente (52 tests) + metatests de sensibilidad.
- `tests/conftest.py` fija `GDK_BACKEND` y carga la librería de layer shell antes de gi.
- Verificación visual: la hace el agente (spec `verificacion-visual` invertida),
  mandando notificaciones de prueba y capturando la pantalla.
