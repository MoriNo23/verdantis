"""
Tests del contrato click→ActionInvoked (spec freedesktop 1.2).

Contrato vigente (tras el fix "no abrir navegadores a lo loco"):
- El click emite ActionInvoked con la key REAL del sender (BUG-2), o nada si no hay.
- El click NUNCA lanza una ventana de la app (se eliminó el spawn → no más Firefox
  duplicados). El foco lo resuelve el sender vía ActionInvoked, o xdg-open si hay URL.
"""
import sys
import os
from unittest.mock import Mock

os.environ.setdefault("GDK_BACKEND", "wayland")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from verdantis_daemon import NotificationManager, _pick_action_key


class FakeBus:
    """Bus falso: registra los ActionInvoked emitidos."""

    def __init__(self):
        self.emitted = []

    def emit_signal(self, *args):
        self.emitted.append(args)


def _manager_with_notification(actions=None, hints=None, app_name="firefox"):
    m = NotificationManager(corner="top-right")
    m.set_dbus(FakeBus())
    nid = m.notify(
        app_name=app_name, app_icon="", summary="t", body="b",
        actions=actions or [], hints=hints or {}, expire_timeout=5000,
    )
    return m, nid


def _invoked_keys(m):
    """Keys ActionInvoked emitidas (ignora NotificationClosed)."""
    return [
        e[4].unpack()[1]
        for e in m._dbus_bus.emitted
        if e[3] == "ActionInvoked"
    ]


def _popens(m, monkeypatch):
    """Captura los xdg-open lanzados por el click."""
    popens = []
    monkeypatch.setattr(
        "verdantis_daemon.subprocess.Popen",
        lambda cmd, **k: popens.append(cmd),
    )
    return popens


# --- _pick_action_key (lógica pura) ---

def test_pick_action_key_default_when_provided():
    assert _pick_action_key(["default", "Abrir"]) == "default"
    assert _pick_action_key(["default", "Abrir", "open", "Ir"]) == "default"


def test_pick_action_key_first_real_key():
    # Sin "default", la primera key real manda (spec: emitir la key del sender)
    assert _pick_action_key(["open", "Ir"]) == "open"
    assert _pick_action_key(["reply", "Responder", "open", "Ir"]) == "reply"


def test_pick_action_key_none_without_actions():
    assert _pick_action_key([]) is None
    assert _pick_action_key(None) is None
    assert _pick_action_key(["solo_key_sin_label"]) is None


# --- BUG-2: emitir la key real, nunca inventar ---

def test_action_invoked_emits_real_key(monkeypatch):
    m, nid = _manager_with_notification(actions=["open", "Ir"])
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert _invoked_keys(m) == ["open"]
    assert popens == [], "sin URL no hay xdg-open"


def test_action_invoked_no_signal_without_actions(monkeypatch):
    m, nid = _manager_with_notification(actions=[])
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert _invoked_keys(m) == []
    assert popens == []


# --- Contrato central: el click NUNCA abre ventanas de la app ---

def test_no_spawn_with_default_action(monkeypatch):
    # Caso navegador: ActionInvoked("default") y nada más (el navegador se enfoca solo)
    m, nid = _manager_with_notification(
        actions=["default", "Abrir"], hints={"desktop-entry": "firefox"},
    )
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert _invoked_keys(m) == ["default"]
    assert popens == [], "con action default y sin URL no se abre nada"


def test_no_spawn_without_actions(monkeypatch):
    # Notificación plana sin URL: se cierra sin spawn (antes abría Firefox a lo loco)
    m, nid = _manager_with_notification(actions=[], hints={"desktop-entry": "firefox"})
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert _invoked_keys(m) == []
    assert popens == [], "sin URL y sin actions no se lanza ninguna app"


def test_no_spawn_with_custom_action_key(monkeypatch):
    # Action custom: emitir su key, pero igual NO lanzar ventanas
    m, nid = _manager_with_notification(actions=["open", "Ir"])
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert _invoked_keys(m) == ["open"]
    assert popens == []


# --- URL: única vía de redirigir (xdg-open → tab del navegador por defecto) ---

def test_url_opens_via_xdg_open(monkeypatch):
    m, nid = _manager_with_notification(
        actions=["default", "Abrir"],
        hints={"x-kde-urls": ["https://example.com"]},
    )
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert popens and popens[0] == ["xdg-open", "https://example.com"]
    assert _invoked_keys(m) == ["default"]


def test_url_without_actions_still_opens(monkeypatch):
    m, nid = _manager_with_notification(
        actions=[],
        hints={"url": "https://example.org"},
    )
    popens = _popens(m, monkeypatch)
    m._on_action_invoked(nid)
    assert popens and popens[0] == ["xdg-open", "https://example.org"]
    assert _invoked_keys(m) == []


# --- Navegador: línea "Brave - <tab>" (app_label) + título plegado ---

def test_is_browser_detection():
    from verdantis_daemon import _is_browser
    assert _is_browser("Brave", "brave-browser-nightly") is True
    assert _is_browser("Firefox", "firefox.desktop") is True
    assert _is_browser("Telegram", "telegramdesktop") is False
    assert _is_browser("", "org.kde.dolphin") is False


def test_browser_notification_gets_app_label():
    # Payload real de Brave: desktop-entry brave-browser-nightly → app_label + hide_title
    m = NotificationManager(corner="top-right")
    m.set_dbus(FakeBus())
    nid = m.notify(
        app_name="Brave", app_icon="",
        summary="Verdantis Test", body="clické",
        actions=["default", "Activate"],
        hints={"desktop-entry": "brave-browser-nightly", "urgency": 1},
        expire_timeout=5000,
    )
    popup = m._active[0][1]
    assert popup.app_label == "Brave - Verdantis Test"
    assert popup.hide_title is True


def test_non_browser_no_app_label():
    m = NotificationManager(corner="top-right")
    m.set_dbus(FakeBus())
    nid = m.notify(
        app_name="Telegram", app_icon="",
        summary="Mensaje", body="hola",
        actions=[], hints={"desktop-entry": "telegramdesktop"},
        expire_timeout=5000,
    )
    popup = m._active[0][1]
    assert popup.app_label is None
    assert popup.hide_title is False


def test_local_path_strips_file_uri():
    from verdantis_daemon import _local_path
    assert _local_path("file:///tmp/logo.png") == "/tmp/logo.png"
    assert _local_path("/tmp/logo.png") == "/tmp/logo.png"
    assert _local_path("") == ""
