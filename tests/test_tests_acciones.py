"""
Metatest de sensibilidad para el contrato de botones de acción
(tests/test_acciones.py, spec `toast-acciones`).

El bug cubierto: el click en un botón cae en la DEFAULT (None) en vez de la
key de ese botón — exactamente el comportamiento que había antes del change
(las actions solo alimentaban `_pick_action_key`). Se inyecta la versión
bugueada de `_on_button_press` y se verifica que el predicado de
`test_click_en_boton_emite_su_key` queda en rojo; sin esto, ese test sería
un placebo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import alloc_and_draw

from test_acciones import ACTIONS_2, _Ev, _sin_iconos_resolvibles, _widget

W = wp._CARD_WIDTH


def _press_bugueado(self, widget, event):
    """Versión BUGUEADA: el click dentro de un botón emite None (la default),
    ignorando la key del rect — como si la fila no existiera."""
    for rect in self._action_rects:
        x0, y0, x1, y1, key = rect
        if x0 <= event.x <= x1 and y0 <= event.y <= y1:
            if self._on_click:
                self._on_click(None)   # BUG: la default en vez de `key`
            return True
    if self._on_click:
        self._on_click(None)
    return True


def test_metatest_bug_click_boton_a_default(monkeypatch):
    """Con el bug inyectado, el predicado de 1.2 (click en botón → SU key)
    queda en rojo: los rects existen pero el click cae en None."""
    _sin_iconos_resolvibles(monkeypatch)
    monkeypatch.setattr(NotificationWidget, "_on_button_press", _press_bugueado)

    llamados = []
    w = _widget(actions=ACTIONS_2, on_click=lambda key=None: llamados.append(key))
    alloc_and_draw(w, W, w.desired_height())
    assert len(w._action_rects) == 2, (
        "sanidad: la fila debe existir para poder inyectar el bug del click"
    )

    for rect in w._action_rects:
        x0, y0, x1, y1, key = rect
        w._on_button_press(w, _Ev((x0 + x1) / 2, (y0 + y1) / 2))

    esperadas = [r[4] for r in w._action_rects]
    assert llamados != esperadas, (
        "Metatest roto: con el bug inyectado (click de botón → None) el "
        "callback recibió las keys correctas (%s) — si se cumpliera, el test "
        "de 1.2 `test_click_en_boton_emite_su_key` no detectaría el bug "
        "(sería un placebo)" % (llamados,)
    )
    assert llamados == [None, None], (
        "el bug inyectado debe mandar la default (None) por click, no %s"
        % (llamados,)
    )


def test_metatest_version_real_distingue_el_bug(monkeypatch):
    """Contraparte (smoke): con el _on_button_press REAL, el click en cada
    botón emite SU key — el predicado distingue los dos estados."""
    _sin_iconos_resolvibles(monkeypatch)
    llamados = []
    w = _widget(actions=ACTIONS_2, on_click=lambda key=None: llamados.append(key))
    alloc_and_draw(w, W, w.desired_height())
    for rect in w._action_rects:
        x0, y0, x1, y1, key = rect
        w._on_button_press(w, _Ev((x0 + x1) / 2, (y0 + y1) / 2))
    assert llamados == [r[4] for r in w._action_rects], (
        "la versión real debe emitir la key de cada botón, no %s" % (llamados,)
    )
