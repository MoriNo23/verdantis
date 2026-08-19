#!/usr/bin/env python3
"""
Master Production Integration: Floating Wayland HUD Card for KDE Plasma 6
Stack: Python 3.13 | GTK 3.0 | gtk-layer-shell 0.1 | Cairo | Pango (Manrope) | GdkPixbuf
"""

import sys
import os
import math
from pathlib import Path
import ctypes
import ctypes.util
import cairo

# -------------------------------------------------------------------------
# 1. Configuración de Entorno y Typelibs para Python 3.13 en .venv
# -------------------------------------------------------------------------
SYSTEM_TYPELIB_PATHS = [
    "/usr/lib64/girepository-1.0",
    "/usr/lib/x86_64-linux-gnu/girepository-1.0",
    "/usr/lib/girepository-1.0",
    "/usr/local/lib64/girepository-1.0",
    "/usr/local/lib/girepository-1.0"
]
existing_gi = os.environ.get("GI_TYPELIB_PATH", "")
valid_gi_paths = [p for p in SYSTEM_TYPELIB_PATHS if Path(p).exists()]
if existing_gi:
    valid_gi_paths.append(existing_gi)
os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(valid_gi_paths)

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gtk, Gdk, GdkPixbuf, GtkLayerShell, Pango, PangoCairo, GLib

# -------------------------------------------------------------------------
# 2. Inyección Dinámica de Fuente Bundled (Manrope)
# -------------------------------------------------------------------------
def inject_bundled_fonts() -> None:
    """Carga archivos TTF locales en el FontConfig del proceso actual."""
    font_search_paths = [
        Path(__file__).parent / "fonts" / "Manrope-SemiBold.ttf",
        Path(__file__).parent / "fonts" / "Manrope-Regular.ttf",
        Path("/usr/share/fonts/TTF/Manrope-SemiBold.ttf"),
        Path("/usr/share/fonts/google-manrope-fonts/Manrope-SemiBold.ttf"),
    ]
    try:
        fc_lib_name = ctypes.util.find_library("fontconfig") or "libfontconfig.so.1"
        fc = ctypes.cdll.LoadLibrary(fc_lib_name)
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_bool
        for p in font_search_paths:
            if p.exists():
                fc.FcConfigAppFontAddFile(None, str(p.resolve()).encode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"Aviso: Carga de fuente en runtime omitida ({e})\n")

# -------------------------------------------------------------------------
# 3. Utilidades de Renderizado Cairo y Pango
# -------------------------------------------------------------------------
class CairoGeometry:
    @staticmethod
    def rounded_rectangle(cr: cairo.Context, x: float, y: float, width: float, height: float, radius: float) -> None:
        deg = math.pi / 180.0
        r = min(radius, width / 2.0, height / 2.0)
        cr.new_sub_path()
        cr.arc(x + width - r, y + r, r, -90 * deg, 0 * deg)
        cr.arc(x + width - r, y + height - r, r, 0 * deg, 90 * deg)
        cr.arc(x + r, y + height - r, r, 90 * deg, 180 * deg)
        cr.arc(x + r, y + r, r, 180 * deg, 270 * deg)
        cr.close_path()

class PangoTypography:
    @staticmethod
    def draw_text(
        cr: cairo.Context,
        text: str,
        x: float,
        y: float,
        max_width: float,
        font_desc: str = "Manrope Medium 13",
        color_rgba: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.95),
        ellipsize: bool = True
    ) -> tuple[int, int]:
        cr.save()
        layout: Pango.Layout = PangoCairo.create_layout(cr)
        layout.set_text(text, -1)
        layout.set_font_description(Pango.FontDescription.from_string(font_desc))
        
        if max_width > 0:
            layout.set_width(int(max_width * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        
        if ellipsize:
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            
        cr.set_source_rgba(*color_rgba)
        cr.move_to(x, y)
        PangoCairo.update_layout(cr, layout)
        PangoCairo.show_layout(cr, layout)
        w_px, h_px = layout.get_pixel_size()
        cr.restore()
        return (w_px, h_px)

# -------------------------------------------------------------------------
# 4. DrawingArea de la HUD Card Interactiva con Animación Wipe
# -------------------------------------------------------------------------
class ProductionHUDCardWidget(Gtk.DrawingArea):
    def __init__(self, close_action: callable) -> None:
        super().__init__()
        self.close_action = close_action
        
        # Geometría del contenedor
        self.card_w = 400
        self.card_h = 104
        self.padding = 16
        
        # Control de la animación Wipe (V-Sync)
        self.animating = True
        self.wipe_progress = 0.0
        self.duration_us = 400000  # 400ms
        self.start_frame_time_us: int | None = None
        
        # Geometría y Estado del Pill de Cierre
        self.pill_w = 28
        self.pill_h = 28
        self.pill_x = self.card_w - self.pill_w - self.padding
        self.pill_y = self.padding
        self.is_pill_hovered = False
        self.is_pill_pressed = False
        
        # Eventos de Entrada
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.ENTER_NOTIFY_MASK |
            Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        
        # Conexiones de Señales
        self.connect("draw", self._on_draw)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("leave-notify-event", self._on_leave)
        
        self.set_size_request(self.card_w, self.card_h)
        
        # Carga Segura de Pixbuf
        self.avatar_pixbuf = self._create_or_load_avatar()
        
        # Iniciar ciclo de animación ligado al FrameClock
        self.add_tick_callback(self._on_animation_tick)

    def _create_or_load_avatar(self) -> GdkPixbuf.Pixbuf:
        """Carga una imagen de avatar o genera un fallback estético en memoria."""
        img_path = Path(__file__).parent / "avatar.png"
        if img_path.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(img_path), 56, 56, True)
            except Exception:
                pass
        
        # Fallback: buffer RGBA con degradado
        fallback = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 56, 56)
        fallback.fill(0x2563EBEA)  # Azul moderno
        return fallback

    def _on_animation_tick(self, widget: Gtk.Widget, frame_clock: Gdk.FrameClock) -> bool:
        current_time = frame_clock.get_frame_time()
        if self.start_frame_time_us is None:
            self.start_frame_time_us = current_time
            
        elapsed = current_time - self.start_frame_time_us
        t = min(1.0, elapsed / self.duration_us)
        
        # Easing cúbico de salida
        self.wipe_progress = 1.0 - math.pow(1.0 - t, 3)
        self.queue_draw()
        
        if t >= 1.0:
            self.animating = False
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _inside_pill(self, x: float, y: float) -> bool:
        return (self.pill_x <= x <= self.pill_x + self.pill_w and 
                self.pill_y <= y <= self.pill_y + self.pill_h)

    def _set_cursor(self, name: str) -> None:
        gw = self.get_window()
        if gw is not None:
            display = self.get_display() or Gdk.Display.get_default()
            if display:
                gw.set_cursor(Gdk.Cursor.new_from_name(display, name))

    def _on_motion(self, widget: Gtk.Widget, event: Gdk.EventMotion) -> bool:
        hovered = self._inside_pill(event.x, event.y)
        if hovered != self.is_pill_hovered:
            self.is_pill_hovered = hovered
            self._set_cursor("pointer" if hovered else "default")
            self.queue_draw()
        return False

    def _on_button_press(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1 and self._inside_pill(event.x, event.y):
            self.is_pill_pressed = True
            self.queue_draw()
            return True
        return False

    def _on_button_release(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1 and self.is_pill_pressed:
            self.is_pill_pressed = False
            self.queue_draw()
            if self._inside_pill(event.x, event.y):
                self.close_action()
            return True
        return False

    def _on_leave(self, widget: Gtk.Widget, event: Gdk.EventCrossing) -> bool:
        if self.is_pill_hovered:
            self.is_pill_hovered = False
            self._set_cursor("default")
            self.queue_draw()
        return False

    def _on_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
        # 1. Aplicar Wipe Transition Mask
        if self.animating:
            cr.save()
            cr.rectangle(0, 0, self.card_w * self.wipe_progress, self.card_h)
            cr.clip()

        # 2. Renderizar Fondo Card Glassmorphism
        cr.save()
        CairoGeometry.rounded_rectangle(cr, 0.5, 0.5, self.card_w - 1, self.card_h - 1, radius=18.0)
        cr.set_source_rgba(0.08, 0.09, 0.12, 0.95)  # Fondo oscuro elegante
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.12)     # Borde sutil
        cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

        # 3. Avatar con Recorte Redondeado
        img_sz = 56
        img_x = self.padding
        img_y = (self.card_h - img_sz) / 2
        cr.save()
        CairoGeometry.rounded_rectangle(cr, img_x, img_y, img_sz, img_sz, radius=img_sz / 2.0)
        cr.clip()
        scaled_avatar = self.avatar_pixbuf.scale_simple(img_sz, img_sz, GdkPixbuf.InterpType.BILINEAR)
        if scaled_avatar:
            Gdk.cairo_set_source_pixbuf(cr, scaled_avatar, img_x, img_y)
            cr.paint()
        cr.restore()

        # 4. Textos con Pango (Manrope)
        text_x = img_x + img_sz + 14
        max_text_w = self.pill_x - text_x - 8
        
        # Título Principal
        PangoTypography.draw_text(
            cr,
            text="KDE Plasma 6 Wayland HUD",
            x=text_x,
            y=img_y + 4,
            max_width=max_text_w,
            font_desc="Manrope SemiBold 13",
            color_rgba=(0.96, 0.97, 1.0, 0.98),
            ellipsize=True
        )
        
        # Subtítulo Descriptivo
        PangoTypography.draw_text(
            cr,
            text="Python 3.13 • GTK3 • LayerShell • Cairo • Pango",
            x=text_x,
            y=img_y + 28,
            max_width=max_text_w,
            font_desc="Manrope Regular 11",
            color_rgba=(0.62, 0.66, 0.75, 0.90),
            ellipsize=True
        )

        # 5. Pill de Cerrar
        cr.save()
        pill_radius = self.pill_h / 2.0
        CairoGeometry.rounded_rectangle(cr, self.pill_x, self.pill_y, self.pill_w, self.pill_h, pill_radius)
        if self.is_pill_pressed:
            cr.set_source_rgba(0.92, 0.22, 0.22, 0.9)
        elif self.is_pill_hovered:
            cr.set_source_rgba(0.85, 0.20, 0.20, 0.6)
        else:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.fill()

        # Cruz 'X'
        cx, cy = self.pill_x + self.pill_w / 2.0, self.pill_y + self.pill_h / 2.0
        sz = 4.0
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0 if self.is_pill_hovered else 0.7)
        cr.set_line_width(1.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(cx - sz, cy - sz)
        cr.line_to(cx + sz, cy + sz)
        cr.stroke()
        cr.move_to(cx + sz, cy - sz)
        cr.line_to(cx - sz, cy + sz)
        cr.stroke()
        cr.restore()

        if self.animating:
            cr.restore()

        return True

# -------------------------------------------------------------------------
# 5. Ventana Principal de Capa Wayland (Layer Shell)
# -------------------------------------------------------------------------
class FloatingHUDWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("WaylandHUDCard")
        self.set_decorated(False)
        self.set_resizable(False)

        # Habilitar canal alfa RGBA
        screen = self.get_screen()
        if screen and screen.is_composited():
            visual = screen.get_rgba_visual()
            if visual:
                self.set_visual(visual)
        self.set_app_paintable(True)

        # Limpiar canvas
        self.connect("draw", self._on_window_draw)

        # Inicializar Layer Shell ANTES de mostrar o realizar
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_exclusive_zone(self, 0)  # Flotante, no empuja paneles
        
        # Anclajes en la esquina superior derecha
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 28)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 28)

        # Instanciar e incrustar la Card
        self.card = ProductionHUDCardWidget(close_action=self.on_close)
        self.add(self.card)

        # Configurar máscara de Click-Through
        self.connect("realize", self._on_realize)

    def _on_window_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.restore()
        return False

    def _on_realize(self, widget: Gtk.Widget) -> None:
        gdk_win = self.get_window()
        if gdk_win:
            rect = cairo.RectangleInt(0, 0, self.card.card_w, self.card.card_h)
            region = cairo.Region(rect)
            gdk_win.input_shape_combine_region(region, 0, 0)

    def on_close(self) -> None:
        self.destroy()
        Gtk.main_quit()

# -------------------------------------------------------------------------
# 6. Punto de Entrada
# -------------------------------------------------------------------------
def main() -> None:
    inject_bundled_fonts()
    app = FloatingHUDWindow()
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
