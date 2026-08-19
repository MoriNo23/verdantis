"""Pycairo Advanced 2D Vector Engine for UI Cards, Pills & Shaders."""

import math
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf

class CairoGeometry:
    @staticmethod
    def rounded_rectangle(
        cr: cairo.Context,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float
    ) -> None:
        deg = math.pi / 180.0
        r = min(radius, width / 2.0, height / 2.0)
        cr.new_sub_path()
        cr.arc(x + width - r, y + r, r, -90 * deg, 0 * deg)
        cr.arc(x + width - r, y + height - r, r, 0 * deg, 90 * deg)
        cr.arc(x + r, y + height - r, r, 90 * deg, 180 * deg)
        cr.arc(x + r, y + r, r, 180 * deg, 270 * deg)
        cr.close_path()

class CairoCardRenderer:
    @staticmethod
    def draw_card(
        cr: cairo.Context,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float = 16.0,
        bg_rgba: tuple[float, float, float, float] = (0.09, 0.10, 0.13, 0.94),
        border_rgba: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.12)
    ) -> None:
        cr.save()
        CairoGeometry.rounded_rectangle(cr, x, y, width, height, radius)
        cr.set_source_rgba(*bg_rgba)
        cr.fill_preserve()
        cr.set_source_rgba(*border_rgba)
        cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

    @staticmethod
    def draw_clipped_pixbuf(
        cr: cairo.Context,
        pixbuf: GdkPixbuf.Pixbuf,
        x: float,
        y: float,
        w: float,
        h: float,
        radius: float = 12.0
    ) -> None:
        cr.save()
        CairoGeometry.rounded_rectangle(cr, x, y, w, h, radius)
        cr.clip()
        scaled = pixbuf.scale_simple(int(w), int(h), GdkPixbuf.InterpType.BILINEAR)
        if scaled is not None:
            Gdk.cairo_set_source_pixbuf(cr, scaled, x, y)
            cr.paint()
        cr.restore()

    @staticmethod
    def draw_close_pill(
        cr: cairo.Context,
        x: float,
        y: float,
        w: float,
        h: float,
        is_hovered: bool = False,
        is_pressed: bool = False
    ) -> None:
        cr.save()
        r = h / 2.0
        CairoGeometry.rounded_rectangle(cr, x, y, w, h, r)
        
        if is_pressed:
            cr.set_source_rgba(0.92, 0.23, 0.23, 0.85)
        elif is_hovered:
            cr.set_source_rgba(0.85, 0.20, 0.20, 0.60)
        else:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.fill()

        cx, cy = x + w / 2.0, y + h / 2.0
        sz = 4.0
        alpha = 1.0 if (is_hovered or is_pressed) else 0.65
        cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
        cr.set_line_width(1.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        
        cr.move_to(cx - sz, cy - sz)
        cr.line_to(cx + sz, cy + sz)
        cr.stroke()
        
        cr.move_to(cx + sz, cy - sz)
        cr.line_to(cx - sz, cy + sz)
        cr.stroke()
        cr.restore()

class CairoWipeShader:
    @staticmethod
    def apply_horizontal_wipe(
        cr: cairo.Context,
        x: float,
        y: float,
        max_width: float,
        height: float,
        progress: float
    ) -> None:
        p = max(0.0, min(1.0, progress))
        cr.rectangle(x, y, max_width * p, height)
        cr.clip()
