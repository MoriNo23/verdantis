"""Hallazgos de la auditoría: cola de iconos, historial hinchado, URL local,
prepare fallido y critical en replay. Cada test falla antes del fix.
"""
import sys
from pathlib import Path

sys.path.insert(0, "tests")

import daemon as vd
import history_store
import replay
from gi.repository import GLib
from test_contrato_dbus import FakeBus
from test_replay_cli import _manager, datos  # noqa: F401 (fixture)


def test_iconos_no_colisionan_entre_reinicios(datos):
    png = datos / "viejo.png"
    png.write_bytes(b"viejo")
    a = history_store.copy_icon(1, str(png), "avatar")
    Path(history_store.icon_path(a)).write_bytes(b"VIEJO")
    b = history_store.write_icon(1, b"NUEVO", "avatar")
    assert a != b
    assert Path(history_store.icon_path(a)).read_bytes() == b"VIEJO"


def test_historial_no_duplica_los_bytes_de_image_data(datos):
    m = _manager()
    m.notify(app_name="Brave", summary="tab", body="b",
             hints={"image-data": (64, 64, 256, True, 8, 4,
                                   bytes(range(256)) * 64)},
             expire_timeout=6000)
    linea = Path(history_store._history_path()).read_text()
    assert "image-data" not in linea, "el variant binario se guardó como texto"
    assert len(linea) < 2000, "historial hinchado: %d bytes" % len(linea)


def test_local_url_en_decimal_y_hex():
    for url in ("http://2130706433/", "http://0x7f000001/",
                "http://[::ffff:127.0.0.1]/"):
        assert vd._is_local_url(url), url


def test_prepare_fallido_emite_notification_closed(monkeypatch):
    m = vd.NotificationManager(corner="top-right")
    m._scheduler = lambda ms, cb: 0
    bus = FakeBus()
    m.set_dbus(bus)

    def explotar(self):
        raise RuntimeError("sin layer-shell")

    monkeypatch.setattr(vd.ToastWindow, "prepare", explotar)
    m.notify(app_name="t", summary="s", body="b",
             hints={"transient": True}, expire_timeout=5000)
    m._pump()          # el scheduler de tests no dispara solo
    cerradas = [e for e in bus.emitted if e[3] == "NotificationClosed"]
    assert cerradas, "el sender nunca recibió el cierre"
    assert cerradas[-1][4].unpack()[1] == 3


def test_replay_de_critical_es_persistente():
    kw = replay.record_a_kwargs({"hints": {"urgency": 2}, "duration": 6000})
    assert kw["duration"] == 0


def test_replay_respeta_duration_explicita_en_critical():
    kw = replay.record_a_kwargs(
        {"hints": {"urgency": 2}, "duration": 6000}, duration=3000)
    assert kw["duration"] == 3000
