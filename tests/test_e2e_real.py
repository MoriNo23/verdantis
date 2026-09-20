"""
End-to-end verification of the three notification fixes using the REAL code
paths (no fakes/mirrors):

  1. Close-button X rendering — calls the actual NotificationWidget._draw onto
     a real Cairo surface with a persistent+hovered widget and asserts the X is
     crisp (fully-opaque pink pixels, pixel-centered, present only on hover).
  2. Burst batching — drives the real NotificationManager with its real GLib
     scheduler over a real GLib main loop: a 5-notification burst must NOT all
     appear at once; toasts are revealed one per STAGGER_MS.
  3. Deduplication — two identical notifications within DEDUP_WINDOW must not
     stack: the second replaces the first (one active toast, not two).

Requires a live display (WAYLAND_DISPLAY) so Gtk widgets can be constructed.
The manager's popup is replaced with an off-screen fake that records activity
without opening real Wayland windows, but the scheduling/timing is 100% real.
"""
import os
import sys
import time
import types

os.environ.setdefault("GDK_BACKEND", "wayland")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cairo
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib  # noqa: E402

from render_helpers import surface_pixels  # noqa: E402

import verdantis_daemon as vd  # noqa: E402
import wayland_popup as wp  # noqa: E402


# ── 1. Close-button X rendering (real _draw) ────────────────────────────────

def _render_real_close_button(W=360, H=120):
    """Build a REAL NotificationWidget (persistent + hovered) and draw it
    through the actual _draw method onto a Cairo surface."""
    widget = wp.NotificationWidget(
        app_name="TestApp",
        app_icon="",
        titulo="Título de prueba",
        cuerpo="Cuerpo de la notificación de prueba.",
        icon_path=None,
        image_path=None,
        accent="#80cbc4",
        persistent=True,
    )
    widget._hover = True  # hover over the card -> close strip should draw

    # The widget is not realized; feed it a fixed allocation so _draw proceeds.
    widget.get_allocation = lambda: types.SimpleNamespace(width=W, height=H)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surface)
    widget._draw(None, cr)
    surface.flush()

    path = os.path.join(os.path.dirname(__file__), "..", "render_out",
                        "e2e_close_real.png")
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    surface.write_to_png(path)

    # Read pixels back via GdkPixbuf for channel data (helper compartido).
    pixels = surface_pixels(surface)
    return pixels, path, widget


def _is_x_pink(r, g, b, a):
    return a > 200 and r > 200 and 100 < g < 160 and 140 < b < 200


def test_e2e_close_button_renders_crisp():
    pixels, path, _ = _render_real_close_button()
    H = len(pixels)
    W = len(pixels[0])

    # X center in the strip: franja de descarte de 44px, X centrada en
    # (W - 22, H/2) = (338, 60) para una card 360x120.
    cx, cy = W - 22, H // 2
    x_pixels = []
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            x, y = cx + dx, cy + dy
            if 0 <= x < W and 0 <= y < H:
                r, g, b, a = pixels[y][x]
                if _is_x_pink(r, g, b, a):
                    x_pixels.append(a)
    assert x_pixels, "No pink X pixels rendered by the real _draw (close button missing)"

    # Anti-blur invariant: the X must be fully covered (no partially-covered
    # anti-aliased fringe pixels). With ANTIALIAS_NONE the strokes are
    # hard-edged; any pink pixel whose alpha sits in the "fringe" band
    # (10..249) would mean sub-pixel AA bleed = the ghosting bug. The only
    # sub-255 value allowed is the translucent card base (>=250), which is
    # by design and does not blur.
    fringe = [a for a in x_pixels if 10 <= a <= 249]
    assert not fringe, (
        f"X stroke has anti-aliased fringe pixels (alpha in 10..249: "
        f"{sorted(set(fringe))}) — ANTIALIAS_NONE fix missing/broken in live "
        f"code. PNG: {path}"
    )
    assert min(x_pixels) >= 250, (
        f"X stroke alpha too low (min={min(x_pixels)}) — expected near-opaque. "
        f"PNG: {path}"
    )

    # The close pill background should be reddish and confined to the top-right.
    # It's drawn at alpha 0.18 over the dark card (#1e1e2e), so the composited
    # pixel is a muted red (~64,31,45), not the raw (219,38,38). Detect muted red.
    pill_red = 0
    for y in range(6, 34):
        for x in range(312, 341):  # exact pill bounds (cx0=312, cx1=340)
            r, g, b, a = pixels[y][x]
            if r > 55 and r > g + 12 and r > b + 8 and g < 90 and b < 90:
                pill_red += 1
    assert pill_red > 0, "Close pill background (muted red) not found top-right"


def test_e2e_close_button_only_on_hover():
    """Without hover, the persistent widget must NOT draw the close pill/X."""
    widget = wp.NotificationWidget(
        app_name="TestApp", app_icon="", titulo="x", cuerpo="y",
        icon_path=None, image_path=None, accent="#80cbc4",
        persistent=True,
    )
    widget._hover = False
    widget.get_allocation = lambda: types.SimpleNamespace(width=360, height=120)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, 120)
    cr = cairo.Context(surface)
    widget._draw(None, cr)
    surface.flush()
    pixels = surface_pixels(surface)
    # Scan la franja de descarte (donde viviría la X): sin hover no hay rosa.
    strip_x0 = 360 - wp.NotificationWidget._CLOSE_STRIP_W
    for y in range(0, 120):
        for x in range(strip_x0, 360):
            if _is_x_pink(*pixels[y][x]):
                assert False, "Close X drawn even without hover (should be hidden)"


# ── 2 & 3. Batching + dedup with the REAL GLib scheduler ────────────────────

def _fake_show(mgr):
    """Replace _show_popup with an off-screen recorder that builds a REAL
    NotificationWidget (the card that owns the close button + click logic) but
    NO Wayland window and NO auto-close timers. This keeps the close-button,
    hover, and click-to-close behavior 100% real while avoiding real GTK
    windows / 50ms progress timers leaking into the shared GLib context."""
    def fake_show(nid, kwargs):
        widget = wp.NotificationWidget(
            app_name=kwargs.get("app_name", ""),
            app_icon=kwargs.get("app_icon", "") or "",
            titulo=kwargs.get("titulo", ""),
            cuerpo=kwargs.get("cuerpo", ""),
            icon_path=kwargs.get("icon_path"),
            image_path=kwargs.get("image_path"),
            accent=kwargs.get("accent", "#80cbc4"),
            image_data_raw=kwargs.get("image_data_raw"),
            on_click=kwargs.get("on_click"),
            on_close=kwargs.get("on_close"),
            app_label=kwargs.get("app_label"),
            hide_title=kwargs.get("hide_title", False),
            persistent=(kwargs.get("duration", 6000) == 0),
        )
        idx = len(mgr._active)
        try:
            widget.set_stack_margin(idx)  # no-op without a window
        except Exception:
            pass
        # The manager's _close_id()/close_all() call popup._close(); on the real
        # WaylandPopup that destroys the window + fires _on_close. Here we make
        # it a no-op (the manager already does the _active removal + drain) so
        # closing logic stays real without spawning GTK windows/timers.
        widget._close = lambda: None
        mgr._active.append((nid, widget))
    return fake_show


def _pump(duration):
    """Drive the REAL default GLib main context for `duration` real seconds,
    processing timers as their real deadlines elapse. This is the same context
    GLib.timeout_add (the manager's real scheduler) registers into — so the
    batching/dedup timers actually fire. Runs on the main thread: no cross-thread
    race between timeout_add and the loop."""
    ctx = GLib.MainContext.default()
    deadline = time.time() + duration
    while time.time() < deadline:
        ctx.iteration(False)  # process any due timers without blocking
        time.sleep(0.005)


def test_e2e_burst_batched_real_scheduler():
    mgr = vd.NotificationManager(corner="top-right")  # scheduler=None -> real GLib
    mgr._show_popup = _fake_show(mgr)

    # Fire a burst of 5 identical-urgency notifications almost instantly.
    for i in range(5):
        mgr.notify(summary="n{}".format(i), app_name="app")
    # Nothing should be shown yet (pump waits STAGGER_MS before first reveal).
    assert len(mgr._pending) == 5, mgr._pending
    assert len(mgr._active) == 0

    # NOTA (auditoría): antes se alineaba con wall-clock (==1 tras 500ms),
    # pero bajo la carga de la suite completa los timers GLib disparan TARDE
    # (0 activos a los 500ms) o justo-temprano, y el test era flaky en ambas
    # direcciones. El intento real del test es "se revelan DE A UNO, nunca
    # todos juntos", así que bombeamos en pasos cortos y verificamos que el
    # conteo NUNCA salta por más de 1 por intervalo de stagger.
    step, deadline = 0.05, time.time() + 8.0
    seen = 0
    while seen < 5 and time.time() < deadline:
        _pump(step)
        active = len(mgr._active)
        assert active - seen <= 1, (
            "stagger roto: saltaron {}->{} activos en un paso de "
            "{}s (deberían revelarse de a uno)".format(seen, active, step)
        )
        seen = active
    assert len(mgr._active) == 5, "burst not fully drained: {}".format(
        len(mgr._active))


def test_e2e_dedup_replaces_not_stacks_real_scheduler():
    mgr = vd.NotificationManager(corner="top-right")
    mgr._show_popup = _fake_show(mgr)

    n1 = mgr.notify(summary="dup", app_name="app")
    _pump(0.5)  # n1 shown (active)
    assert len(mgr._active) == 1

    n2 = mgr.notify(summary="dup", app_name="app")  # identical within window
    # At this instant the duplicate must have closed n1 and enqueued n2,
    # never stacking two identical toasts.
    active_ids = [nid for nid, _ in mgr._active]
    assert n1 not in active_ids, "duplicate left the old toast active"
    assert len(mgr._pending) == 1

    _pump(0.5)  # n2 revealed
    shown = [nid for nid, _ in mgr._active]
    assert shown == [n2], "expected only the replacement toast active: {}".format(
        shown)
    assert len(mgr._active) == 1


# ── Operator follow-up: non-auto-closing (persistent) toasts must have a ──────
# ── working close button (click-to-close), per expire_timeout=0. And the ──────
# ── suspected "clicking close on one closes ALL" bug must be disproven. ───────

def _render_widget(widget, W=360, H=120):
    """Force a synchronous _draw so the close-rect is computed for a
    non-realized widget (normally done by GTK's draw signal)."""
    widget.get_allocation = lambda: types.SimpleNamespace(width=W, height=H)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surface)
    widget._draw(None, cr)
    return surface


def test_e2e_persistent_toast_is_closeable():
    """expire_timeout=0 -> persistent popup, and clicking the red X pill
    actually closes ONLY that toast (real _on_button_press -> _on_close ->
    manager _on_closed). This is the toast-never-closes-itself case the
    operator asked to confirm."""
    mgr = vd.NotificationManager(corner="top-right")
    mgr._show_popup = _fake_show(mgr)

    nid = mgr.notify(summary="sticky", app_name="app", expire_timeout=0)
    _pump(0.5)  # shown (active), NOT auto-expired (duration=0)

    assert len(mgr._active) == 1
    _nid, card = mgr._active[0]
    # The widget must be flagged persistent (so the X pill draws + click is armed).
    assert card._persistent is True, "expire_timeout=0 toast not persistent"
    assert card._on_close is not None, "persistent toast should wire a close callback"

    # Render with hover so the close rect is computed, then click the X center.
    card._hover = True
    _render_widget(card)
    cx0, cy0, cx1, cy1 = card._close_rect
    mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2

    class _Ev:
        x = mx
        y = my

    closed = []
    orig = mgr._on_closed

    def spy_closed(cid):
        closed.append(cid)
        return orig(cid)

    mgr._on_closed = spy_closed
    # Real button-press handler (the one wired in NotificationWidget.__init__).
    card._on_button_press(card, _Ev())

    assert closed == [nid], "clicking the X did not close the persistent toast"
    assert len(mgr._active) == 0, "toast still active after close-button click"


def test_e2e_close_one_does_not_close_all():
    """Suspected bug: clicking the close (X) on ONE toast closes ALL of them.
    This test proves the opposite — only the clicked persistent toast closes,
    the other (mixed auto + persistent) toasts stay put."""
    mgr = vd.NotificationManager(corner="top-right")
    mgr._show_popup = _fake_show(mgr)

    # Mix: a persistent (sticky) toast, an auto-closing one, another persistent.
    n_auto = mgr.notify(summary="auto", app_name="app", expire_timeout=5000)
    n_sticky1 = mgr.notify(summary="sticky1", app_name="app", expire_timeout=0)
    n_sticky2 = mgr.notify(summary="sticky2", app_name="app", expire_timeout=0)
    _pump(2.0)  # all three revealed (one per 400ms)

    active_ids = [nid for nid, _ in mgr._active]
    assert sorted(active_ids) == sorted([n_auto, n_sticky1, n_sticky2]), active_ids

    # Find the card for n_sticky2 and click its X.
    target = [p for (nid, p) in mgr._active if nid == n_sticky2][0]
    card = target
    assert card._persistent is True
    card._hover = True
    _render_widget(card)
    cx0, cy0, cx1, cy1 = card._close_rect
    mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2

    class _Ev:
        x = mx
        y = my

    closed = []
    orig = mgr._on_closed

    def spy_closed(cid):
        closed.append(cid)
        return orig(cid)

    mgr._on_closed = spy_closed
    card._on_button_press(card, _Ev())

    # Only the clicked toast closed; the other two remain active.
    assert closed == [n_sticky2], "clicking one X closed the wrong toast(s): {}".format(
        closed)
    remaining = [nid for nid, _ in mgr._active]
    assert sorted(remaining) == sorted([n_auto, n_sticky1]), (
        "clicking one X closed more than one toast (suspected bug confirmed): "
        "{}".format(remaining))
    assert len(mgr._active) == 2, "expected 2 toasts still active, got {}".format(
        len(mgr._active))


def test_e2e_close_all_closes_everything():
    """close_all() is the intended 'dismiss everything' path (e.g. a global
    gesture). It must clear active + pending + pump flag."""
    mgr = vd.NotificationManager(corner="top-right")
    mgr._show_popup = _fake_show(mgr)

    for i in range(4):
        mgr.notify(summary="n{}".format(i), app_name="app")
    _pump(2.0)  # all 4 revealed
    assert len(mgr._active) == 4

    mgr.close_all()
    assert mgr._active == [], "close_all left active toasts"
    assert mgr._pending == [], "close_all left pending toasts"
    assert mgr._pump_scheduled is False, "close_all left pump scheduled"


def test_e2e_persistent_close_button_renders_on_hover():
    """A real persistent popup (duration=0) must draw the X close pill when
    hovered. Mirrors the manual 'hover the sticky toast -> red X appears' step."""
    mgr = vd.NotificationManager(corner="top-right")
    mgr._show_popup = _fake_show(mgr)
    nid = mgr.notify(summary="sticky", app_name="app", expire_timeout=0)
    _pump(0.5)  # past first stagger -> revealed + active (duration=0, no auto-close)
    assert mgr._active, "persistent toast was not revealed"
    _, widget = mgr._active[0]
    assert widget._persistent is True

    widget._hover = True
    surface = _render_widget(widget)
    pixels = surface_pixels(surface)
    x_pink = 0
    # La X vive centrada en la franja de descarte (44px, borde derecho):
    # scan de la franja completa alrededor del centro vertical de la card.
    strip_x0 = 360 - wp.NotificationWidget._CLOSE_STRIP_W
    for y in range(60 - 16, 60 + 17):
        for x in range(strip_x0, 360):
            if _is_x_pink(*pixels[y][x]):
                x_pink += 1
    assert x_pink > 0, "persistent (expire_timeout=0) toast shows no close X on hover"
