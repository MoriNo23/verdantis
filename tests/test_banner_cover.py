"""El banner grande se centra y cubre el rectángulo sin deformarse."""
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import toast_core as tc


def _pixel(pixbuf, x, y):
    px = pixbuf.get_pixels()
    ch, fila = pixbuf.get_n_channels(), pixbuf.get_rowstride()
    i = y * fila + x * ch
    return tuple(px[i:i + ch])


def test_cover_respeta_el_tamano_y_no_estira():
    src = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 300, 100)
    src.fill(0x80cbc4ff)
    out = tc._cover_pixbuf(src, 260, 140)
    assert (out.get_width(), out.get_height()) == (260, 140)
    assert _pixel(out, 130, 70)[:3] == (0x80, 0xcb, 0xc4)


def test_cover_recorta_padding_transparente_y_centra():
    lienzo = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 400, 200)
    lienzo.fill(0x00000000)
    sujeto = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 20, 20)
    sujeto.fill(0x80cbc4ff)
    sujeto.copy_area(0, 0, 20, 20, lienzo, 350, 160)
    out = tc._cover_pixbuf(lienzo, 260, 140)
    assert _pixel(out, 130, 70)[:3] == (0x80, 0xcb, 0xc4)
