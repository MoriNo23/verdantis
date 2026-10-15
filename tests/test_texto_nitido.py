"""El texto del card se rasteriza con antialiasing en grises (spec
`toast-texto-nitido` del change toast-pila-dos-y-texto-nitido).

Pango reparte la cobertura del antialiasing por canal de color cuando usa
subpixel (el default de fontconfig en muchos equipos: `rgba: rgb`). Sobre el
fondo TRANSLÚCIDO del card esa cobertura por canal se ve como franjas de color
en los bordes de las letras — la discolouration conocida de pangocairo en
superficies con alpha. El daemon fija el antialiasing en el PangoContext de cada
layout, así que el render no depende de la configuración del sistema.

EL TEST NO MIRA PÍXELES: el defecto no se reproduce en un equipo con fontconfig
`rgba: none` (ahí cairo ya rasteriza en grises), así que un test de píxeles sería
verde con el bug puesto. Lo determinista y observable es la OPCIÓN con la que
quedó cada layout: `ANTIALIAS_GRAY` explícito en vez del `DEFAULT` que resuelve
fontconfig.
"""

import cairo

import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import alloc_and_draw

W = 360
TITULO = "Título del toast"
CUERPO = "Cuerpo del toast."
ACCIONES = ["settings", "Ajustes", "mail-mark-read", "Marcar"]


def _sin_iconos(monkeypatch):
    """Determinismo: los iconos del tema/.desktop no cambian el layout."""
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop",
        lambda app_name, size=80, mode="cover": None)
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)


def _widget_completo(monkeypatch):
    """Toast con los cuatro bloques de texto: label de app, título, body y
    labels de los botones de acción."""
    _sin_iconos(monkeypatch)
    return NotificationWidget(
        "App", "", TITULO, CUERPO, None, None, "#80cbc4",
        on_click=lambda key=None: None, actions=ACCIONES,
    )


def _layouts_del_card(widget, monkeypatch):
    """Layouts de Pango que crea `_draw`, en orden.

    Espía `PangoCairo.create_layout` — el único punto donde el card pide un
    layout — y renderiza headless. Los layouts del placeholder se crean en
    `__init__`, antes del espía, así que no entran: acá se verifica el texto
    dibujado sobre la superficie translúcida del card.
    """
    creados = []
    real = wp.PangoCairo.create_layout

    def spy(cr):
        lay = real(cr)
        creados.append(lay)
        return lay

    monkeypatch.setattr(wp.PangoCairo, "create_layout", spy)
    alloc_and_draw(widget, W, widget.desired_height())
    return creados


def _antialias(lay):
    """Antialiasing con el que quedó el PangoContext del layout."""
    return wp.PangoCairo.context_get_font_options(
        lay.get_context()).get_antialias()


def test_todos_los_layouts_del_card_quedan_en_grises(monkeypatch):
    """Scenario "Texto sobre card translúcido sin franjas de color" y "Ningún
    texto del card queda sin el antialiasing explícito" (spec
    `toast-texto-nitido`): ningún bloque de texto queda con el antialiasing del
    sistema (el `DEFAULT` que resuelve fontconfig, que puede ser subpixel).

    Rojo hoy: `_draw` crea los layouts con `PangoCairo.create_layout(cr)` a
    secas, así que heredan las opciones del contexto de Cairo (DEFAULT)."""
    creados = _layouts_del_card(_widget_completo(monkeypatch), monkeypatch)

    textos = [lay.get_text() for lay in creados]
    for esperado in (TITULO, CUERPO, "Ajustes", "Marcar"):
        assert esperado in textos, (
            "el render tiene que pasar por todos los bloques de texto del card "
            "(falta %r); creó %s" % (esperado, textos)
        )

    malos = [(lay.get_text(), _antialias(lay)) for lay in creados
             if _antialias(lay) != cairo.ANTIALIAS_GRAY]
    assert not malos, (
        "spec toast-texto-nitido: TODO el texto del card se rasteriza con "
        "ANTIALIAS_GRAY fijado por el daemon — el subpixel reparte la cobertura "
        "por canal y el fondo translúcido lo muestra como franjas de color. "
        "Quedaron sin fijar (texto, antialias): %s" % (malos,)
    )
