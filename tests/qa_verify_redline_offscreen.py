#!/usr/bin/env python3
"""Independent QA verification of the close-button red-line fix.

Renders the REAL NotificationWidget._draw path headlessly (offscreen cairo,
not a screenshot) in the hover+hover_close state, then scans the close-pill
region (top-right 28x28) for a floating red outline artifact.

The original bug (t_ba80d727): an explicit red stroke
  cr.set_source_rgba(0.86, 0.15, 0.15, 0.35); cr.set_line_width(1.0); cr.stroke()
on the close pill. Its alpha (0.35) was much higher than the fill (0.18),
reading as a floating red line. The fix removed that stroke.

We assert, at the pixel level, that the close-pill region contains:
  (a) the pink #f38ba8 X (clear hover feedback preserved), and
  (b) NO distinct floating red ring/border around the pill.

Run: .venv/bin/python tests/qa_verify_redline_offscreen.py
"""
import os
import sys
import math

# Respect a live session: if WAYLAND_DISPLAY is set (Mori's KDE session),
# keep 'wayland' so Gtk can actually create the widget; otherwise fall back
# to 'offscreen'. Do NOT force offscreen here (would break GtkStyleContext).
if not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

import wayland_popup as wp


def build_widget():
    """Construct a persistent NotificationWidget and force hover+close-hover."""
    w = wp.NotificationWidget(
        app_name="QA Test",
        app_icon=None,
        titulo="Titulo de prueba",
        cuerpo="Cuerpo de la notificacion para verificar el fix.",
        icon_path=None,
        image_path=None,
        accent="#89b4fa",
        persistent=True,
    )
    # Force the visual states that trigger the close pill (src/wayland_popup.py:905)
    w._persistent = True
    w._hover = True
    w._hover_close = True
    return w


def render_real_draw(w, width=360, height=120):
    """Render the widget's actual _draw onto a cairo ImageSurface.

    _draw reads self.get_allocation().width/height and otherwise only uses
    cairo/Pango (display-independent). We stub get_allocation() so no display
    is required, then call _draw directly with a cairo context.
    """
    rect = Gdk.Rectangle()
    rect.x, rect.y, rect.width, rect.height = 0, 0, width, height

    def _fake_alloc():
        return rect

    w.get_allocation = _fake_alloc
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)
    w._draw(w, cr)
    surface.flush()
    return surface


def load_pixels(surface):
    """Read ARGB32 pixels directly from the cairo surface (BGRA byte order)."""
    w = surface.get_width()
    h = surface.get_height()
    stride = surface.get_stride()
    raw = surface.get_data()
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            off = y * stride + x * 4
            # cairo ARGB32 memory layout is BGRA
            b = raw[off]
            g = raw[off + 1]
            r = raw[off + 2]
            a = raw[off + 3]
            row.append((r, g, b, a))
        out.append(row)
    return out


def is_pink_x(r, g, b, a):
    # Close X stroke color #f38ba8 = (244, 154, 168) at alpha ~0.95.
    # Rendered pixels composite to ~(235, 118, 162, 254) over the semi-transparent
    # red pill + card, so we allow a tolerant window around that.
    if a < 180:
        return False
    return r > 200 and 100 < g < 190 and 120 < b < 210


def is_red_artifact(r, g, b, a):
    """A floating red *outline* (the bug): the original bug stroked a 1px red
    line at rgba(0.86,0.15,0.15,0.35) around the close pill. Composited over
    the dark card the FILL interior is dim red (~ (88,30,41) at alpha 0.32),
    but the STROKE ring is BRIGHTER (~ r>=110) because its alpha (0.35) sits
    on top of the fill. The genuine artifact is that brighter ring, NOT the
    uniform pill fill (which is intended hover feedback). It is NOT the pink
    X (#f38ba8 family: blue is high, b>120) nor the gray card edge.
    """
    if a < 150:
        return False
    # Brighter than the uniform pill fill (r~88) — only a stroke ring qualifies
    if r < 110:
        return False
    # Red must clearly dominate over green and blue (the ring's signature)
    if not (r > g + 30 and r > b + 30):
        return False
    # Exclude the pink X (#f38ba8 family: blue is high)
    if b > 120:
        return False
    # Exclude gray card edge / near-neutral pixels (r~g~b)
    if r < g - 5 or g > b + 25:
        return False
    return True


def negative_control_red_stroke_detected():
    """Guard: if the red-stroke bug were reintroduced, this must FAIL.

    We monkeypatch NotificationWidget._draw to re-add the offending stroke
    (rgba(0.86,0.15,0.15,0.35) + line_width(1.0) + stroke around the pill) and
    verify is_red_artifact() flags pixels in that case. This proves the pixel
    detector is SENSITIVE to the exact bug, so a PASS on the fixed code means
    something.
    """
    import cairo
    from gi.repository import Gdk

    w = build_widget()
    rect = Gdk.Rectangle()
    rect.x, rect.y, rect.width, rect.height = 0, 0, 360, 120
    w.get_allocation = lambda: rect

    # Re-add the bug: a 1px red outline on the close pill (the original artifact)
    orig_draw = wp.NotificationWidget._draw

    def buggy_draw(self, widget, cr):
        # Draw the normal (fixed) close pill, then add the red stroke.
        orig_draw(self, widget, cr)
        if self._persistent and self._hover:
            cs = 28
            cx_r = 360 - 14 - 6
            cy_t = 6
            cx0, cy0 = cx_r - cs, cy_t
            cr.save()
            cr.translate(0.5, 0.5)
            # pill rounded rect outline
            cr.set_source_rgba(0.86, 0.15, 0.15, 0.35)
            cr.set_line_width(1.0)
            cr.arc(cx0 + 8, cy0 + 8, 8, 0, 2 * math.pi)
            cr.stroke()
            cr.restore()

    wp.NotificationWidget._draw = buggy_draw
    try:
        surface = render_real_draw(w)
    finally:
        wp.NotificationWidget._draw = orig_draw

    px = load_pixels(surface)
    W, H = surface.get_width(), surface.get_height()
    cx_r = W - 14 - 6
    cy_t = 6
    cx0, cy0, cx1, cy1 = cx_r - 28, cy_t, cx_r, cy_t + 28
    red_hits = []
    for y in range(max(0, cy0 - 2), min(H, cy1 + 2)):
        for x in range(max(0, cx0 - 2), min(W, cx1 + 2)):
            r, g, b, a = px[y][x]
            if is_red_artifact(r, g, b, a):
                red_hits.append((x, y, (r, g, b, a)))
    assert len(red_hits) > 0, (
        "NEGATIVE CONTROL FAILED: re-inserted the red-stroke bug but the "
        "detector did not flag any red-artifact pixels — the pixel guard is "
        "not sensitive to the regression."
    )
    print(f"negative-control OK: red-stroke bug re-inserted -> {len(red_hits)} red pixels flagged")
    return True


def source_asserts_no_red_stroke():
    """Source-level regression guard: the _draw source must NOT contain the
    exact offending red-stroke triple (rgba 0.86,0.15,0.15,0.35 + stroke)."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    # The triple only appears in a COMMENT now; assert it's not in a live call.
    # Strip comments to avoid false negatives from the explanatory note.
    no_comment = "\n".join(
        ln for ln in src.splitlines() if not ln.strip().startswith("#")
    )
    assert "0.86, 0.15, 0.15, 0.35" not in no_comment, (
        "SOURCE REGRESSION: red-stroke rgba(0.86,0.15,0.15,0.35) found in live "
        "_draw code — the red-line bug is back."
    )
    print("source-guard OK: no live red-stroke rgba(0.86,0.15,0.15,0.35) in _draw")


def main():
    source_asserts_no_red_stroke()
    negative_control_red_stroke_detected()

    w = build_widget()
    surface = render_real_draw(w)
    px = load_pixels(surface)

    W, H = surface.get_width(), surface.get_height()
    pad = 14
    cs = 28
    cx_r = W - pad - 6
    cy_t = 6
    cx0, cy0, cx1, cy1 = cx_r - cs, cy_t, cx_r, cy_t + cs

    # Scan the close-pill bounding box (+2px margin to catch a floating outline)
    red_hits = []
    pink_hits = []
    for y in range(max(0, cy0 - 2), min(H, cy1 + 2)):
        for x in range(max(0, cx0 - 2), min(W, cx1 + 2)):
            r, g, b, a = px[y][x]
            if is_pink_x(r, g, b, a):
                pink_hits.append((x, y, (r, g, b, a)))
            elif is_red_artifact(r, g, b, a):
                red_hits.append((x, y, (r, g, b, a)))

    print(f"close-pill region: x[{cx0},{cx1}] y[{cy0},{cy1}]")
    print(f"pink X stroke pixels found: {len(pink_hits)}")
    print(f"red-artifact pixels found: {len(red_hits)}")

    ok = True
    if len(pink_hits) == 0:
        print("FAIL: no pink X hover feedback rendered — close button feedback lost")
        ok = False
    else:
        print("PASS: pink #f38ba8 X hover feedback present (clear visual feedback)")

    if len(red_hits) > 0:
        sample = red_hits[:5]
        print(f"FAIL: red-line artifact pixels present (sample={sample})")
        ok = False
    else:
        print("PASS: no floating red outline/line artifact in close-pill region")

    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
