"""Badge de pendientes: la cola deja de ser invisible bajo los 2 toasts.

La pila muestra 2 cards y el resto espera en `_pending` sin ninguna señal
visual (spec `toast-stack`). Este badge es una franja chica debajo de la pila
que dice cuántas notificaciones esperan; desaparece cuando la cola se vacía.
No reordena ni cambia el FIFO (spec `toast-orden-llegada`).
"""
import os
from unittest.mock import Mock

import pytest

import verdantis_daemon as vd
from test_contrato_dbus import _manager_headless


def _notify(m, i):
    return m.notify(app_name="t", app_icon="", summary="s%d" % i, body="b",
                    actions=[], hints={"transient": True}, expire_timeout=5000)


def test_texto_del_badge():
    assert vd._badge_text(0) == ""
    assert vd._badge_text(1) == "+1 notificación en espera"
    assert vd._badge_text(4) == "+4 notificaciones en espera"


def test_sync_badge_usa_el_tamano_de_la_cola():
    m = _manager_headless()
    m._badge = Mock()
    for i in range(5):
        _notify(m, i)
    m._pump()
    m._pump()
    assert len(m._active) == 2 and len(m._pending) == 3
    m._sync_badge()
    assert m._badge.update.call_args.args[0] == 3


def test_sync_badge_oculta_cuando_la_cola_esta_vacia():
    m = _manager_headless()
    m._badge = Mock()
    m._sync_badge()
    assert m._badge.update.call_args.args[0] == 0


def test_notify_actualiza_el_badge_solo():
    m = _manager_headless()
    m._badge = Mock()
    _notify(m, 0)
    assert m._badge.update.call_args.args[0] == 1


@pytest.mark.skipif(not os.environ.get("WAYLAND_DISPLAY"),
                    reason="el badge real necesita layer-shell")
def test_el_badge_real_se_construye_y_se_actualiza():
    """Atrapa errores de API de layer-shell (Edge.TOP, no Edge.Top)."""
    b = vd._PendingBadge("top-right")
    b.update(3, 360)
    assert b.label.get_label() == "+3 notificaciones en espera"
    b.update(0, 360)
    assert not b.window.get_visible()
