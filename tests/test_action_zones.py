"""
RED: zonas de interacción amplias (anti-misclick).

Especificación (Variante 1 aprobada, adaptada al stack cairo):

  - CERRAR: franja vertical derecha de 44px × altura del card, hover-only en
    persistentes (antes: pill 28×28 en la esquina). Click en CUALQUIER punto
    de la franja cierra (on_close) sin disparar on_click (que abriría el
    video/URL). El ancho de la franja se reclama SOLO con hover: la columna
    de texto del persistente pasa de 332 a 288 px (240 → 196 con avatar) y el
    texto re-wrappea, así nunca queda debajo del tinte. Sin hover la columna
    usa el ancho completo y la barra "Ver más" llega al pad derecho.
  - EXPANDIR: barra full-width inferior — TODO el ancho de la franja es
    clickeable (antes solo el pill), alto _BTN_H sube 20 → 28.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# wayland_popup PRIMERO: fija Gdk 3.0 antes de que el import suelto de Gdk
# cargue 4.0 y crashee (pitfall documentado en AGENTS.md).
import pytest

import wayland_popup as wp
from wayland_popup import NotificationWidget

LONG = "x" * 400
W = 360
PAD = 14
STRIP = 44


@pytest.fixture(autouse=True)
def _sin_iconos_resolvibles(monkeypatch):
    """Estos tests validan las ZONAS de interacción con texto a ancho completo
    (sin avatar). Con el lookup de iconos case-insensitive (fix Ticket avatar),
    "App" ahora resuelve el icono genérico "app" y el has_avatar encogería la
    columna: anclar la resolución a None deja los anchos de franja/barra como
    el único verificado, sin depender del tema instalado."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)


class _Ev:
    """Evento sintético con coordenadas de click."""
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _pixbuf_16():
    """Pixbuf 16×16 opaco — avatar sintético para fijar el ancho de columna."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    pb.fill(0x1E1E2EFF)
    return pb


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
    """CON hover, la barra "Ver más" termina ANTES de la franja de cierre
    (no se solapan; el click no es ambiguo)."""
    w, h = _draw_widget(persistent=True, hover=True, cuerpo=LONG)
    assert w._expand_rect is not None
    assert w._expand_rect[2] <= W - wp.NotificationWidget._CLOSE_STRIP_W


def test_expand_strip_is_full_width_without_hover():
    """SIN hover la franja no se dibuja y su ancho NO se reserva: la barra
    "Ver más" llega al pad derecho como en un toast estándar. (El espacio de
    la franja solo se reclama mientras el puntero está encima.)"""
    w, h = _draw_widget(persistent=True, hover=False, cuerpo=LONG)
    assert w._expand_rect is not None
    assert w._expand_rect[2] >= W - PAD - 2, (
        "sin hover la franja no existe: la barra debe llegar al pad derecho, "
        "no terminar en %s" % (w._expand_rect[2],)
    )


# ---------------------------------------------------------------------------
# La franja solo existe con hover — y su ancho solo se reserva con hover
# ---------------------------------------------------------------------------

def test_persistent_text_width_reserves_strip_only_on_hover():
    """El wrap del persistente depende del hover: sin puntero la columna usa
    el ancho completo (332); con hover cede los 44px de la franja (288) y el
    mismo texto envuelve a más líneas → card más alta (visible en expandido;
    colapsado el cap de 3 líneas iguala ambas)."""
    assert wp._count_body_lines(LONG, wp._TEXT_COL_W - STRIP, 14) > \
        wp._count_body_lines(LONG, wp._TEXT_COL_W, 14), (
        "el wrap a 44px menos debe dar más líneas"
    )
    w = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4", persistent=True,
    )
    w._expanded = True
    w._hover = False
    assert w._eff_text_width() == wp._CARD_WIDTH - 2 * PAD
    h_sin_hover = w.desired_height()
    h_esperado_sin_hover = wp.WaylandPopup.calc_card_height(
        "App", LONG, "", text_width=wp._CARD_WIDTH - 2 * PAD, expanded=True,
        font_scale=w._font_scale, has_avatar=False,
    )
    assert h_sin_hover == h_esperado_sin_hover, (
        "sin hover el persistente debe wrappear a ancho completo"
    )

    w._hover = True
    h_con_hover = w.desired_height()
    assert h_con_hover > h_sin_hover, (
        "con hover el persistente debe reservar el ancho de la franja en el wrap"
    )


def test_eff_text_width_shrinks_for_persistent():
    """_eff_text_width (medición de desired_height) refleja el hover.

    Sin avatar: 332 px sin hover, 288 px con hover (332 − 44 de la franja).
    Con avatar: 240 px sin hover, 196 px con hover."""
    base = wp._CARD_WIDTH - 14 - 14
    strip = wp.NotificationWidget._CLOSE_STRIP_W
    assert (base, base - strip) == (332, 288), (
        "las columnas del contrato son 332 sin hover y 288 con hover"
    )

    w = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4", persistent=True,
    )
    w._hover = False
    assert w._eff_text_width() == base, (
        "sin hover el persistente usa el ancho completo: los 44px de la franja "
        "no se reservan mientras no se dibuje"
    )
    w._hover = True
    assert w._eff_text_width() == base - strip

    # Con avatar la columna es 240 sin hover y 196 con hover.
    w._avatar_pb = _pixbuf_16()
    w._hover = False
    assert w._eff_text_width() == 240
    w._hover = True
    assert w._eff_text_width() == 196

    # No persistente: la franja nunca se dibuja → jamás se reserva su ancho.
    w2 = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4", persistent=False,
    )
    w2._hover = True
    assert w2._eff_text_width() == base
