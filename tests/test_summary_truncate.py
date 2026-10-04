"""
RED/GREEN: el summary (titulo) del navegador puede venir con saltos de linea
(\\n) o tabs. Verdantis debe colapsarlos a 1 linea con ellipsis de Pango, no
desplegarlos como multiples lineas (lo que agrandaba la card y empujaba el
body). Confirmado contra mako/dunst: el titulo es 1 linea con ellipsis.

Test del widget NotificationWidget (headless, offscreen).
"""


from wayland_popup import NotificationWidget


def _widget(summary, body=""):
    s = summary or ""
    w = NotificationWidget(
        "Brave", "", s, body, None, None, "#80cbc4",
        on_click=lambda key=None: None, app_label="Brave - " + s,
        hide_title=False,
    )
    return w


def test_summary_newline_collapsed_to_single_line():
    # Navegador manda summary con \n (texto largo en multiples lineas)
    long_summary = "Mensaje muy largo del navegador\nque venia con salto de linea"
    w = _widget(long_summary)
    # El titulo interno NO debe contener \n: se colapsa a 1 linea
    assert "\n" not in w._titulo, "el titulo no debe tener saltos de linea"
    assert "\t" not in w._titulo


def test_summary_tab_collapsed():
    w = _widget("Titulo\tcon\ttabs")
    assert "\t" not in w._titulo


def test_summary_plain_unchanged():
    w = _widget("Hola mundo")
    assert w._titulo == "Hola mundo"


def test_summary_none_safe():
    w = _widget(None)
    assert w._titulo == ""
