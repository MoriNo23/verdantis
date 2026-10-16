"""
Metatest de sensibilidad para el contrato de razones de cierre
(tests/test_contrato_dbus.py, spec `contrato-dbus`).

El bug cubierto: el mapeo fuente→razón degenera (p. ej. a la razón fija 2 de
antes del fix, o a perder la razón 3 del bus). Se inyecta la tabla `_RAZONES`
bugueada del daemon y se verifica que el predicado del test correspondiente
queda en rojo; sin esto, test_contrato_dbus sería un placebo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import verdantis_daemon

from test_contrato_dbus import _manager_con_toast, _closes


def test_metatest_mapeo_fijo_2_detectado_en_timer(monkeypatch):
    """Inyección: TODAS las fuentes → razón 2 (el mapeo fijo de antes).
    El test de timer (espera razón 1) debe quedar en rojo."""
    monkeypatch.setattr(
        verdantis_daemon, "_RAZONES",
        {"timeout": 2, "user": 2, "action": 2, "dbus-close": 2},
    )
    m, nid = _manager_con_toast()
    m._active[0][1]._close()
    assert _closes(m._dbus_bus) != [(nid, 1)], (
        "Metatest roto: con el mapeo bugueado (todo → 2) el test del timer "
        "queda en verde — test_contrato_dbus no estaría detectando nada"
    )


def test_metatest_dbus_close_razon_2_detectado(monkeypatch):
    """Inyección: dbus-close pierde su razón 3 (cae en la genérica 2).
    El test de CloseNotification (espera razón 3) debe quedar en rojo."""
    monkeypatch.setattr(
        verdantis_daemon, "_RAZONES",
        {"timeout": 1, "user": 2, "action": 2, "dbus-close": 2},
    )
    m, nid = _manager_con_toast()
    m._close_id(nid)
    assert _closes(m._dbus_bus) != [(nid, 3)], (
        "Metatest roto: con dbus-close → 2 el test de CloseNotification "
        "queda en verde — la razón 3 no estaría cubierta"
    )
