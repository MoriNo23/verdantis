"""Ningún toast queda sin texto legible.

Los navegadores esconden el título porque va en la línea de app ("Brave - Tab").
Si además el body está vacío (o es solo una URL que se sanitiza), la card queda
con una sola línea y un hueco grande. Sin body, el título vuelve a su fila.
"""
import replay
import toast_helpers as th
import toast_window as tw
from test_contrato_dbus import _manager_headless


def test_browser_con_body_pliega_el_titulo():
    assert th.browser_labels("Brave", "Mi pestaña", "Mensaje nuevo") == (
        "Brave - Mi pestaña", True)


def test_browser_sin_body_muestra_el_titulo():
    assert th.browser_labels("Brave", "Mi pestaña", "   ") == ("Brave", False)
    assert th.browser_labels("Brave", "Mi pestaña", "https://xat.com/sala") == (
        "Brave", False)


def test_daemon_no_pliega_titulo_sin_body(monkeypatch):
    m = _manager_headless()
    vistos = []
    m._show_popup = lambda nid, kw: vistos.append(kw)
    m.notify(app_name="Brave", summary="Mi pestaña", body="",
             hints={"transient": True, "desktop-entry": "brave-browser"},
             expire_timeout=5000)
    kw = vistos[0] if vistos else m._pending[0][1]
    assert kw["hide_title"] is False
    assert kw["app_label"] == "Brave"


def test_replay_no_pliega_titulo_sin_body():
    rec = {"app_name": "Brave", "summary": "Mi pestaña", "body": "",
           "hints": {"desktop-entry": "brave-browser"}, "duration": 6000}
    kw = replay.record_a_kwargs(rec)
    assert kw["hide_title"] is False
    assert kw["app_label"] == "Brave"


def test_card_vacia_recibe_texto_neutro():
    w = tw.ToastCard("sim", "", "", "", None, None, tw.DEFAULT_ACCENT,
                     persistent=True)
    assert w._titulo == "Notificación"
