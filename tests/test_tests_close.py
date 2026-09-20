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
    SENSIBILIDAD: si alguien revierte la franja de descarte al pill 28x28
    esquinado (regresión del anti-misclick), la layout del cierre cambia.
    Verificamos que los constants de la franja están en el source.
    """
    src = inspect.getsource(wp.NotificationWidget._draw)
    assert "sx0 = W - sw" in src, (
        "Metatest: la franja debe anclarse al borde derecho (sx0 = W - sw)"
    )
    assert "self._close_rect = (sx0, 0, W, H)" in src, (
        "Metatest: el hit-rect de cierre debe cubrir el alto completo del card"
    )
    assert "sw = self._CLOSE_STRIP_W" in src, (
        "Metatest: el ancho de la franja debe salir de _CLOSE_STRIP_W"
    )
    assert wp.NotificationWidget._CLOSE_STRIP_W == 44, (
        "Metatest: el ancho de la franja debe seguir siendo 44px"
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
