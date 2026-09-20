"""
RED: zonas de interacción amplias (anti-misclick).

Especificación (Variante 1 aprobada, adaptada al stack cairo):

  - CERRAR: franja vertical derecha de 44px × altura del card, hover-only en
    persistentes (antes: pill 28×28 en la esquina). Click en CUALQUIER punto
    de la franja cierra (on_close) sin disparar on_click (que abriría el
    video/URL). El ancho de la franja está RESERVADO: la columna de texto
    de los persistentes es 44px más angosta (el texto nunca queda debajo).
  - EXPANDIR: barra full-width inferior — TODO el ancho de la franja es
    clickeable (antes solo el pill), alto _BTN_H sube 20 → 28.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# wayland_popup PRIMERO: fija Gdk 3.0 antes de que el import suelto de Gdk
# cargue 4.0 y crashee (pitfall documentado en AGENTS.md).
import wayland_popup as wp
from wayland_popup import NotificationWidget

LONG = "x" * 400
W = 360
PAD = 14
STRIP = 44


class _Ev:
    """Evento sintético con coordenadas de click."""
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _draw_widget(persistent=False, hover=False, cuerpo=LONG, expanded=False):
    """Render headless (helper compartido); devuelve (widget, altura)."""
    from render_helpers import alloc_and_draw
    w = NotificationWidget(
        "App", "", "T", cuerpo, None, None, "#80cbc4",
        on_click=lambda: None, on_close=lambda: None, persistent=persistent,
    )
    w._hover = hover
    w._expanded = expanded
    h = w.desired_height()
    alloc_and_draw(w, W, h)
    return w, h


# ---------------------------------------------------------------------------
# Franja de descarte (cerrar)
# ---------------------------------------------------------------------------

def test_close_rect_is_full_height_strip():
    """El rect de cierre es una franja vertical: 44px × alto del card."""
    w, h = _draw_widget(persistent=True, hover=True)
    rect = w._close_rect
    assert rect is not None, "hover en persistente debe computar _close_rect"
    x0, y0, x1, y1 = rect
    assert x1 - x0 == wp.NotificationWidget._CLOSE_STRIP_W, (
        f"ancho de franja debe ser {wp.NotificationWidget._CLOSE_STRIP_W}, no {x1 - x0}"
    )
    assert (x0, y0, x1, y1) == (W - wp.NotificationWidget._CLOSE_STRIP_W, 0, W, h), (
        "la franja debe ocupar el borde derecho completo, de arriba a abajo"
    )


def test_close_strip_covers_mid_card_click():
    """Un click a mitad de card en el borde derecho cae en la franja
    (antes con el pill 28×28 hubiera caído en el body → abrir el video)."""
    w, h = _draw_widget(persistent=True, hover=True)
    assert w._in_close_rect(W - 10, h / 2), "mid-card derecho debe ser cierre"
    assert w._in_close_rect(W - 2, h - 4), "borde inferior derecho debe ser cierre"
    assert w._in_close_rect(W - 40, 4), "top de la franja debe ser cierre"
    assert not w._in_close_rect(W - 50, h / 2), "fuera de la franja es body"
    assert not w._in_close_rect(W / 2, h / 2), "centro del card es body"


def test_click_on_strip_closes_without_opening():
    """Click en la franja: on_close SÍ, on_click NO (no abre el video)."""
    closed, clicked = [], []
    from render_helpers import alloc_and_draw
    w = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4",
        on_click=lambda: clicked.append(1),
        on_close=lambda: closed.append(1),
        persistent=True,
    )
    w._hover = True
    h = w.desired_height()
    alloc_and_draw(w, W, h)
    w._on_button_press(w, _Ev(W - 10, h / 2))
    assert closed and not clicked, (
        "click en la franja debe cerrar sin disparar on_click (misclick del video)"
    )


def test_non_persistent_has_no_close_rect():
    """Sin persistente no hay franja (igual que antes con la X)."""
    w, _ = _draw_widget(persistent=False, hover=True)
    assert w._close_rect is None


# ---------------------------------------------------------------------------
# Barra expandir full-width
# ---------------------------------------------------------------------------

def test_expand_rect_is_full_width():
    """El rect de expandir abarca TODO el ancho interior de la card."""
    w, h = _draw_widget(persistent=False, cuerpo=LONG)
    rect = w._expand_rect
    assert rect is not None
    x0, _, x1, _ = rect
    assert x0 <= PAD + 2, f"la barra debe arrancar en el pad izquierdo, no en {x0}"
    assert x1 >= W - PAD - 2, (
        f"la barra debe llegar al pad derecho (full-width), no terminar en {x1}"
    )


def test_expand_bar_height_is_28():
    """_BTN_H sube a 28px: target de toque más holgado (antes 20)."""
    assert wp.NotificationWidget._BTN_H == 28


def test_expand_strip_reserves_close_strip():
    """En persistentes la barra termina ANTES de la franja de cierre
    (no se solapan; el click no es ambiguo)."""
    w, h = _draw_widget(persistent=True, cuerpo=LONG)
    assert w._expand_rect is not None
    assert w._expand_rect[2] <= W - wp.NotificationWidget._CLOSE_STRIP_W


# ---------------------------------------------------------------------------
# Reserva de layout en persistentes
# ---------------------------------------------------------------------------

def test_persistent_reserves_strip_in_text_width():
    """calc_card_height(persistent=True): columna 44px más angosta →
    el mismo texto envuelve a más líneas → card más alta (visible en
    expandido; colapsado el cap de 3 líneas iguala ambas)."""
    assert wp._count_body_lines(LONG, wp._TEXT_COL_W - STRIP, 14) > \
        wp._count_body_lines(LONG, wp._TEXT_COL_W, 14), (
        "el wrap a 44px menos debe dar más líneas"
    )
    h_plain = wp.WaylandPopup.calc_card_height("App", LONG, "", expanded=True)
    h_persist = wp.WaylandPopup.calc_card_height(
        "App", LONG, "", expanded=True, persistent=True)
    assert h_persist > h_plain, (
        "el persistente debe reservar el ancho de la franja en el wrap"
    )


def test_eff_text_width_shrinks_for_persistent():
    """_eff_text_width (medición de desired_height) refleja la reserva."""
    w = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4", persistent=True,
    )
    base = wp._CARD_WIDTH - 14 - 14
    assert w._eff_text_width() == base - wp.NotificationWidget._CLOSE_STRIP_W
    w2 = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4", persistent=False,
    )
    assert w2._eff_text_width() == base
