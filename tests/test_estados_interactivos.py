"""Estados pressed de franja/X y botones (specs `toast-franja-descarte` y
`toast-acciones`, ADDED "estados interactivos").

Routing press/release: la acción se ejecuta al SOLTAR dentro del mismo rect;
presionar marca el estado pressed (tinte más intenso) y consume; soltar
fuera cancela y restaura. La barra "Ver más" queda press-based (PRODUCT.md
no la nombra).

Headless: `NotificationWidget.__new__` + attrs inyectados — el routing es
lógica propia, el render lo verifica el usuario (spec `verificacion-visual`).
"""
from unittest.mock import Mock

from wayland_popup import NotificationWidget


class _Evt:
    """Evento GDK mínimo: solo las coords que lee el routing."""

    def __init__(self, x, y):
        self.x, self.y = x, y


def _widget():
    """Widget sin display: justo los attrs que toca press/release."""
    w = NotificationWidget.__new__(NotificationWidget)
    w._close_rect = (280, 0, 360, 120)          # franja de 80px
    w._expand_rect = None
    w._action_rects = [(10, 60, 100, 88, "settings")]
    w._hover = True
    w._hover_close = False
    w._hover_action_idx = None
    w._pressed_close = False
    w._pressed_action_idx = None
    w._buttons_actionable = True
    w._on_click = None
    w._on_close = None
    w.queue_draw = lambda: None
    # GTK internals que el routing de leave/motion toca pero no son sujeto
    # del test (necesitan un Gtk.Window real).
    w._set_cursor = lambda hand: None
    w._resize_por_hover = lambda: None
    return w


# --- Franja/X: release-based ---

def test_press_en_franja_no_cierra_solo_marca_pressed():
    w = _widget()
    w._on_close = Mock()
    w._on_button_press(None, _Evt(320, 60))
    assert w._pressed_close is True, "el press marca el estado pressed"
    w._on_close.assert_not_called(), (
        "el cierre va al SOLTAR: en el press no se cierra nada"
    )


def test_release_dentro_de_la_franja_cierra():
    w = _widget()
    w._on_close = Mock()
    w._on_button_press(None, _Evt(320, 60))
    w._on_button_release(None, _Evt(320, 60))
    w._on_close.assert_called_once_with("user")
    assert w._pressed_close is False


def test_release_fuera_de_la_franja_cancela():
    """Presionar la X y arrastrar fuera antes de soltar NO cierra."""
    w = _widget()
    w._on_close = Mock()
    w._on_button_press(None, _Evt(320, 60))
    w._on_button_release(None, _Evt(10, 10))
    w._on_close.assert_not_called()
    assert w._pressed_close is False


# --- Botones: release-based + gate accionable ---

def test_boton_release_dentro_emite_su_key():
    w = _widget()
    w._on_click = Mock()
    w._on_button_press(None, _Evt(50, 70))
    w._on_click.assert_not_called(), "en el press no se emite nada"
    assert w._pressed_action_idx == 0
    w._on_button_release(None, _Evt(50, 70))
    w._on_click.assert_called_once_with("settings")
    assert w._pressed_action_idx is None


def test_boton_release_fuera_no_emite():
    w = _widget()
    w._on_click = Mock()
    w._on_button_press(None, _Evt(50, 70))
    w._on_button_release(None, _Evt(320, 60))   # soltó en la franja
    w._on_click.assert_not_called()
    assert w._pressed_action_idx is None


def test_boton_no_accionable_consume_sin_pressed_ni_emision():
    """Replay: botones renderizados por fidelidad — consumen el click (nada
    de default/URL fantasma por fall-through) pero sin pressed ni emisión."""
    w = _widget()
    w._buttons_actionable = False
    w._on_click = Mock()
    consumed = w._on_button_press(None, _Evt(50, 70))
    assert consumed is True, "el botón consume el evento aunque no ejecute"
    assert w._pressed_action_idx is None
    w._on_button_release(None, _Evt(50, 70))
    w._on_click.assert_not_called()


def test_leave_del_card_resetea_el_pressed():
    """El puntero que se va del card cancela la presión en curso."""
    w = _widget()
    w._on_close = Mock()
    w._on_button_press(None, _Evt(320, 60))
    w._on_leave(None, None)
    assert w._pressed_close is False
    w._on_button_release(None, _Evt(320, 60))
    w._on_close.assert_not_called(), (
        "la presión murió con el leave: el release posterior no cierra"
    )


# --- Cursor honesto (spec toast-acciones ADDED) ---

def _widget_cursor(on_click=None, buttons_actionable=True):
    """Widget con `_set_cursor` grabador: registro de los cursor pedidos."""
    w = _widget()
    w._on_click = on_click
    w._buttons_actionable = buttons_actionable
    w.cursor = []
    w._set_cursor = lambda hand: w.cursor.append(hand)
    w._cursor_hand = False
    return w


# Coordenadas del fixture: botón (10,60)-(100,88), franja (280,0)-(360,120).

def test_daemon_pointer_en_cuerpo_boton_y_franja():
    """Daemon: el click siempre tiene efecto (default, URL o cierre)."""
    w = _widget_cursor(on_click=Mock())
    assert w._cursor_por_posicion(50, 30) is True      # cuerpo
    assert w._cursor_por_posicion(50, 70) is True      # botón accionable
    assert w._cursor_por_posicion(320, 60) is True     # franja/X


def test_one_shot_sin_url_sin_pointer_en_todo_el_card():
    """One-shot sin URL (on_click None): ningún elemento promete click —
    salvo la franja/X, que SIEMPRE cierra (cierre manual)."""
    w = _widget_cursor(on_click=None)
    assert w._cursor_por_posicion(50, 30) is False     # cuerpo: nada que hacer
    assert w._cursor_por_posicion(50, 70) is False     # botón: sin efecto
    assert w._cursor_por_posicion(320, 60) is True     # X: cierre manual sí


def test_replay_pointer_en_cuerpo_default_en_botones():
    """Replay: la URL archivada hace el cuerpo clickeable; los botones
    reproducidos no ejecutan (sin sender) y no muestran pointer."""
    w = _widget_cursor(on_click=Mock(), buttons_actionable=False)
    assert w._cursor_por_posicion(50, 30) is True      # cuerpo con URL
    assert w._cursor_por_posicion(50, 70) is False     # botón sin sender
    assert w._cursor_por_posicion(320, 60) is True     # X: cierre manual


def test_on_enter_ya_resuelve_el_cursor_honesto():
    """El enter no pone hand a ciegas: pregunta por la posición de entrada
    y PISA un cursor hand previo si el cuerpo no tiene efecto."""
    w = _widget_cursor(on_click=None)
    w._cursor_hand = True                       # venía de un contexto hand
    w._on_enter(None, _Evt(50, 30))             # entra por el cuerpo muerto
    assert w.cursor == [False], "cuerpo sin efecto → cursor default"
