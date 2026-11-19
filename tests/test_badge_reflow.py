"""El badge sigue el alto real de la pila cuando una card cambia de tamaño.

`on_resized` sólo re-floweaba las cards: si un toast crecía (expandir "Ver más",
re-wrap por hover), el badge quedaba en la posición vieja y podía solaparse con
la última card. Spec `toast-badge-pendientes`.
"""
from unittest.mock import Mock

from test_contrato_dbus import _manager_headless
from toast_window import ToastWindow


def test_reflow_reposiciona_el_badge_con_el_alto_nuevo():
    m = _manager_headless()
    m._badge = Mock()
    nid = m.notify(app_name="t", app_icon="", summary="s", body="b",
                   actions=[], hints={"transient": True}, expire_timeout=5000)
    m._pump()
    antes = m._badge.update.call_args.args[1]

    # La card crece 60px: el reflow debe mover el badge el mismo delta.
    popup = m._active[0][1]
    alto_original = popup.stack_height()
    popup.stack_height = lambda: alto_original + 60
    m._reflow_stack()

    assert m._badge.update.call_args.args[1] == antes + 60
