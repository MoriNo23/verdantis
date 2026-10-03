"""
Metatest de sensibilidad para el contrato hover-dependiente de la franja
(tests/test_franja_hover.py + tests/test_action_zones.py).

El bug que estos tests cubren es doble y va por el MISMO camino de código:

  1. la franja/X se dibujaba sin puntero encima, y
  2. sus 44 px se reservaban de forma permanente (el persistente wrappeaba a
     la columna de hover aunque la franja no estuviera en pantalla).

Ambos cuelgan del gate `_strip_w()`, la única autoridad de "cuánto ancho
reclama la franja" (la consumen `_eff_text_width`, el posicionamiento de
`_draw` y el dibujado de la franja). Se inyecta la versión BUGUEADA —reserva
permanente, franja siempre visible— y se verifica que los predicados de 1.1
y 1.2 quedan en rojo; sin esto, esos tests serían placebos.
"""

import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import surface_pixels
from test_franja_hover import (
    LONG, SHORT, STRIP, W, _difieren, _is_x_rosa, _region, _render,
)

# Versión BUGUEADA del gate: la franja reserva sus 44 px y se dibuja siempre
# que el toast sea persistente, esté el puntero encima o no.
def _strip_w_bugueado(self):
    return NotificationWidget._CLOSE_STRIP_W if self._persistent else 0


def _widget_persistente(cuerpo=LONG):
    return NotificationWidget(
        "App", "", "T", cuerpo, None, None, "#80cbc4", persistent=True,
    )


def test_metatest_gate_hover_dependiente_existe():
    """Sanidad: el gate vive en `_strip_w` y es hover-dependiente. Si alguien
    lo borra o lo vuelve a colgar solo de `persistent`, la inyección de este
    metatest dejaría de simular el bug (y el metatest no probaría nada)."""
    w = _widget_persistente(SHORT)
    w._hover = False
    assert w._strip_w() == 0, (
        "sin hover la franja no reclama ancho: `_strip_w` debe ser 0"
    )
    w._hover = True
    assert w._strip_w() == STRIP
    w._persistent = False
    w._hover = True
    assert w._strip_w() == 0, (
        "un toast no persistente nunca reclama el ancho de la franja"
    )


def _pin_sin_iconos(monkeypatch):
    """Los anchos de columna son lo único verificado here: los del contrato son
    240/196 (columna única con franja en hover), sin depender de los iconos del
    tema instalados."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)


def test_metatest_bug_detecta_la_reserva_permanente(monkeypatch):
    """Con el bug inyectado, el predicado de 1.1
    (`test_eff_text_width_shrinks_for_persistent`: 240 sin hover) queda en
    rojo: el persistente mide 196 px aunque la franja no se dibuje."""
    _pin_sin_iconos(monkeypatch)
    monkeypatch.setattr(NotificationWidget, "_strip_w", _strip_w_bugueado)
    w = _widget_persistente()
    w._hover = False
    assert w._eff_text_width() == 196, (
        "con el bug inyectado el persistente sin hover debe medir la columna "
        "de hover (196 = 240 − 44). Si no se cumpliera, el test de 1.1 no "
        "detectaría la reserva permanente de 44 px (sería un placebo). Hoy mide "
        "%s porque la columna del contrato viejo (path sin slot) es 332."
        % (w._eff_text_width(),)
    )
    assert w._eff_text_width() != 240, (
        "el bug debe dejar el persistente sin hover en la columna de hover, "
        "no en la columna del card (240) que exige el contrato"
    )


def test_metatest_bug_hace_caer_el_test_de_re_wrap(monkeypatch):
    """Con el bug inyectado, el predicado de 1.1
    (`test_persistent_text_width_reserves_strip_only_on_hover`: la columna y
    la altura cambian con el hover) queda en rojo."""
    _pin_sin_iconos(monkeypatch)
    monkeypatch.setattr(NotificationWidget, "_strip_w", _strip_w_bugueado)
    w = _widget_persistente()
    w._expanded = True
    columnas, alturas = set(), set()
    for hover in (False, True):
        w._hover = hover
        columnas.add(w._eff_text_width())
        alturas.add(w.desired_height())
    assert len(columnas) == 1, (
        "Metatest roto: con el bug inyectado la columna de texto cambia con el "
        "hover — el test de 1.1 no distinguiría los dos estados (placebo)"
    )
    assert len(alturas) == 1, (
        "Metatest roto: con el bug inyectado la altura cambia con el hover; "
        "el test de 1.1 (`h_con_hover > h_sin_hover`) lo detectaría por otra razón"
    )


def test_metatest_la_version_real_distingue_los_dos_estados(monkeypatch):
    """Contraparte de los dos metatests anteriores (smoke): con el gate real,
    la columna y la altura SÍ dependen del hover — 240 → 196."""
    _pin_sin_iconos(monkeypatch)
    w = _widget_persistente()
    w._expanded = True
    w._hover = False
    assert w._eff_text_width() == 240
    h_sin = w.desired_height()
    w._hover = True
    assert w._eff_text_width() == 196
    h_con = w.desired_height()
    assert h_con > h_sin


def test_metatest_bug_detecta_la_franja_sin_hover(monkeypatch):
    """Con el bug inyectado, el predicado de 1.2
    (`test_sin_hover_el_persistente_no_dibuja_franja`: persistente sin hover
    idéntico píxel a píxel a un no persistente) queda en rojo, y aparecen
    píxeles de la X sin puntero encima."""
    monkeypatch.setattr(NotificationWidget, "_strip_w", _strip_w_bugueado)
    _, _, px_persist = _render(SHORT, True, False, monkeypatch)
    _, _, px_std = _render(SHORT, False, False, monkeypatch)

    franja_persist = _region(px_persist, W - STRIP, W)
    franja_std = _region(px_std, W - STRIP, W)
    assert franja_persist != franja_std, (
        "Metatest roto: con el bug inyectado el persistente sin hover sigue "
        "siendo idéntico a un toast sin franja — si se cumple, el test de 1.2 "
        "no detectaría la franja dibujada sin hover (sería un placebo)"
    )

    rosa = [(x, y) for y, row in enumerate(px_persist)
            for x, (r, g, b, a) in enumerate(row)
            if _is_x_rosa(r, g, b, a)]
    assert rosa, (
        "Metatest roto: el bug inyectado no dibuja la X sin hover; el test de "
        "1.2 `test_sin_hover_no_hay_pixeles_rosa_de_la_x` lo detectaría por otra "
        "razón"
    )


def test_metatest_la_franja_bugueada_invade_44px(monkeypatch):
    """La versión correcta limita la franja a sus 44 px: fuera de ellos el card
    con hover es idéntico al de un toast sin franja (para un body que no
    re-wrappea). Es la mitad "geométrica" del contrato de 1.2."""
    from render_helpers import alloc_and_draw
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)

    def _render_real(persistent):
        w = NotificationWidget(
            "App", "", "Titulo", SHORT, None, None, "#80cbc4",
            persistent=persistent, on_click=lambda: None,
        )
        w._hover = True
        h = w.desired_height()
        return surface_pixels(alloc_and_draw(w, W, h, hover=True))

    fuera = _difieren(_region(_render_real(True), 0, W - STRIP),
                      _region(_render_real(False), 0, W - STRIP))
    assert not fuera, (
        "con hover, fuera de los %d px de la franja el card debe ser idéntico "
        "al de un toast sin franja (difieren %d px)" % (STRIP, len(fuera))
    )
