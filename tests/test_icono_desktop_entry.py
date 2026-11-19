"""El icono se resuelve como Plasma: manda `desktop-entry`, no el nombre visual.

KDE (`Notification::Private::processFdoHints`) usa `hints["desktop-entry"]` con
`KService::serviceByDesktopName` para sacar `Icon=`. `app_name` es sólo fallback
y suele estar localizado ("Correo", "Courrier") o ser un nombre de proceso.
"""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

import toast_helpers as th

Gtk.init_check()   # el lookup de tema necesita un display GTK


def test_desktop_entry_resuelve_icono_cuando_app_name_no_matchea():
    path = th._exact_desktop_file("Correo", desktop_entry="thunderbird")
    assert path and path.endswith("thunderbird.desktop")


def test_icono_de_tema_por_desktop_entry():
    pb = th._get_app_icon_from_desktop(
        "Correo", 80, desktop_entry="thunderbird")
    assert pb is not None and pb.get_width() == 80


def test_app_name_sigue_siendo_fallback():
    path = th._exact_desktop_file("Thunderbird")
    assert path and path.endswith("thunderbird.desktop")


def test_desktop_entry_inexistente_cae_al_fallback():
    path = th._exact_desktop_file("Thunderbird", desktop_entry="no-existe-xyz")
    assert path and path.endswith("thunderbird.desktop")


def test_daemon_pasa_desktop_entry_al_popup():
    import daemon
    from test_contrato_dbus import _manager_headless
    m = _manager_headless()
    vistos = []
    m._show_popup = lambda nid, kw: vistos.append(kw)
    m.notify(app_name="Correo", app_icon="", summary="s", body="b",
             hints={"transient": True, "desktop-entry": "thunderbird"},
             expire_timeout=5000)
    kw = vistos[0] if vistos else m._pending[0][1]
    assert kw["desktop_entry"] == "thunderbird"


def test_replay_pasa_desktop_entry():
    import replay
    kw = replay.record_a_kwargs({
        "app_name": "Correo", "summary": "s", "body": "b", "duration": 6000,
        "hints": {"desktop-entry": "thunderbird"},
    })
    assert kw["desktop_entry"] == "thunderbird"


def test_card_resuelve_icono_con_desktop_entry():
    import toast_window as tw
    w = tw.ToastCard("Correo", "", "s", "b", None, None, tw.DEFAULT_ACCENT,
                     desktop_entry="thunderbird")
    assert w._image_left_pb is not None
