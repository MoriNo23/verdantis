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

import pytest

import wayland_popup as wp

LONG = "x" * 400
W = 360


@pytest.fixture(autouse=True)
def _sin_iconos_resolvibles(monkeypatch):
    """Estos tests validan el layout del path con y sin slot resuelto. Con el
    lookup de iconos case-insensitive, "App"/"Brave" resuelven iconos de tema
    ("app"/"brave") y la procedencia del slot cambiaría el stack: anclar la
    resolución a None deja el invariante (barra al padding) como el único
    verificado, sin depender del tema hicolor instalado."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)


def _rows(app_name, hide_title, con_slot):
    """`_rows_above_body` tolerant a la firma.

    El contrato nuevo elimina el tercer argumento (`has_avatar`: con el slot
    siempre presente ya no hay dos variantes de stack). Se pasa si la firma lo
    acepta y se reintenta sin él si no, para que el rojo de los asserts sea el
    del VALOR esperado y no un TypeError de una firma que cambió. Un TypeError
    que no sea de firma se propaga (el helper no debe tapar bugs del test)."""
    try:
        return wp._rows_above_body(app_name, hide_title, con_slot)
    except TypeError as e:
        if "argument" not in str(e):
            raise
        return wp._rows_above_body(app_name, hide_title)


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

    CONTRATO NUEVO (spec `toast-imagen-izquierda`, D4): con el slot siempre
    presente el respiro del HR (18 px) desaparece para TODOS los toasts — la
    distancia app→título/body es la misma con imagen real, con icono de app o
    con placeholder. Antes el +18 solo se aplicaba al path sin slot y el
    `has_avatar` condicional partía la fuente del stack en dos.

    El tercer argumento histórico (`has_avatar`) ya no pertenece al contrato,
    por eso `_rows` reintenta sin él: así el rojo de este test es el del VALOR
    y no el de una firma que cambió."""
    assert _rows("App", False, False) == 20 + 22
    assert _rows("App", False, True) == 20 + 22      # slot resuelto: sin HR
    assert _rows("App", True, False) == 20           # título oculto
    assert _rows("", False, False) == 22             # SIN app
    assert _rows("", True, False) == 0


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
