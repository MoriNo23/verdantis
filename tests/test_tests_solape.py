"""Metatest de sensibilidad para "un toast que entra no tapa al que ya estaba"
(tests/test_stack_reflow.py::test_el_que_entra_ya_llega_en_su_hueco).

El bug es de ORDEN en `_show_popup`: mapear la superficie —que commitea el primer
frame, ya visible— ANTES de reservar el hueco. Se inyecta esa versión vieja y se
verifica que el predicado del test real queda en rojo; sin esto, ese test sería
un placebo.
"""

import verdantis_daemon as vd
import wayland_popup as wp

from test_stack_reflow import _margenes_al_mapear, pila  # noqa: F401 (fixture)


def _show_popup_bugueado(self, nid, kwargs):
    """Versión vieja del orden: `prepare()` (mapea con el offset 0) y recién
    después el append + el reflow."""
    popup = wp.WaylandPopup(**kwargs)
    idx = len(self._active)
    if popup.duration > 0 and idx > 0:
        popup.duration += idx * self.CLOSE_STAGGER_MS
    popup.on_resized = self._reflow_stack
    popup.prepare()
    self._active.append((nid, popup))
    self._reflow_stack()


def test_metatest_el_orden_viejo_mapea_con_offset_cero(pila, monkeypatch):
    """Con el orden viejo inyectado, el que entra mapea con offset 0 (encima
    del de arriba): el test real lo detectaría."""
    monkeypatch.setattr(vd.NotificationManager, "_show_popup",
                        _show_popup_bugueado)
    visto, _arriba = _margenes_al_mapear(pila, monkeypatch)

    assert visto == [0], (
        "Metatest roto: con el orden viejo el offset al mapear tendría que ser 0 "
        "(la superficie se mapea antes de reservar el hueco); fue %s — el test "
        "real no estaría detectando el solape" % (visto,)
    )


def test_metatest_la_version_real_reserva_el_hueco(pila, monkeypatch):
    """Contraparte: con el `_show_popup` real el offset al mapear ya es el hueco
    (distinto de 0), así que el metatest no prueba un placeholder."""
    visto, _arriba = _margenes_al_mapear(pila, monkeypatch)

    assert visto != [0], (
        "con el fix, el offset al mapear tiene que ser el hueco reservado "
        "(alto de arriba + gap), no 0; fue %s" % (visto,)
    )
