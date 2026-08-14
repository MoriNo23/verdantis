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
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from verdantis_daemon import NotificationManager


def _duration_for(expire_timeout):
    m = NotificationManager(corner="top-right")
    m.set_dbus(_FakeBus())
    nid = m.notify(
        app_name="Brave", summary="Pinterest", body="idea",
        actions=["default", "Open"],
        hints={"desktop-entry": "brave-browser"},
        expire_timeout=expire_timeout,
    )
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
