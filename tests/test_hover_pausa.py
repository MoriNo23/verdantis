"""Pausa del vencimiento con hover (spec `toast-franja-descarte`, ADDED).

Sin hover el wipe avanza con el reloj; con el puntero sobre el card se
congela (crédito que compensa tick a tick) y al salir reanuda con el tiempo
restante — sin esto, la X de un toast de 6s es una carrera perdida contra
el timer que el usuario siempre pierde.

Headless: WaylandPopup sin window ni card real (prepare()/_build_ui nunca se
llaman, igual que en test_contrato_dbus). El card es un stub con la interfaz
que _update_progress toca (_hover + set_fraction) y el reloj un stub inyectado
SOLO en el `time` del módulo — el render lo verifica el usuario (spec
`verificacion-visual`).
"""
import types

import wayland_popup
from wayland_popup import WaylandPopup


class _CardStub:
    """Card mínimo: guarda la fracción que le pasa set_fraction."""

    def __init__(self):
        self._hover = False
        self._fraction = 1.0

    def set_fraction(self, f):
        self._fraction = f


def _popup_con_card(duration=5000):
    p = WaylandPopup(duration=duration)
    p._card = _CardStub()
    return p


def _con_reloj(monkeypatch, popup):
    reloj = {"t": 0.0}
    monkeypatch.setattr(
        wayland_popup, "time",
        types.SimpleNamespace(monotonic=lambda: reloj["t"]))
    popup._start = reloj["t"]
    return reloj


def test_hover_congela_el_wipe(monkeypatch):
    p = _popup_con_card()
    reloj = _con_reloj(monkeypatch, p)
    reloj["t"] = 1.0                       # 1s sin hover: 1/5 consumido
    p._update_progress()
    f0 = p._card._fraction
    assert abs(f0 - 0.8) < 1e-9

    p._card._hover = True
    for _ in range(10):                    # 500ms de ticks CON cursor encima
        reloj["t"] += 0.05
        p._update_progress()
    assert abs(p._card._fraction - f0) < 1e-9, (
        "con hover el wipe no avanza: el vencimiento está en pausa"
    )


def test_al_salir_reanuda_con_el_tiempo_restante(monkeypatch):
    p = _popup_con_card()
    reloj = _con_reloj(monkeypatch, p)
    reloj["t"] = 1.0
    p._update_progress()
    f0 = p._card._fraction
    p._card._hover = True
    for _ in range(10):
        reloj["t"] += 0.05
        p._update_progress()
    p._card._hover = False
    reloj["t"] += 0.05                     # un tick fuera del card
    p._update_progress()
    f = p._card._fraction
    assert f0 - 0.05 < f < f0, (
        "al salir reanuda desde el tiempo restante: ni se reinicia (f0) "
        "ni vence de golpe"
    )


def test_persistente_no_cambia_con_hover(monkeypatch):
    """duration=0 nunca vence: el hover no le agrega comportamiento."""
    p = _popup_con_card(duration=0)
    reloj = _con_reloj(monkeypatch, p)
    p._card._hover = True
    reloj["t"] += 60.0                     # una hora con el cursor encima
    assert p._update_progress() is False
    assert p._card._fraction == 1.0       # sin wipe que congelar
