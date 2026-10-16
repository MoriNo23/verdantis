"""Metatest de sensibilidad para tests/test_contraste.py (spec `toast-contraste`).

El bug cubierto: un cambio de paleta rompe AA y el test de contraste no lo
detecta (porque midió una copia, o contra el fondo equivocado). Se inyecta un
color de reemplazo casi idéntico al fondo y el predicado de ratio que usa
test_contraste debe quedar en rojo; sin esto, el test sería un placebo.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import wayland_popup as wp

from test_contraste import _ratio, _BG, AA


def test_metatest_color_que_rompe_aa_detectado(monkeypatch):
    """Inyección: el app label pasa a ser casi el color del fondo.
    El predicado del test de zona clara debe quedar en rojo."""
    monkeypatch.setattr(wp, "_TXT_APP_L", "#33363f")
    fg = wp._hex_rgb(wp._TXT_APP_L)
    assert _ratio(fg, _BG) < AA, (
        "Metatest roto: con un app label casi del color del fondo el test "
        "de contraste queda en verde — no estaría midiendo la paleta real"
    )
