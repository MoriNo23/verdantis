"""El slot izquierdo debe ser un círculo sólido y centrado.

El placeholder era un cuadrado redondeado con esquinas transparentes: al
recortarlo en círculo quedaban huecos dentro del borde. Se rellena el fondo
circular antes de pintar la imagen centrada con cover.
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf

import toast_core as tc


def _pixel(pixbuf, x, y):
    px = pixbuf.get_pixels()
    canales = pixbuf.get_n_channels()
    fila = pixbuf.get_rowstride()
    i = y * fila + x * canales
    return tuple(px[i:i + canales])


def test_circulo_solido_y_centradо():
    """Una imagen con esquinas transparentes no deja huecos en el círculo."""
    base = tc._make_placeholder_icon("V", 80)
    salida = tc._make_circular(base, 80)
    assert salida.get_width() == 80 and salida.get_height() == 80
    # Punto dentro del círculo cerca del borde: antes era transparente.
    assert _pixel(salida, 3, 40)[3] == 255
    assert _pixel(salida, 40, 3)[3] == 255
    # Centro opaco.
    assert _pixel(salida, 40, 40)[3] == 255


def test_sujeto_con_padding_transparente_se_centra_y_crece():
    """Un icono con mucho espacio vacío alrededor debe llenar el círculo."""
    lienzo = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 100, 100)
    lienzo.fill(0x00000000)
    sujeto = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 20, 20)
    sujeto.fill(0x80cbc4ff)
    sujeto.copy_area(0, 0, 20, 20, lienzo, 70, 70)
    salida = tc._make_circular(lienzo, 80)
    # Con cover sobre el lienzo completo el sujeto queda chico y descentrado;
    # recortando el padding transparente ocupa el círculo y pasa por el centro.
    assert _pixel(salida, 12, 40)[:3] == (0x80, 0xcb, 0xc4)


def test_imagen_no_cuadrada_se_centra_y_llena():
    ancho, alto = 200, 60
    cruda = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, ancho, alto)
    cruda.fill(0x80cbc4ff)
    salida = tc._make_circular(cruda, 80)
    assert salida.get_width() == 80 and salida.get_height() == 80
    for x, y in ((40, 40), (3, 40), (76, 40), (40, 3), (40, 76)):
        assert _pixel(salida, x, y)[3] == 255
