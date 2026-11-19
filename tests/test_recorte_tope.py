"""Re-auditoría: el recorte de padding no puede bloquear el daemon."""
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import toast_core as tc


def test_imagen_enorme_no_se_recorre_pixel_a_pixel():
    grande = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 2000, 2000)
    grande.fill(0x00000000)
    # Por encima del tope se devuelve la misma imagen: cover sigue funcionando
    # y no se recorren 4 millones de píxeles en Python.
    assert tc._recortar_transparente(grande) is grande
    out = tc._cover_pixbuf(grande, 260, 140)
    assert (out.get_width(), out.get_height()) == (260, 140)
