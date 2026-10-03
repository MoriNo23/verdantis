"""Helpers compartidos de render/pixel-check para los tests de verdantis.

La auditoría de suite encontró `rrect`, carga de píxeles y la danza
allocation+draw duplicadas en 5 archivos. Viven acá con una sola firma.

Orden de imports: este módulo NO importa Gdk a nivel top (cargaría la 4.0);
lo hace dentro de las funciones, después de que el test ya importó
wayland_popup (que fija la 3.0).
"""
import math

import cairo


def rrect(cr, x, y, w, h, r):
    """Rounded rect clockwise — misma forma que el helper de _draw."""
    r = min(r, w / 2, h / 2)
    cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def alloc_and_draw(widget, width, height, hover=False):
    """Allocation forzada + `_draw` headless sobre superficie nueva.

    Devuelve la superficie flushed (listo para leer píxeles o write_to_png).
    """
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    a = Gdk.Rectangle()
    a.x = a.y = 0
    a.width, a.height = width, height
    widget.get_allocation = lambda a=a: a
    widget._hover = hover or getattr(widget, "_hover", False)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    widget._draw(widget, cairo.Context(surf))
    surf.flush()
    return surf


def pixbuf_pixels(pb):
    """Lista 2D de (R,G,B,A) por píxel desde un GdkPixbuf."""
    raw = pb.get_pixels()
    n = pb.get_n_channels()
    rs = pb.get_rowstride()
    w, h = pb.get_width(), pb.get_height()
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            off = y * rs + x * n
            row.append((raw[off], raw[off + 1], raw[off + 2],
                        raw[off + 3] if n == 4 else 255))
        out.append(row)
    return out


def surface_pixels(surface):
    """(R,G,B,A) por píxel desde una superficie cairo ARGB32."""
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    pb = Gdk.pixbuf_get_from_surface(
        surface, 0, 0, surface.get_width(), surface.get_height())
    return pixbuf_pixels(pb)


def png_pixels(path):
    """(R,G,B,A) por píxel desde un PNG en disco."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    return pixbuf_pixels(GdkPixbuf.Pixbuf.new_from_file(path))
