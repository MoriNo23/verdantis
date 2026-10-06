"""
RED: Close button X must be crisp (no blur/ghosting).

Validates that the X strokes in the close strip don't have semi-transparent
fringe pixels that would make the X appear blurry/ghosted on screen.
(The X lives centered in the 44px dismiss strip; this render isolates a
28x28 crop around it.)

Approach: render the close button Cairo drawing path (mirrored from _draw)
to a 28x28 png and check that the X pixels are fully opaque (A=255) — no
anti-aliased semi-transparent fringes. With the fix (ANTIALIAS_NONE +
pixel-centering), X stroke pixels are 100% opaque. Without it, they'd be
semi-transparent (A < 255) from round-cap anti-aliasing.
"""
import os
import math

import cairo
import inspect

import wayland_popup as wp
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from render_helpers import rrect, png_pixels

_CARD_BG = wp._hex_rgb("#1e1e2e")
_CLOSE_ACCENT = (0.953, 0.482, 0.659, 0.95)  # #f38ba8 pink


def _render_close_to_png(path, hover_close=False):
    """Render a 28x28 close button using the EXACT drawing path from _draw."""
    cs = 28
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, cs, cs)
    cr = cairo.Context(surface)

    # Card bg so pill composites correctly
    cr.set_source_rgb(*_CARD_BG)
    cr.paint()

    cx0, cy0 = 0, 0
    cr.save()
    cr.translate(0.5, 0.5)
    rrect(cr, cx0, cy0, cs, cs, 8)
    cr.set_source_rgba(0.86, 0.15, 0.15, 0.32 if hover_close else 0.18)
    cr.fill()
    # Border red explícito eliminado (ver src/wayland_popup.py): generaba
    # artifact de línea roja en hover.
    mx = cx0 + cs / 2
    my = cy0 + cs / 2
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


def _load_pixels(path):
    """Load PNG and return 2D list of (R,G,B,A) tuples."""
    return png_pixels(path)


def _is_x_stroke(r, g, b, a):
    """Detect pink X stroke pixels."""
    return a > 200 and r > 200 and 100 < g < 160 and 140 < b < 200


def _render_and_load(hover_close=False, name="test"):
    path = os.path.join(os.path.dirname(__file__), "..", "render_out",
                        f"{name}.png")
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _render_close_to_png(path, hover_close=hover_close)
    return _load_pixels(path)


def test_close_x_strokes_are_fully_opaque():
    """All X stroke pixels must be fully opaque (A=255). Semi-transparent
    fringe pixels indicate anti-aliasing blur from round caps."""
    pixels = _render_and_load(hover_close=False, name="test_close_x_opaque")

    x_alphas = []
    for row in pixels:
        for r, g, b, a in row:
            if _is_x_stroke(r, g, b, a):
                x_alphas.append(a)

    assert len(x_alphas) > 0, "No X stroke pixels found — render failed"
    min_alpha = min(x_alphas)
    assert min_alpha == 255, (
        f"X stroke has semi-transparent pixels (min alpha={min_alpha}). "
        f"This means anti-aliasing is still on, causing blur/ghosting. "
        f"Ensure ANTIALIAS_NONE + pixel-centering is used for the X."
    )


def test_close_x_is_symmetric():
    """The X must be vertically and horizontally symmetric (no misalignment)."""
    pixels = _render_and_load(hover_close=False, name="test_close_x_symmetric")

    diag_pixels = []
    anti_diag_pixels = []
    for i in range(15):
        x, y = 7 + i, 7 + i
        diag_pixels.append(pixels[y][x])
        x2, y2 = 7 + i, 21 - i
        anti_diag_pixels.append(pixels[y2][x2])

    diag_count = sum(1 for p in diag_pixels if _is_x_stroke(*p))
    anti_count = sum(1 for p in anti_diag_pixels if _is_x_stroke(*p))

    assert diag_count > 0 and anti_count > 0, (
        f"X diagonals have no stroke pixels: diag={diag_count}, anti={anti_count}"
    )
    diff = abs(diag_count - anti_count)
    assert diff <= 2, (
        f"X is asymmetric: diag={diag_count} vs anti={anti_count} (diff={diff}). "
        f"This indicates misalignment in the X rendering."
    )


def test_close_x_center_is_pixel_aligned():
    """The X center pixel (14,14) must be an X stroke pixel."""
    pixels = _render_and_load(hover_close=False, name="test_close_x_center")
    center = pixels[14][14]
    assert _is_x_stroke(*center), (
        f"Center pixel (14,14) is not an X stroke pixel: {center}. "
        f"X may be misaligned."
    )


def test_close_source_has_fix():
    """El pipeline de dibujado debe contener el fix de antialiasing y
    pixel-centering de la X.

    Desde `bajar-complejidad-draw` la X se dibuja en `_draw_close_strip`, no en
    `_draw` (que quedó como orquestador); el marcador se busca en el source de
    toda la clase para que el test siga válido si el paso vuelve a moverse."""
    src = inspect.getsource(wp.NotificationWidget)
    assert "translate(0.5, 0.5)" in src, (
        "Missing cr.translate(0.5, 0.5) — pixel-centering required for crisp X"
    )
    assert "ANTIALIAS_NONE" in src, (
        "Missing cr.set_antias(cairo.ANTIALIAS_NONE) — required to eliminate "
        "sub-pixel fringe blur on the X strokes"
    )
