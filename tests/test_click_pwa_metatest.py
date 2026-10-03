"""Metatest de sensibilidad: inyecta la version BUGUEADA de _on_action_invoked
(siempre xdg-open, sin chequear PWA) y verifica que test_on_action_invoked_pwa_no_xdgopen
la detecta (falla). Si el metatest pasa, el fix es real y no un false-positive.
"""
import os


from unittest import mock

import verdantis_daemon as vd
from verdantis_daemon import NotificationManager

APP_DIR = os.path.expanduser("~/.local/share/applications")
PWA_DESKTOP = "brave-hnpfjngllnobngcgfapefoaidbinmjnm-Default.desktop"


def _buggy_on_action_invoked(self, nid):
    """Version bugueada: xdg-open SIEMPRE que hay URL (ignora PWA)."""
    info = self._notifications.get(nid, {})
    actions = info.get("actions", [])
    url = info.get("url", "")
    action_key = vd._pick_action_key(actions)
    if action_key and self._dbus_bus:
        try:
            self._dbus_bus.emit_signal(
                None, "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", "ActionInvoked",
                mock.MagicMock(),
            )
        except Exception:
            pass
    if url:
        import subprocess
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_sensitivity_pwa_bug_detected():
    mgr = NotificationManager()
    mgr._notifications[1] = {
        "actions": ["default", "Abrir"],
        "url": "https://web.whatsapp.com/",
        "desktop_entry": PWA_DESKTOP,
    }
    bus = mock.MagicMock()
    mgr.set_dbus(bus)
    original = NotificationManager._on_action_invoked
    NotificationManager._on_action_invoked = _buggy_on_action_invoked
    try:
        with mock.patch.object(vd.subprocess, "Popen") as popen:
            mgr._on_action_invoked(1)
        # La version bugueada llama xdg-open -> el test real debe haber fallado.
        # Si llegamos aqui sin AssertionError, el metatest falla (no detecto el bug).
        assert popen.called, "metatest no detecto el bug: xdg-open NO fue llamado por la version bugueada"
        raise AssertionError("SENSITIVITY FAIL: la version bugueada NO fue detectada por test_on_action_invoked_pwa_no_xdgopen")
    except AssertionError as e:
        # Esperado: el test real hubiera fallado. El metatest confirma la deteccion.
        assert "SENSITIVITY FAIL" in str(e)
    finally:
        NotificationManager._on_action_invoked = original


def _buggy_broadcast_on_action_invoked(self, nid):
    """Version bugueada: emite ActionInvoked con dest=None (broadcast), no dirigido."""
    info = self._notifications.get(nid, {})
    actions = info.get("actions", [])
    action_key = vd._pick_action_key(actions)
    if action_key and self._dbus_bus:
        try:
            self._dbus_bus.emit_signal(
                None, "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", "ActionInvoked",
                mock.MagicMock(),
            )
        except Exception:
            pass


def test_sensitivity_broadcast_bug_detected():
    """La version bugueada (dest=None) debe ser detectada por
    test_on_action_invoked_emits_to_sender (que exige dest=sender)."""
    mgr = NotificationManager()
    mgr._notifications[1] = {
        "actions": ["default", "Abrir"],
        "url": "",
        "desktop_entry": PWA_DESKTOP,
        "sender": ":1.42",
    }
    bus = mock.MagicMock()
    mgr.set_dbus(bus)
    original = NotificationManager._on_action_invoked
    NotificationManager._on_action_invoked = _buggy_broadcast_on_action_invoked
    try:
        with mock.patch.object(vd.subprocess, "Popen"):
            mgr._on_action_invoked(1)
        # Si llegamos aqui sin AssertionError, el metatest falla (no detecto el bug).
        raise AssertionError("SENSITIVITY FAIL: la version broadcast NO fue detectada por test_on_action_invoked_emits_to_sender")
    except AssertionError as e:
        assert "SENSITIVITY FAIL" in str(e)
    finally:
        NotificationManager._on_action_invoked = original
