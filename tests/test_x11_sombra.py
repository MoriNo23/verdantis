"""Paridad de diseño: el fallback X11 también necesita sitio para la sombra."""
import toast_core as tc


def test_geometry_x11_deja_sitio_a_la_sombra_y_mantiene_la_card_en_16px():
    sw, sh = 1366, 768
    h = 108
    W, H, x, y = tc.x11_geometry("top-right", h, 16, sw, sh)
    assert (W, H) == tc.surface_size(tc._CARD_WIDTH, h)
    assert x + tc._SHADOW_PAD["left"] == sw - tc._CARD_WIDTH - 16
    assert y + tc._SHADOW_PAD["top"] == 16


def test_esquina_inferior_x11():
    sw, sh = 1366, 768
    h = 108
    W, H, x, y = tc.x11_geometry("bottom-left", h, 16, sw, sh)
    assert (W, H) == tc.surface_size(tc._CARD_WIDTH, h)
    assert y + tc._SHADOW_PAD["top"] + h == sh - 16
    assert x + tc._SHADOW_PAD["left"] == 16
