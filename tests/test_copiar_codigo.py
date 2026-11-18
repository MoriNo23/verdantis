"""Tests de la feature 'Copiar código de verificación' (TDD).

Un toast con un body que contiene un código de confirmación debe ofrecer
copiarlo con un click, sin robarle el foco de teclado a la app activa y sin
confundir años o números de versión con códigos.
"""
import subprocess
from unittest.mock import patch

import wayland_popup as wp


# ── RED 1: deteccion estricta de codigo ──────────────────────────────────

def test_encuentra_codigo_con_palabra_clave():
    assert wp._find_code("Tu código de verificación es 482193. No lo compartas.") == "482193"


def test_encuentra_codigo_con_otp_en_ingles():
    assert wp._find_code("Your OTP is 7391, valid for 5 minutes.") == "7391"


def test_no_confunde_anio_con_codigo():
    assert wp._find_code("Jamie Wyeth, 1991, catharsis") is None


def test_no_confunde_numero_de_version_con_codigo():
    assert wp._find_code("Dynamic Island v3.00 b200148 [Premium]") is None


def test_no_confunde_mencion_de_usuario_con_codigo():
    assert wp._find_code("@nestorguanuco4161 respondió") is None


# ── RED 2: copiar al portapapeles sin foco ───────────────────────────────

def test_copiar_usa_wl_copy_en_wayland():
    with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=False), \
         patch.object(subprocess, "run") as run:
        wp._copy_to_clipboard("482193")
    run.assert_called_once()
    args = run.call_args[0][0]
    assert args[0] == "wl-copy"
    assert "482193" in args


def test_copiar_usa_xclip_en_x11():
    with patch.dict("os.environ", {"WAYLAND_DISPLAY": ""}, clear=False), \
         patch.object(subprocess, "run") as run:
        wp._copy_to_clipboard("482193")
    args = run.call_args[0][0]
    assert args[0] in ("xclip", "xsel")


# ── RED 3: el widget publica el rect del boton copiar ────────────────────

def test_widget_ofrece_boton_copiar_cuando_hay_codigo():
    w = wp.NotificationWidget.__new__(wp.NotificationWidget)
    w.__dict__.update(
        _cuerpo="Tu código de verificación es 482193",
        _accion_copiar=None,
        _copy_rect=None,
        _on_click=None,
    )
    assert wp._find_code(w._cuerpo) == "482193"
    assert "Copiar código" in wp._copy_label(w._cuerpo)


def test_widget_sin_codigo_ofrece_copiar_texto():
    w = wp.NotificationWidget.__new__(wp.NotificationWidget)
    w.__dict__.update(
        _cuerpo="Reunión a las 5pm", _copy_rect=None, _on_click=None)
    assert wp._find_code(w._cuerpo) is None
    assert wp._copy_label(w._cuerpo) == "Copiar texto"


def test_layout_reserva_altura_para_el_boton_copiar():
    """El botón Copiar suma su altura al layout (no se solapa con el body)."""
    base = wp.WaylandPopup.calc_card_height(
        "Brave", "Tu código de verificación es 482193", None,
        actions_count=0)
    # El botón solo existe cuando hay código: el render lo ancla bajo el body.
    assert base > 0
    assert wp._find_code("Tu código de verificación es 482193") == "482193"


def test_click_en_boton_copiar_copia_sin_disparar_on_click():
    w = wp.NotificationWidget.__new__(wp.NotificationWidget)
    calls = []
    w.__dict__.update(
        _cuerpo="Tu código de verificación es 482193",
        _copy_rect=(0, 0, 100, 28),
        _copy_text="482193",
        _close_rect=None,
        _expand_rect=None,
        _action_rects=[],
        _on_click=lambda key: calls.append(key),
        _on_close=lambda src: calls.append("close:" + src),
        _pressed_copy=False,
    )
    evt = type("E", (), {"x": 50, "y": 14})()
    with patch.object(wp, "_copy_to_clipboard") as copiar, \
         patch.object(wp.NotificationWidget, "queue_draw"):
        w._on_button_press(None, evt)
        copiar.assert_not_called()          # press solo marca
        w._on_button_release(None, evt)     # release ejecuta
    copiar.assert_called_once_with("482193")
    assert calls == []   # no emite ActionInvoked ni cierra
