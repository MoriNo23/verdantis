"""
Spec del WRAP del body: el texto llena el margen de la columna sin partir
palabras.

El wrap siempre fue por palabra (`Pango.WrapMode.WORD_CHAR`) — lo que hacen
mako / dunst / Plasma — y por eso un renglón que no llega a la palabra siguiente
deja el hueco del corte al final: con el body real de xat el renglón 1 quedaba
en 207 px de tinta de los 240 de la columna. Decisión del usuario (change
`ellipsis-body-lineas-exactas`, D5): justificar los renglones parciales con
`Pango.Layout.set_justify`, que estira SOLO los espacios inter-palabra — llega
al margen sin cortar ninguna palabra.

El contrato queda en tres asserts:

1. lo dibujado llega al margen de la columna en TODOS los renglones (píxeles);
2. el hueco existía de verdad (referencia sin justificar), así que el assert 1
   no pasa por casualidad;
3. las DOS funciones gemelas justifican y NINGUNA cambia el modo de wrap: el
   dibujado y la medición siguen envueltos por palabra — con `CHAR` se llenaría
   el margen partiendo palabras a la mitad.
"""

import inspect

import cairo
import pytest

import wayland_popup as wp
from render_helpers import alloc_and_draw, surface_pixels
from wayland_popup import NotificationWidget

from test_body_colapso import (
    BODY_RGB, OVERFLOW, _body_bands, _body_fs,
)

W = wp._TEXT_COL_W          # 240: la columna única de texto
ROW_GAP = 2
TOL = 12                    # el mismo margen de color que test_body_colapso
# El hueco final de un renglón justificado NO es cero: es el espacio del corte,
# estirado como los demás. Por eso el contrato se mide contra la propia línea
# (el hueco no puede ser más ancho que un espacio de palabra de ese renglón) en
# vez de contra el margen exacto — un ±2 px de antialiasing no es un contrato.
HOLGURA = 2


def _bandas_de_referencia(cuerpo, font_scale, justify, cap=3, ancho=W):
    """Bandas `(top, left, right)` de un layout del body SOLO, sin card.

    Reproduce el layout que dibuja el body (misma fuente, ancho, wrap, cap y
    ellipsis) con o sin justificar: es la referencia para comparar el "antes"
    del hueco. El fondo queda transparente, así que "hay tinta" es alfa > 0.
    """
    from gi.repository import Pango, PangoCairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, 260)
    cr = cairo.Context(surf)
    cr.set_source_rgb(1, 1, 1)
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(
        Pango.FontDescription("Manrope " + str(_body_fs(font_scale))))
    layout.set_text(cuerpo, -1)
    layout.set_width(int(ancho * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    if justify:
        layout.set_justify(True)
    line_h = layout.get_line_readonly(0).get_pixel_extents()[1].height
    layout.set_height(int(cap * line_h) * Pango.SCALE)
    layout.set_ellipsize(Pango.EllipsizeMode.END)
    cr.move_to(0, 0)
    PangoCairo.show_layout(cr, layout)
    surf.flush()
    data = surf.get_data()
    bands = []
    for y in range(260):
        fila = y * surf.get_stride()
        xs = [x for x in range(ancho) if data[fila + x * 4 + 3] > 0]
        if not xs:
            continue
        if bands and y - bands[-1][1] <= ROW_GAP:
            bands[-1][1] = y
            bands[-1][3] = max(bands[-1][3], xs[-1])
        else:
            bands.append([y, y, xs[0], xs[-1]])
    return [(b[0], b[2], b[3]) for b in bands]


def _pixeles_del_body(cuerpo, font_scale=1.0, app="App"):
    """Píxeles del render headless + la geometría de la columna del body.

    Es la región que usa `_body_bands` (mismo origen), expuesta aparte para
    poder medir los huecos horizontales de un renglón sin volver a duplicar el
    criterio de "qué es el body".
    """
    w = NotificationWidget(app, "", "Titulo", cuerpo, None, None, "#80cbc4")
    w._font_scale = font_scale
    h = w.desired_height()
    px = surface_pixels(alloc_and_draw(w, wp._CARD_WIDTH, h))
    x0 = wp._PAD + wp._IMAGE_LEFT_W + wp._IMAGE_LEFT_GAP
    return px, (x0, wp._PAD + wp._rows_above_body(app, False),
               wp._CARD_WIDTH - x0 - wp._PAD - w._strip_w())


def _huecos(px, banda, x0, margen):
    """(hueco hasta el margen, hueco más ancho dentro del renglón).

    Se proyecta la banda sobre el eje x para quedarse con las corridas de
    tinta: el hueco del final es de la última corrida al margen, y el hueco
    interno es el más ancho entre corridas (un espacio de palabra).
    """
    tinta = set()
    for y in range(banda[0], banda[1] + 1):
        for x in range(x0, margen):
            if all(abs(px[y][x][i] - BODY_RGB[i] * 255) <= TOL for i in range(3)):
                tinta.add(x)
    corridas, inicio = [], None
    for x in range(x0, margen):
        if x in tinta and inicio is None:
            inicio = x
        elif x not in tinta and inicio is not None:
            corridas.append((inicio, x - 1))
            inicio = None
    if inicio is not None:
        corridas.append((inicio, margen - 1))
    internos = [b[0] - a[1] - 1 for a, b in zip(corridas, corridas[1:])]
    assert corridas, "la banda %s no tiene tinta en la columna" % (banda,)
    return margen - corridas[-1][1], max(internos or [0])


@pytest.mark.parametrize("font_scale", [0.85, 1.0])
def test_el_renglon_se_justifica_hasta_el_margen(font_scale):
    """Los renglones del body se llenan hasta el margen de la columna.

    Sin justificar, el renglón que corta antes de la palabra siguiente queda
    con un hueco visible al final (el espacio del corte). Justificado, los
    espacios se estiran y ese hueco queda al tamaño de un espacio de palabra más
    o menos — no más. El criterio es "no más ancho que el espacio más ancho del
    mismo renglón" porque el último espacio (el del corte) no se estira igual:
    medirse contra el margen exacto sería exigir 0 px y fallar por el
    antialiasing.
    """
    px, (x0, top, col_w) = _pixeles_del_body(OVERFLOW, font_scale)
    _w, _h, bands, _ = _body_bands(OVERFLOW, font_scale=font_scale)
    assert bands, "el body del test debe dibujar algo"
    margen = x0 + col_w
    for b in bands:
        hueco, gap_max = _huecos(px, b, x0, margen)
        assert hueco <= gap_max + HOLGURA, (
            "el renglón de la fila %d deja %d px de hueco hasta el margen (%d), "
            "más que el espacio más ancho de esa misma línea (%d px): no está "
            "justificado (¿falta set_justify?)" % (b[0], hueco, margen, gap_max)
        )


def test_el_hueco_existia_de_verdad():
    """Premisa del arreglo: sin justificar, un renglón queda con hueco de verdad.

    Sin este assert, `test_el_renglon_se_justifica_hasta_el_margen` pasaría
    igual en un mundo donde el renglón ya llegara al margen por otra razón.
    """
    for font_scale in (0.85, 1.0):
        sin = _bandas_de_referencia(OVERFLOW, font_scale, justify=False)
        huecos = [W - r[2] for r in sin]
        assert max(huecos) >= 20, (
            "font_scale %s: la referencia sin justificar debe tener un renglón "
            "con hueco de verdad (>= 20 px); si no, el assert del margen no "
            "prueba nada. Huecos: %s" % (font_scale, huecos)
        )


def test_las_dos_gemelas_justifican_y_el_wrap_sigue_siendo_por_palabra():
    """Medición y dibujado envuelven IGUAL: los dos justifican, ninguno parte
    palabras.

    `set_justify` solo estira los espacios inter-palabra: los cortes de línea no
    se mueven. Si alguien cambiara el wrap a `CHAR` (que llena el margen
    partiendo palabras a la mitad), el margen llenado tendría el precio de cortar
    "amistoso" en "amistos/o" — este assert lo prohíbe explícitamente.
    """
    for fn in (wp._body_metrics, NotificationWidget._draw_text):
        src = inspect.getsource(fn)
        assert "set_wrap(Pango.WrapMode.WORD_CHAR)" in src, (
            "%s debe envolver por palabra (WORD_CHAR): cambiar a CHAR llenaría "
            "el margen partiendo palabras" % fn.__name__
        )
        assert "layout.set_justify(True)" in src, (
            "%s debe justificar los renglones parciales: sin él queda el hueco "
            "del corte al final del renglón" % fn.__name__
        )
