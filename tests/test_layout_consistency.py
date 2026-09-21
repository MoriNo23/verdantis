"""
RED: una sola fuente de verdad para el layout de la card.

La auditoría encontró que `_draw`, `calc_card_height` y `_eff_text_width`
computaban el stack de la card cada uno por su lado y divergían en dos
puntos REALES (verificados con render antes de este fix):

1. El gap del botón (+8) se reserva en calc_card_height pero `_draw` nunca
   lo aplicaba entre body y barra: la barra "Ver más" flotaba 8px sobre el
   padding inferior.
2. El gap del HR (18px) se sumaba en `_draw` aunque NO hubiera app_name
   (el HR solo se dibuja con app_name): sin app_name el contenido
   DESBORDABA la card — btn bottom 148 en una card de H=132 → 30px
   recortados en pantalla.

Invariants de este test: el contenido ancla al padding inferior con
cualquier combinación de flags, y el stack vive en _rows_above_body.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

import wayland_popup as wp

LONG = "x" * 400
W = 360


@pytest.fixture(autouse=True)
def _sin_iconos_resolvibles(monkeypatch):
    """Estos tests validan el layout del path SIN avatar (texto a ancho
    completo). Con el lookup de iconos case-insensitive (fix Ticket avatar),
    "App"/"Brave" ahora resuelven iconos de tema ("app"/"brave") y el
    has_avatar cambiaría el stack: anclar la resolución a None deja el
    invariante (barra al padding) como el único verificado, sin depender
    del tema hicolor instalado."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80: None)


def _render(app_name, cuerpo=LONG, expanded=False, hide_title=False):
    from render_helpers import alloc_and_draw
    w = wp.NotificationWidget(app_name, "", "T", cuerpo, None, None,
                              "#80cbc4", hide_title=hide_title)
    w._expanded = expanded
    h = w.desired_height()
    alloc_and_draw(w, W, h)
    return w, h


def test_expand_bar_flush_with_bottom_padding():
    """Con overflow, la barra expandir ancla al padding inferior (H - pad)."""
    for app_name in ("App", ""):
        w, h = _render(app_name)
        assert w._expand_rect is not None
        gap = h - wp._PAD - w._expand_rect[3]
        assert gap == 0, (
            "app_name=%r: la barra flota %dpx sobre el padding "
            "(H=%s, btn_bottom=%s)" % (app_name, gap, h, w._expand_rect[3])
        )


def test_expand_bar_flush_when_expanded():
    """El invariant se mantiene con la card expandida."""
    for app_name in ("App", ""):
        w, h = _render(app_name, expanded=True)
        assert w._expand_rect is not None
        gap = h - wp._PAD - w._expand_rect[3]
        assert gap == 0, (
            "app_name=%r expandido: barra no anclada (H=%s, gap=%d)"
            % (app_name, h, gap)
        )


def test_expand_bar_flush_hide_title():
    """También con el título plegado (navegadores: hide_title)."""
    w, h = _render("Brave", hide_title=True)
    assert w._expand_rect is not None
    assert h - wp._PAD - w._expand_rect[3] == 0


def test_rows_above_body_single_source():
    """`_rows_above_body` es LA fuente del stack superior al body.

    Valores: app 20 + título 22 + HR 18 (el HR SOLO con app_name y sin
    avatar — sin app_name no hay HR que respire, el +18 fantasma era el
    bug del desborde)."""
    f = wp._rows_above_body
    assert f("App", False, False) == 20 + 22 + 18
    assert f("App", False, True) == 20 + 22          # avatar: sin HR
    assert f("App", True, False) == 20 + 18          # título oculto
    assert f("", False, False) == 22                 # SIN app: sin HR fantasma
    assert f("", True, False) == 0


def test_short_content_fits_card():
    """Texto corto: sin barra, sin desborde, la altura es la de calc
    (con el MISMO font_scale del widget — el runtime lo ajusta por
    resolución de pantalla)."""
    w, h = _render("App", cuerpo="hola")
    assert w._expand_rect is None
    # desired_height debe ser EXACTAMENTE calc_card_height con el mismo
    # font_scale del widget (el runtime lo ajusta por resolución).
    assert h == wp.WaylandPopup.calc_card_height(
        "App", "hola", "", font_scale=w._font_scale)
