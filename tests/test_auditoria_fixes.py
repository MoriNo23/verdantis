"""
Tests de remediación de la auditoría (change `auditoria-fixes`).

- prepare() sin WAYLAND_DISPLAY → RuntimeError (antes: print + None →
  one-shot colgado en Gtk.main, daemon con slot fugado).
- _show_popup: si prepare() explota, el hueco se libera y la cola sigue.
- _pending con tope: drop de la MÁS VIEJA, FIFO intacto, estado limpio.
- _on_closed (timer) limpia _dedup como _close_id (leak lento).
- calc_card_height == _layout_metrics (red permanente anti-divergencia).
- Margins por instancia (spec entrada-fallback fija --margin).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import wayland_popup as wp
from wayland_popup import WaylandPopup, NotificationWidget, _layout_metrics
from test_contrato_dbus import FakeBus

from verdantis_daemon import NotificationManager


def _manager_stub_show():
    """Manager con _show_popup stub (sin ventanas) y bus falso."""
    m = NotificationManager(corner="top-right")
    m._scheduler = lambda ms, cb: 0
    m.set_dbus(FakeBus())

    def stub_show(nid, kwargs):
        popup = WaylandPopup(**kwargs)
        m._active.append((nid, popup))

    m._show_popup = stub_show
    return m


# --- 1.1 prepare() sin WAYLAND_DISPLAY ---

def test_prepare_sin_wayland_display_levanta(monkeypatch):
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    popup = WaylandPopup(titulo="t", cuerpo="b")
    try:
        popup.prepare()
    except RuntimeError as e:
        assert "WAYLAND_DISPLAY" in str(e)
    else:
        raise AssertionError(
            "prepare() sin WAYLAND_DISPLAY debe levantar RuntimeError "
            "(antes: print + return None → Gtk.main colgado)")


def test_show_popup_con_prepare_roto_libera_hueco(monkeypatch):
    from verdantis_daemon import WaylandPopup as _WP
    monkeypatch.setattr(_WP, "prepare", lambda self: (_ for _ in ()).throw(
        RuntimeError("simulado")))
    m = NotificationManager(corner="top-right")
    m._scheduler = lambda ms, cb: 0
    m.set_dbus(FakeBus())
    nid1 = m.notify(app_name="a", summary="s1", body="b1",
                    hints={"transient": True}, expire_timeout=5000)
    nid2 = m.notify(app_name="a", summary="s2", body="b2",
                    hints={"transient": True}, expire_timeout=5000)
    m._pump()
    # prepare explotó: el hueco NO queda fugado y la siguiente sigue viva
    assert nid1 not in [aid for aid, _ in m._active], "slot fugado"
    assert nid1 not in m._notifications, "estado huérfano del popup roto"
    assert nid2 in [aid for aid, _, _ in m._pending] or \
        nid2 in [aid for aid, _ in m._active], "la cola murió con el popup"


# --- 1.2 Tope de _pending ---

def test_pending_con_tope_dropea_la_mas_vieja():
    m = _manager_stub_show()
    for i in range(25):
        m.notify(app_name="flood", summary="s", body="b{}".format(i),
                 hints={"transient": True}, expire_timeout=5000)
    pend = [nid for nid, _, _ in m._pending]
    assert len(pend) == 20, "la cola SHALL toparse en 20"
    assert pend == list(range(6, 26)), (
        "se dropea la MÁS VIEJA; la recién llegada queda y el resto conserva FIFO")
    for nid in range(1, 6):
        assert nid not in m._notifications, "estado huérfano de la dropeada"
        assert nid not in [v[0] for v in m._dedup.values()], (
            "dedup huérfano de la dropeada")


# --- 1.3 _on_closed limpia _dedup ---

def test_cierre_por_timer_limpia_dedup():
    m = _manager_stub_show()
    nid = m.notify(app_name="t", summary="s", body="b",
                   hints={"transient": True}, expire_timeout=5000)
    m._pump()
    assert any(v[0] == nid for v in m._dedup.values()), "sanidad: entró al dedup"
    m._active[0][1]._close()  # timer path → _on_closed
    assert not any(v[0] == nid for v in m._dedup.values()), (
        "el path de timer también limpia _dedup (leak lento por contenido único)")


# --- 1.4 Igualdad de altura: red permanente ---

def _calc_viejo_y_metrics(app, cuerpo, expanded, actions_count):
    """calc_card_height ACTUAL vs _layout_metrics con los mismos args."""
    body_fs = max(9, round(wp._BODY_FS * 1.0))
    h_calc = WaylandPopup.calc_card_height(
        app, cuerpo, "", text_width=wp._TEXT_COL_W, expanded=expanded,
        hide_title=False, font_scale=1.0, actions_count=actions_count)
    lay = _layout_metrics(
        cuerpo, wp._TEXT_COL_W, body_fs, app, False, expanded,
        actions_count > 0, wp._IMAGE_LEFT_W, NotificationWidget._MAX_VISIBLE_LINES,
        NotificationWidget._BTN_H)
    return h_calc, wp._PAD + lay.row_h + wp._PAD


def test_altura_calc_igual_a_layout_metrics():
    casos = [
        ("app", "corto", False, 0),
        ("app", "texto " * 40, False, 0),
        ("app", "texto " * 40, False, 2),
        ("app", "texto " * 40, True, 1),
        ("app", "una línea con contenido medio", False, 3),
    ]
    for app, cuerpo, expanded, actions in casos:
        h_calc, h_metrics = _calc_viejo_y_metrics(app, cuerpo, expanded, actions)
        assert h_calc == h_metrics, (
            "calc_card_height y _layout_metrics divergieron en {!r} "
            "(render desborda o deja slack)".format((cuerpo[:20], expanded, actions)))


# --- 1.5 Margins por instancia ---

def test_margins_por_instancia_desde_self_margin():
    p = WaylandPopup(titulo="t", cuerpo="b", margin=42)
    assert p._margins["top-right"] == (42, 42, 0, 0), (
        "--margin debe honrarse en Wayland (spec entrada-fallback)")
    d = WaylandPopup(titulo="t", cuerpo="b")
    assert d._margins["top-right"] == (16, 16, 0, 0), "default intacto"
