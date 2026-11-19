"""El hover no reacomoda la card, el cierre vive en un rail fijo y el body no
se justifica.

Motivo (review de diseño 2026-11-18, P0): `_strip_w()` devolvía 80 px con
CUALQUIER hover, así que la columna de texto pasaba de 240 a 160 px, el botón
Copiar se corría 80 px y `desired_height()` podía cambiar con él — la card se
deformaba al pasar el mouse y el control destructivo aparecía bajo el puntero.
El rail de cierre queda reservado siempre: el hover solo lo tiñe.
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gtk, Pango

import toast_window as wp


def _widget(cuerpo="Tu código de verificación es 482193",
            acciones=None, hover=False):
    w = wp.ToastCard.__new__(wp.ToastCard)
    w.__dict__.update(
        _cuerpo=cuerpo, _app_name="Brave", _hide_title=False,
        _expanded=False, _actions=acciones or [], _fraction=0.6,
        _hover=hover,
        _accent_rgb=wp._hex_rgb("#80cbc4"),
        _card_bg=wp._hex_rgb(wp._CARD_BG_HEX),
        _left_title=wp._hex_rgb(wp._TXT_TITLE_L),
        _left_body=wp._hex_rgb(wp._TXT_BODY_L),
        _left_app=wp._hex_rgb(wp._TXT_APP_L),
        _right_title=wp._hex_rgb(wp._TXT_TITLE_R),
        _right_body=wp._hex_rgb(wp._TXT_BODY_R),
        _right_app=wp._hex_rgb(wp._TXT_APP_R),
        _titulo="Título", _app_label=None, _font_scale=1.0,
        _image_left_pb=None, _image_pb=None, _app_icon_pb=None,
        _action_icon_pbs={}, _action_rects=[], _close_rect=None,
        _copy_rect=None, _copy_text=wp._find_code(cuerpo),
        _copy_done=False,
        _pressed_copy=False, _hover_copy=False, _hover_close=False,
        _pressed_action_idx=None, _pressed_close=False,
        _hover_action_idx=None,
    )
    w.get_width = lambda: 360
    w.get_height = lambda: w.desired_height()
    w.queue_draw = lambda: None
    return w


# ── RED 1: el hover no cambia el ancho de texto ──────────────────────────

def test_el_hover_no_cambia_el_ancho_de_la_columna_de_texto():
    reposo = _widget(hover=False)._eff_text_width()
    hover = _widget(hover=True)._eff_text_width()
    assert reposo == hover, (
        "el hover movía la columna de 240 a 160 px: la card se reacomoda "
        "al pasar el mouse")


def test_el_hover_no_cambia_el_alto_de_la_card():
    cuerpo = ("Reunión a las 5pm en la sala grande con el equipo de "
              "infraestructura para revisar el incidente del viernes.")
    reposo = _widget(cuerpo, hover=False).desired_height()
    hover = _widget(cuerpo, hover=True).desired_height()
    assert reposo == hover, (
        "un body largo cambia de alto con el hover y la pila de toasts salta")


# ── RED 2: el rail de cierre está reservado en reposo ────────────────────

def test_el_rail_de_cierre_existe_tambien_en_reposo():
    w = _widget(hover=False)
    Gtk.Snapshot.new()
    snap = Gtk.Snapshot.new()
    w.do_snapshot(snap)
    assert w._close_rect is not None, (
        "sin hover no había rect de cierre: el rail debe estar reservado")
    ancho = w._close_rect[2] - w._close_rect[0]
    assert ancho == wp.ToastCard._CLOSE_RAIL_W
    assert ancho >= 24, "WCAG 2.5.8: target mínimo 24x24"


def test_el_rail_no_invade_la_columna_de_texto():
    w = _widget(hover=False)
    snap = Gtk.Snapshot.new()
    w.do_snapshot(snap)
    x0, _, x1, _ = w._close_rect
    assert x1 - x0 <= 32
    assert x0 >= 360 - 14 - 32, "el rail debe vivir en el padding derecho"


# ── RED 3: copiar confirma sin mover nada ────────────────────────────────

def test_copiar_muestra_confirmacion(monkeypatch):
    monkeypatch.setattr(wp, "_copy_to_clipboard", lambda t: True)
    w = _widget()
    w._copy_rect = (14, 100, 332, 128)
    w._copy_text = "482193"
    assert w._on_press_xy(100, 110) is True
    assert w._on_release_xy(100, 110) is True
    assert w._copy_label() == "Copiado"


def test_la_confirmacion_se_apaga_sola():
    w = _widget()
    w._marcar_copiado()
    assert w._copy_label() == "Copiado"
    assert w._fin_copiado() is False, "el timeout de GLib debe devolver False"
    assert w._copy_label() == "Copiar código"


# ── RED 4: el body no se justifica ───────────────────────────────────────

def test_el_body_no_se_justifica():
    """`_body_layout` es lo que dibuja el body: a 212 px el justificado abre
    ríos entre palabras. Debe ir a bandera derecha."""
    cuerpo = "Tu código de verificación es 482193. No lo compartas."
    lay = wp._body_layout(cuerpo, 11, 212, max_lines=3)
    assert lay.get_justify() is False, (
        "justificar a 212 px genera ríos entre palabras")
