"""Tests para el fix de click en navegador: PWA instalada -> solo ActionInvoked
(nada de xdg-open que abriria una ventana-PWA duplicada); navegador generico o
vacio -> ActionInvoked + xdg-open (abre/focusea la pestaña).

Rojo primero: estas pruebas fallan contra el codigo actual (que hace xdg-open
siempre que hay URL).
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, "/home/fullmetal/repos/verdantis/src")

from unittest import mock

import verdantis_daemon as vd
from verdantis_daemon import NotificationManager


APP_DIR = os.path.expanduser("~/.local/share/applications")
PWA_DESKTOP = "brave-hnpfjngllnobngcgfapefoaidbinmjnm-Default.desktop"
BROWSER_DESKTOP = "brave-browser-nightly.desktop"


def _manager_with(nid, actions, url, desktop_entry):
    mgr = NotificationManager()
    mgr._notifications[nid] = {
        "actions": actions,
        "url": url,
        "desktop_entry": desktop_entry,
    }
    return mgr


def test_is_pwa_true_whatsapp():
    de = os.path.join(APP_DIR, PWA_DESKTOP)
    # Solo corre si la PWA sigue instalada; si no, salta (no falla el suite).
    if not os.path.exists(de):
        import pytest
        pytest.skip("PWA de WhatsApp no instalada en este equipo")
    assert vd._is_pwa(PWA_DESKTOP) is True


def test_is_pwa_false_browser():
    assert vd._is_pwa(BROWSER_DESKTOP) is False


def test_is_pwa_false_empty():
    assert vd._is_pwa("") is False
    assert vd._is_pwa(None) is False


def test_on_action_invoked_pwa_no_xdgopen():
    """PWA instalada: emite ActionInvoked y NO llama xdg-open."""
    mgr = _manager_with(1, ["default", "Abrir"], "https://web.whatsapp.com/", PWA_DESKTOP)
    bus = mock.MagicMock()
    mgr.set_dbus(bus)
    with mock.patch.object(vd.subprocess, "Popen") as popen:
        mgr._on_action_invoked(1)
    bus.emit_signal.assert_called_once()
    # La key real ("default") debe ir en ActionInvoked
    args = bus.emit_signal.call_args
    assert args.args[3] == "ActionInvoked"
    assert "default" in str(args.args[4])
    popen.assert_not_called()  # NO xdg-open -> no ventana PWA duplicada


def test_on_action_invoked_generic_xdgopen():
    """Navegador generico + URL: emite ActionInvoked Y hace xdg-open."""
    mgr = _manager_with(2, ["default", "Abrir"], "https://github.com/MoriNo23/verdantis", BROWSER_DESKTOP)
    bus = mock.MagicMock()
    mgr.set_dbus(bus)
    with mock.patch.object(vd.subprocess, "Popen") as popen:
        mgr._on_action_invoked(2)
    bus.emit_signal.assert_called_once()
    popen.assert_called_once()
    assert popen.call_args.args[0][0] == "xdg-open"


# ---- Paso 1 (plan fix-pwa-click-focus): emitir ActionInvoked DIRIGIDO al sender ----

def _manager_with_sender(nid, actions, url, desktop_entry, sender):
    mgr = NotificationManager()
    mgr._notifications[nid] = {
        "actions": actions,
        "url": url,
        "desktop_entry": desktop_entry,
        "sender": sender,
    }
    return mgr


def test_on_action_invoked_emits_to_sender():
    """ActionInvoked debe ir DIRIGIDO al sender (no broadcast None), para que
    Chromium re-enfoque la PWA al recibirlo. Hoy emite con dest=None -> falla."""
    mgr = _manager_with_sender(7, ["default", "Abrir"], "", PWA_DESKTOP, ":1.42")
    bus = mock.MagicMock()
    mgr.set_dbus(bus)
    with mock.patch.object(vd.subprocess, "Popen"):
        mgr._on_action_invoked(7)
    bus.emit_signal.assert_called_once()
    # 1er arg positional de emit_signal = destination_bus_name
    assert bus.emit_signal.call_args.args[0] == ":1.42"


def test_notify_stores_sender():
    """notify() debe guardar el sender que le pasa _handle_method_call."""
    mgr = NotificationManager()
    mgr.notify(app_name="X", summary="s", body="b", sender=":1.99")
    # El primer nid es 1
    assert mgr._notifications[1].get("sender") == ":1.99"


def test_on_action_invoked_localhost_url_no_xdgopen():
    """URL apuntando a la maquina local (localhost/127.0.0.1/::1): NO xdg-open.

    Reproduce el fallo visto con el tester: la url del propio server era
    http://localhost:8766/notify-tester.html y Verdantis la abria con xdg-open
    (window duplicada del tester). La maquina local jamas es destino legitimo
    de una notificacion.
    """
    for url in ("http://localhost:8766/notify-tester.html",
                "http://127.0.0.1:8766/x",
                "http://0.0.0.0/x",
                "http://[::1]/x"):
        mgr = _manager_with(10, ["default", "Abrir"], url, "")
        bus = mock.MagicMock()
        mgr.set_dbus(bus)
        with mock.patch.object(vd.subprocess, "Popen") as popen:
            mgr._on_action_invoked(10)
        popen.assert_not_called()


def test_on_action_invoked_private_ip_url_no_xdgopen():
    """URL de red privada (RFC1918 / 192.168.x / 10.x / 172.16-31.x): NO xdg-open."""
    for url in ("http://192.168.1.50/x", "http://10.0.0.5/x", "http://172.16.0.1/x"):
        mgr = _manager_with(11, ["default", "Abrir"], url, "")
        bus = mock.MagicMock()
        mgr.set_dbus(bus)
        with mock.patch.object(vd.subprocess, "Popen") as popen:
            mgr._on_action_invoked(11)
        popen.assert_not_called()
