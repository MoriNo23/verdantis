#!/usr/bin/env python3
"""Render the NotificationWidget close button headlessly to a PNG so we can
inspect the rendering artifacts (blur / ghosting / misalignment).

This works by extracting just the close-button Cairo drawing path from
`_draw()` and rendering it on a plain cairo surface — no Gtk.DrawingArea
allocation needed (which fails headless without a display).
"""
import os
os.environ.setdefault("GDK_BACKEND", "offscreen")

import math
import cairo

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import wayland_popup as wp
from wayland_popup import _hex_rgb

_CARD_BG = _hex_rgb("#1e1e2e")
_CLOSE_ACCENT = (0.953, 0.482, 0.659, 0.95)  # #f38ba8 pink


def rrect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def render_close_isolated(path, width=360, height=120, hover=True,
                          hover_close=False):
    """Render the dismiss strip (franja de descarte) on a card background."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)

    sw = 44   # _CLOSE_STRIP_W

    # Card background
    bg_alpha = 0.92 if hover else 0.85
    cr.set_source_rgba(*_CARD_BG, bg_alpha)
    rrect(cr, 0, 0, width, height, 12)
    cr.fill()

    # Card border
    cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
    cr.set_line_width(1.5)
    rrect(cr, 0.5, 0.5, width - 1, height - 1, 12)
    cr.stroke()

    if hover:
        sx0 = width - sw
        # Mirror the exact drawing block from _draw (strip + crisp X fix)
        cr.save()
        cr.new_path()
        rrect(cr, 0, 0, width, height, 12)
        cr.clip()
        if hover_close:
            cr.set_source_rgba(0.86, 0.15, 0.15, 0.32)
        else:
            cr.set_source_rgba(0.86, 0.15, 0.15, 0.18)
        cr.rectangle(sx0, 0, sw, height)
        cr.fill()
        cr.translate(0.5, 0.5)
        # Hairline izquierdo de la franja
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.06)
        cr.set_line_width(1.0)
        cr.move_to(sx0, 12)
        cr.line_to(sx0, height - 12)
        cr.stroke()
        # X centrada en la franja (ANTIALIAS_NONE: nítida, sin fringe blur)
        mx = sx0 + sw / 2
        my = height / 2
        inset = 7
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgba(*_CLOSE_ACCENT)
        cr.set_line_width(2.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(mx - inset, my - inset)
        cr.line_to(mx + inset, my + inset)
        cr.move_to(mx + inset, my - inset)
        cr.line_to(mx - inset, my + inset)
        cr.stroke()
        cr.restore()

    surface.flush()
    surface.write_to_png(path)
    print("wrote", path)


if __name__ == "__main__":
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "render_out")
    os.makedirs(outdir, exist_ok=True)
    render_close_isolated(os.path.join(outdir, "close_persistent_hover.png"))
    render_close_isolated(os.path.join(outdir, "close_hover_close.png"),
                          hover_close=True)
    render_close_isolated(os.path.join(outdir, "close_wipe_active.png"),
                          hover_close=False)
    print("done")
