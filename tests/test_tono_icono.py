"""El color del nombre de app se toma del icono, con piso de contraste AA."""
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import toast_core as tc


def test_tono_del_icono_y_contraste():
    icono = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    icono.fill(0x0080ffff)          # azul saturado, poco luminoso
    tono = tc._icon_tint(icono)
    assert tono[2] > tono[0]        # sigue siendo azul
    assert tc._luminancia(tono) >= 0.25   # legible sobre la card oscura


def test_sin_icono_devuelve_el_color_base():
    assert tc._icon_tint(None) == tc._hex_rgb(tc._TXT_APP_L)


def test_icono_transparente_devuelve_el_color_base():
    vacio = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    vacio.fill(0x00000000)
    assert tc._icon_tint(vacio) == tc._hex_rgb(tc._TXT_APP_L)
