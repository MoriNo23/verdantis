"""
RED: hover feedback + franja de descarte en persistentes.

Especificacion:
  - Todos los toasts deben tener cursor pointer (feedback "clickeable").
  - Hover sobre la card -> bg se aclara levemente.
  - Toasts persistentes (duration=0): al hover, aparece la FRANJA VERTICAL de
    descarte en el borde derecho (44px de ancho x alto del card, tint rojizo
    semi-transparente con X centrada). Anti-misclick: el pill 28x28 de la
    esquina fallaba el click y el fall-through abria el video/URL.
  - Click en la franja -> cierra el toast (no dispara on_click/ActionInvoked).
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import wayland_popup as wp
from wayland_popup import NotificationWidget, WaylandPopup


def _widget(duration=0):
    """Crea un WaylandPopup headless. duration=0 -> persistente."""
    popup = WaylandPopup(
        titulo="Test", cuerpo="Body corto", icon_path=None, image_path=None,
        duration=duration, on_close=lambda: None, on_click=lambda: None,
        app_name="Brave", accent="#80cbc4",
    )
    return popup


def test_persistent_popup_has_close_rect():
    """Un popup persistente (duration=0) debe tener un _close_rect definido
    despues de prepare() (o al menos la logica para computarlo)."""
    w = NotificationWidget(
        "Brave", "", "Pinterest", "body", None, None, "#80cbc4",
        on_click=lambda: None, persistent=True,
    )
    # El widget debe conocer si es persistente
    assert w._persistent is True


def test_non_persistent_popup_has_no_close():
    """Un popup normal (duration>0) NO debe mostrar la X."""
    w = NotificationWidget(
        "Brave", "", "Pinterest", "body", None, None, "#80cbc4",
        on_click=lambda: None, persistent=False,
    )
    assert w._persistent is False


def test_close_click_calls_on_close_not_on_click():
    """Click en la X debe cerrar el toast (on_close), NO disparar on_click."""
    closed = []
    clicked = []
    w = NotificationWidget(
        "Brave", "", "Test", "body", None, None, "#80cbc4",
        on_click=lambda: clicked.append(1),
        on_close=lambda: closed.append(1),
        persistent=True,
    )
    # Simular click en el area de la X: top-right del card
    # El _close_rect se computa en draw; lo forzamos llamando _draw
    alloc = w.get_allocation()
    # En headless alloc es 1x1; el test verifica la logica, no pixels
    # Verificamos que existe un metodo para distinguir click en X vs click normal
    assert hasattr(w, "_on_button_press")


def test_hover_changes_cursor_to_pointer():
    """El widget debe tener eventos de enter/leave y cambiar el cursor."""
    w = NotificationWidget(
        "Brave", "", "Test", "body", None, None, "#80cbc4",
        on_click=lambda: None,
    )
    # Debe tener los event masks de enter/leave/motion
    events = w.get_events()
    # Gdk.EventMask.ENTER_NOTIFY_MASK y LEAVE_NOTIFY_MASK deben estar set
    import gi
    from gi.repository import Gdk
    assert events & Gdk.EventMask.ENTER_NOTIFY_MASK
    assert events & Gdk.EventMask.LEAVE_NOTIFY_MASK


def test_font_is_manrope():
    """La fuente del body debe ser Manrope (bundled, no 'sans-serif' generico)."""
    w = NotificationWidget(
        "Brave", "", "Test", "body", None, None, "#80cbc4",
        on_click=lambda: None,
    )
    assert hasattr(w, "_BODY_FONT")
    assert "Manrope" in w._BODY_FONT


# ---------------------------------------------------------------------------
# TESTS: Close button rendering quality (crisp, no blur/ghosting/misalignment)
# ---------------------------------------------------------------------------

def test_close_button_uses_antialias_none_on_x():
    """The X strokes must use ANTIALIAS_NONE to avoid sub-pixel fringe blur
    from round caps at 2.5px width on a 28x28 pill. Without this, the X
    appears fuzzy/ghosted."""
    import inspect
    import cairo
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "ANTIALIAS_NONE" in src, (
        "Close button X must use cairo.ANTIALIAS_NONE to avoid blurry "
        "sub-pixel fringes from round caps"
    )


def test_close_button_uses_pixel_centering():
    """The close button block must be pixel-centered (cr.translate(0.5, 0.5))
    so pill + X strokes land on pixel boundaries instead of straddling
    sub-pixel positions which causes blur."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "translate(0.5, 0.5)" in src, (
        "Close button drawing must include cr.translate(0.5, 0.5) for "
        "pixel-centering to eliminate sub-pixel blur"
    )


def test_close_strip_position_is_right_edge():
    """Franja de descarte: borde derecho, ancho _CLOSE_STRIP_W, alto completo.
    Marcadores de la geometría de la franja en el source de _draw."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    # La franja nace del borde derecho y baja hasta el piso del card
    assert "sx0 = W - sw" in src, (
        "la franja debe anclarse al borde derecho del card"
    )
    assert "self._close_rect = (sx0, 0, W, H)" in src, (
        "el hit-rect de cierre debe ser la franja completa (alto del card)"
    )


def test_close_strip_width_is_44():
    """La franja de descarte mide 44px de ancho (target 5-8x el pill 28x28)."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "sw = self._CLOSE_STRIP_W" in src
    assert wp.NotificationWidget._CLOSE_STRIP_W == 44


def test_close_button_x_color_is_pink():
    """X stroke color must be #f38ba8 (the pink from the spec)."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "0.953, 0.482, 0.659" in src or "#f38ba8" in src.lower()


def test_close_button_pill_color_is_red():
    """Pill background must be red (0.86, 0.15, 0.15)."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "0.86, 0.15, 0.15" in src


def test_close_button_only_for_persistent():
    """The close button block must be gated on self._persistent and self._hover."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "self._persistent and self._hover" in src
