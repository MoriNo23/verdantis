"""
RED: documenta el manejo de expire_timeout (spec freedesktop 1.2).

Contrato estándar (verificado en los 4 daemons de referencia clonados en
~/repos_fork):
  - plasma-workspace libnotificationmanager/server_p.cpp:331
        "// -1 = server default, 0 would be persistent"
  - mako criteria.c:482   expiring = (requested_timeout != 0)  -> 0 = NO expira
  - dunst: timeout == 0 -> "sticky", nunca expira
  - swaync: guarda expire_timeout crudo y no programa timer si es 0

Regla que verdantis DEBE cumplir:
  expire_timeout == 0  -> duration = 0  (persistente / requireInteraction)
  expire_timeout  > 0  -> duration = ese valor (ms)
  expire_timeout  < 0  -> duration = 6000 (default del server, ej -1)

El bug actual (verdantis_daemon.py:262):
  "duration": expire_timeout if expire_timeout > 0 else 6000
-> convierte 0 en 6000, rompiendo requireInteraction (Pinterest/Slack/WhatsApp
   Web desaparecen a los 6s pidiendo quedarse).
"""


from verdantis_daemon import NotificationManager
from wayland_popup import WaylandPopup


def _duration_for(expire_timeout):
    m = NotificationManager(corner="top-right")
    # Batching refactor (commit t_c93ad5ab): notify() ya NO construye el popup
    # de forma sincrónica; lo encola en _pending y el pump (vía scheduler) lo
    # drena llamando a _show_popup -> _active. Por eso acceder a _active[0]
    # justo después de notify() daba IndexError (lista vacía). Reproducimos el
    # camino real: usamos un scheduler no-op y disparamos el pump a mano.
    m._scheduler = lambda ms, cb: 0  # no auto-dispara; llamamos _pump() abajo
    m.set_dbus(_FakeBus())

    def headless_show(nid, kwargs):
        # Construye el WaylandPopup REAL con los kwargs del daemon, pero sin
        # abrir la ventana GTK (prepare()/set_stack_margin() necesitan display).
        # duration vive en el popup.
        popup = WaylandPopup(**kwargs)
        m._active.append((nid, popup))

    m._show_popup = headless_show
    m.notify(
        app_name="Brave", summary="Pinterest", body="idea",
        actions=["default", "Open"],
        hints={"desktop-entry": "brave-browser"},
        expire_timeout=expire_timeout,
    )
    m._pump()  # drena la cola -> _active poblado
    # duration vive en el WaylandPopup (kwargs que se construye en _show_popup)
    return m._active[0][1].duration


class _FakeBus:
    def emit_signal(self, *a):
        pass


def test_expire_zero_is_persistent():
    # requireInteraction del navegador -> nunca expirar
    assert _duration_for(0) == 0


def test_expire_positive_keeps_value():
    assert _duration_for(5000) == 5000


def test_expire_negative_uses_default():
    # -1 = server default (6000ms)
    assert _duration_for(-1) == 6000


def test_expire_other_negative_uses_default():
    assert _duration_for(-100) == 6000
