"""Metatest de sensibilidad para el antialiasing del texto
(tests/test_texto_nitido.py).

Se inyecta la versión BUGUEADA de la creación del layout —`PangoCairo.
create_layout(cr)` a secas, sin fijar las opciones— y se verifica que el
predicado del test real queda en rojo; sin esto, ese test sería un placebo.
"""

import cairo

import wayland_popup as wp

from test_texto_nitido import _antialias, _layouts_del_card, _widget_completo


def test_metatest_sin_fix_los_layouts_heredan_el_antialias_del_sistema(monkeypatch):
    """Con el bug inyectado NINGÚN layout queda en grises, así que el test real
    (`test_todos_los_layouts_del_card_quedan_en_grises`) lo detectaría."""
    monkeypatch.setattr(
        wp, "_create_layout", lambda cr: wp.PangoCairo.create_layout(cr))
    creados = _layouts_del_card(_widget_completo(monkeypatch), monkeypatch)

    assert creados, "el render tiene que crear layouts de Pango"
    heredados = [lay for lay in creados
                 if _antialias(lay) == cairo.ANTIALIAS_GRAY]
    assert not heredados, (
        "con la creación de layout sin opciones los layouts heredan el "
        "antialiasing del contexto (DEFAULT/subpixel): si alguno quedara en "
        "grises, el test real no detectaría el bug (sería un placebo)"
    )


def test_metatest_la_version_real_deja_todo_en_grises(monkeypatch):
    """Contraparte: con el helper real todos los layouts quedan en grises, así
    que el metatest no está probando un placeholder."""
    creados = _layouts_del_card(_widget_completo(monkeypatch), monkeypatch)
    assert creados, "el render tiene que crear layouts de Pango"
    assert all(_antialias(lay) == cairo.ANTIALIAS_GRAY for lay in creados), (
        "con el fix, cada layout del card tiene que quedar en ANTIALIAS_GRAY"
    )
