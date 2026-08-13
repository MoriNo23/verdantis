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
