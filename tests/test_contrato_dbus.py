"""
Tests del contrato D-Bus de cierre (spec `contrato-dbus`, freedesktop 1.2).

NotificationClosed(id, reason) por path de cierre:
  - timer vence → razón 1
  - usuario (franja, cuerpo, botón, teclado) → razón 2, con ActionInvoked
    ANTES de NotificationClosed cuando el path incluye una acción
  - CloseNotification del bus → razón 3
  - replaces_id / dedup / replay → sin emisión alguna
GetServerInformation reporta spec_version "1.2" (posición 4).

Manager headless: scheduler no-op + `_pump()` manual + WaylandPopup real sin
window (prepare() nunca se llama). FakeBus registra las señales emitidas.
"""
from unittest.mock import Mock

import verdantis_daemon
from verdantis_daemon import NotificationManager, NotificationDaemon, VERSION
from app_info import APP_NAME, VENDOR
from wayland_popup import WaylandPopup


class FakeBus:
    """Bus falso: registra cada emit_signal como tupla de args."""

    def __init__(self):
        self.emitted = []

    def emit_signal(self, *args):
        self.emitted.append(args)


def _manager_headless():
    m = NotificationManager(corner="top-right")
    m._scheduler = lambda ms, cb: 0
    m.set_dbus(FakeBus())

    def headless_show(nid, kwargs):
        popup = WaylandPopup(**kwargs)
        m._active.append((nid, popup))

    m._show_popup = headless_show
    return m


def _manager_con_toast(actions=None, hints=None, **extra):
    """Manager + un toast ya visible (notificación transient: nada a disco)."""
    m = _manager_headless()
    hints = {"transient": True, **(hints or {})}
    nid = m.notify(
        app_name="t", app_icon="", summary="s", body="b",
        actions=actions or [], hints=hints, expire_timeout=5000, **extra,
    )
    m._pump()
    return m, nid


def _closes(bus):
    return [e[4].unpack() for e in bus.emitted if e[3] == "NotificationClosed"]


def _invokes(bus):
    return [e[4].unpack() for e in bus.emitted if e[3] == "ActionInvoked"]


# --- Razón 1: vencimiento por timer ---

def test_timer_expiry_emite_razon_1():
    m, nid = _manager_con_toast()
    # Lo que hace WaylandPopup._update_progress al llegar a 0: _close() sin fuente.
    m._active[0][1]._close()
    assert _closes(m._dbus_bus) == [(nid, 1)]


# --- Razón 2: cierre por usuario ---

def test_cierre_usuario_franja_emite_razon_2():
    # Franja/pill del persistente → WaylandPopup._close("user")
    m, nid = _manager_con_toast()
    m._active[0][1]._close("user")
    assert _closes(m._dbus_bus) == [(nid, 2)]
    assert _invokes(m._dbus_bus) == []


def test_click_cuerpo_con_default_action_invoked_antes_de_closed():
    m, nid = _manager_con_toast(actions=["default", "Abrir"])
    # Click del cuerpo: el widget llama on_click(None) → _on_action_invoked(nid).
    m._on_action_invoked(nid)
    assert _invokes(m._dbus_bus) == [(nid, "default")]
    assert _closes(m._dbus_bus) == [(nid, 2)]
    nombres = [e[3] for e in m._dbus_bus.emitted]
    assert nombres.index("ActionInvoked") < nombres.index("NotificationClosed")


def test_click_cuerpo_url_sin_default_razon_2(monkeypatch):
    # Sin actions pero con URL: no hay ActionInvoked, solo cierre razón 2.
    monkeypatch.setattr(
        "verdantis_daemon.subprocess.Popen", lambda cmd, **k: None)
    m, nid = _manager_con_toast(hints={"url": "https://ejemplo.com/x"})
    m._on_action_invoked(nid)
    assert _invokes(m._dbus_bus) == []
    assert _closes(m._dbus_bus) == [(nid, 2)]


def test_click_boton_accion_key_real_y_razon_2():
    m, nid = _manager_con_toast(actions=["settings", "Ajustes"])
    m._on_action_invoked(nid, "settings")
    assert _invokes(m._dbus_bus) == [(nid, "settings")]
    assert _closes(m._dbus_bus) == [(nid, 2)]
    nombres = [e[3] for e in m._dbus_bus.emitted]
    assert nombres.index("ActionInvoked") < nombres.index("NotificationClosed")


# --- Razón 3: CloseNotification del bus ---

def test_close_notification_dbus_razon_3():
    m, nid = _manager_con_toast()
    m._close_id(nid)
    assert _closes(m._dbus_bus) == [(nid, 3)]


# --- No-cierres: replaces_id, dedup, replay ---

def test_replaces_id_no_emite():
    m, nid1 = _manager_con_toast()
    m.notify(
        app_name="t", app_icon="", summary="s2", body="b2",
        actions=[], hints={"transient": True}, expire_timeout=5000,
        replaces_id=nid1,
    )
    assert _closes(m._dbus_bus) == [], (
        "reemplazo in-place: la notificación reemplazada sigue viva, "
        "no es un cierre"
    )


def test_dedup_no_emite():
    m, _ = _manager_con_toast()
    m.notify(
        app_name="t", app_icon="", summary="s", body="b",
        actions=[], hints={"transient": True}, expire_timeout=5000,
    )
    assert _closes(m._dbus_bus) == [], (
        "dedup por contenido: el duplicado reemplaza al vivo, no lo cierra"
    )


def test_replay_no_emite_ni_cierre_ni_accion():
    m = _manager_headless()
    nid_acc = m.notify(
        app_name="r", summary="s", body="b",
        actions=["default", "Abrir"], hints={"transient": True},
        expire_timeout=5000, replay=True,
    )
    m._pump()
    m._on_action_invoked(nid_acc)
    nid_exp = m.notify(
        app_name="r", summary="otro", body="b",
        hints={"transient": True}, expire_timeout=5000, replay=True,
    )
    m._pump()
    m._active[0][1]._close()
    assert m._dbus_bus.emitted == [], (
        "replay del dashboard: dibuja el card pero no toca el bus"
    )


# --- GetServerInformation: spec_version 1.2 ---

def test_get_server_information_spec_version():
    d = NotificationDaemon()
    invocation = Mock()
    d._handle_method_call(
        None, ":1.1", "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications", "GetServerInformation",
        None, invocation,
    )
    variant = invocation.return_value.call_args[0][0]
    nombre, vendor, version, spec_version = variant.unpack()
    assert (nombre, vendor) == (APP_NAME, VENDOR)
    assert version == VERSION
    assert spec_version == "1.2"
