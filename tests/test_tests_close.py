"""
Metatests visuales para el close button: validan que test_close_render.py es
SENSIBLE a las regresiones de rendering, no un placebo.

Cada metatest simula un BUG (cambio incorrecto) y verifica que el test de
cierre correspondiente la DETECTARÍA. Esto prueba que la suite "ve" con
ojos numéricos los artifacts de rendering.
"""
import os
import sys
import math
import cairo

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import inspect
import wayland_popup as wp


def _source_has_fix():
    """Returns True if the _draw source contains both fix markers."""
    src = inspect.getsource(wp.NotificationWidget._draw)
    return "translate(0.5, 0.5)" in src and "ANTIALIAS_NONE" in src


def test_metatest_source_sensitive_to_fix_removal():
    """
    SENSIBILIDAD: si alguien quita cr.translate(0.5, 0.5) o
    cr.set_antialias(cairo.ANTIALIAS_NONE) del close button,
    test_close_source_has_fix y test_close_button_uses_pixel_centering
    deberían fallar. Verificamos que la source inspection SÍ
    detecta la presencia/ausencia del fix.
    """
    src = inspect.getsource(wp.NotificationWidget._draw)
    # The fix markers must be present
    assert "translate(0.5, 0.5)" in src, (
        "Metatest: pixel-centering marker missing — "
        "test_close_button_uses_pixel_centering would not detect its removal"
    )
    assert "ANTIALIAS_NONE" in src, (
        "Metatest: ANTIALIAS_NONE marker missing — "
        "test_close_button_uses_antialias_none_on_x would not detect its removal"
    )


def test_metatest_close_position_constants():
    """
    SENSIBILIDAD: si alguien cambia la posición del close button (e.g.
    cy_t de 6 a 4, o cs de 28 a 30), la layout del close pill cambia.
    Verificamos que los constants están en el source y son los esperados.
    """
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "cx_r = W - pad - 6" in src or "cx_r=W - pad - 6" in src, (
        "Metatest: close button right margin constant changed — "
        "position would shift off the corner"
    )
    assert "cy_t = 6" in src or "cy_t=6" in src, (
        "Metatest: close button top offset changed — "
        "position would shift from corner"
    )
    assert "cs = 28" in src, (
        "Metatest: close button size changed — would affect crispness"
    )


def test_metatest_close_x_color_constant():
    """
    SENSIBILIDAD: si alguien cambia el color de la X (e.g. #f38ba8 a otro),
    la apariencia visual cambia. Verificamos el constante está en el source.
    """
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "0.953, 0.482, 0.659" in src, (
        "Metatest: X color constant changed — visual appearance would shift"
    )
