"""
RED: la franja de descarte + X son HOVER-ONLY en los toasts persistentes.

El gate de dibujado ya era hover-dependiente, pero el ancho de la franja
también se reservaba de forma permanente: los persistentes wrappeaban a
288 px aunque la franja no estuviera en pantalla. El contrato nuevo:

  - SIN puntero encima: el persistente se dibuja IDÉNTICO a un toast no
    persistente (cero píxeles de tinte y cero píxeles de X). Su columna de
    texto usa el ancho completo (332 px, o 240 con avatar).
  - CON puntero encima: la franja reclama sus 44 px derechos, el texto
    re-wrappea a la columna reducida (288/196) y la X aparece centrada.

Los tests son DIFERENCIALES (persistente vs. no persistente con el mismo
cuerpo): así detectan cualquier píxel de franja aunque el tinte se solape
con el fondo del card, en vez de depender de un color exacto.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# wayland_popup PRIMERO: fija Gdk 3.0 (pitfall de AGENTS.md).
import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import alloc_and_draw, surface_pixels

W = wp._CARD_WIDTH              # 360
STRIP = NotificationWidget._CLOSE_STRIP_W   # 44
SHORT = "Una linea corta que no re-wrappea."
LONG = "Parrafo largo que se re-wrappea al cambiar el ancho de la columna " \
       "de texto del card y por lo tanto ocupa varias lineas al ancho completo."


def _sin_iconos_resolvibles(monkeypatch):
    """Texto a ancho completo (sin avatar): los anchos de columna son los
    únicos verificados, sin depender de los iconos del tema instalados."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)


def _render(cuerpo, persistent, hover, monkeypatch, expanded=False):
    """Píxeles (R,G,B,A) del render headless del widget persistente o no."""
    _sin_iconos_resolvibles(monkeypatch)
    w = NotificationWidget(
        "App", "", "Titulo", cuerpo, None, None, "#80cbc4",
        on_click=lambda: None, on_close=lambda: None,
        persistent=persistent, hide_title=False,
    )
    w._expanded = expanded
    w._hover = hover
    h = w.desired_height()
    surf = alloc_and_draw(w, W, h, hover=hover)
    return w, h, surface_pixels(surf)


def _region(pixels, x0, x1, y0=0, y1=None):
    """Sub-rectángulo de la grilla de píxeles, como tupla plana."""
    y1 = len(pixels) if y1 is None else y1
    return tuple(pixels[y][x] for y in range(y0, y1) for x in range(x0, x1))


def _difieren(a, b):
    """Píxeles (x, y) donde dos renders no coinciden."""
    return [(x, y)
            for y in range(min(len(a), len(b)))
            for x in range(min(len(a[y]), len(b[y])))
            if a[y][x] != b[y][x]]


# ---------------------------------------------------------------------------
# Sin hover: cero píxeles de franja
# ---------------------------------------------------------------------------

def test_sin_hover_el_persistente_no_dibuja_franja(monkeypatch):
    """Sin puntero encima, el persistente es IDÉNTICO píxel a píxel a un
    toast no persistente: cero tinte, cero X en los 44 px derechos."""
    _, _, px_persist = _render(SHORT, True, False, monkeypatch)
    _, _, px_std = _render(SHORT, False, False, monkeypatch)
    assert _region(px_persist, W - STRIP, W) == _region(px_std, W - STRIP, W), (
        "sin hover el persistente dibuja la franja: el tinte/X no debe "
        "aparecer si el puntero no está sobre el card"
    )


def test_sin_hover_no_hay_pixeles_rosa_de_la_x(monkeypatch):
    """El rosa #f38ba8 de la X (0.953, 0.482, 0.659) no aparece en ningún
    píxel del card sin hover."""
    _, _, px = _render(LONG, True, False, monkeypatch)
    for y, row in enumerate(px):
        for x, (r, g, b, a) in enumerate(row):
            assert not _is_x_rosa(r, g, b, a), (
                "píxel de la X en (%d,%d) sin hover: la franja debe ser "
                "invisible sin puntero encima" % (x, y)
            )


# ---------------------------------------------------------------------------
# Con hover: la franja reclama exactamente sus 44 px
# ---------------------------------------------------------------------------

def test_con_hover_la_franja_aparece(monkeypatch):
    """Con puntero encima la franja se dibuja en los 44 px del borde derecho
    (y es lo único que cambia respecto del card sin franja)."""
    _, _, px_persist = _render(SHORT, True, True, monkeypatch)
    _, _, px_std = _render(SHORT, False, True, monkeypatch)
    diff = _difieren(_region(px_persist, W - STRIP, W),
                     _region(px_std, W - STRIP, W))
    assert diff, "con hover el persistente debe dibujar el tinte de la franja"


def test_la_franja_ocupa_exactamente_44px(monkeypatch):
    """El tinte invade los 44 px de la franja y NADA más: con un cuerpo que no
    re-wrappea, el resto del card es idéntico píxel a píxel al de un toast sin
    franja (la franja no se "come" contenido colindante)."""
    _, _, px_persist = _render(SHORT, True, True, monkeypatch)
    _, _, px_std = _render(SHORT, False, True, monkeypatch)
    fuera = _difieren(_region(px_persist, 0, W - STRIP),
                      _region(px_std, 0, W - STRIP))
    assert not fuera, (
        "con hover, fuera de los %d px de la franja el card debe ser idéntico "
        "al de un toast sin franja; difieren %d px (ej. %s)"
        % (STRIP, len(fuera), fuera[:5])
    )


def test_con_hover_hay_pixeles_rosa_de_la_x(monkeypatch):
    """La X (rosa #f38ba8) aparece centrada en la franja."""
    _, _, px = _render(LONG, True, True, monkeypatch)
    rosa = [(x, y) for y, row in enumerate(px)
            for x, (r, g, b, a) in enumerate(row)
            if _is_x_rosa(r, g, b, a)]
    assert len(rosa) >= 8, (
        "con hover la X debe dibujar sus trazos en la franja; encontrados %d "
        "píxeles rosa" % len(rosa)
    )
    # La X vive DENTRO de la franja (no en el cuerpo del card).
    assert all(x >= W - STRIP for x, _ in rosa), (
        "los píxeles de la X deben caer dentro de los %d px de la franja" % STRIP
    )


def test_no_persistente_no_dibuja_franja_con_hover(monkeypatch):
    """Los toasts con auto-expiración nunca dibujan franja ni X, con o sin
    hover (contraste directo con el caso persistente).

    No se compara contra el render sin hover porque el hover aclara el fondo
    del card (feedback "estás sobre esto", 0.85 → 0.92 de alpha): lo que se
    exige es que no aparezca ni un píxel de la X en el borde derecho."""
    _, _, px = _render(LONG, False, True, monkeypatch)
    rosa = [(x, y) for y in range(len(px))
            for x in range(W - STRIP, W)
            if _is_x_rosa(*px[y][x])]
    assert not rosa, (
        "un toast no persistente nunca dibuja la X; píxeles rosa en %s" % rosa[:5]
    )


# ---------------------------------------------------------------------------
# Re-wrap dinámico: la franja nunca pisa texto
# ---------------------------------------------------------------------------

def test_con_hover_el_texto_re_wrappea_a_288(monkeypatch):
    """El re-wrap es real: un body que cabía en N líneas a 332 px necesita más
    líneas a 288 px, y el texto dibujado cambia de ancho."""
    w_sin, h_sin, _ = _render(LONG, True, False, monkeypatch, expanded=True)
    w_con, h_con, _ = _render(LONG, True, True, monkeypatch, expanded=True)
    assert w_sin._eff_text_width() == 332 and w_con._eff_text_width() == 288, (
        "las columnas del contrato: 332 sin hover, 288 con hover"
    )
    assert h_con > h_sin, (
        "el re-wrap a 288 px debe cambiar la altura requerida del card "
        "(expandido: %s → %s)" % (h_sin, h_con)
    )


# ---------------------------------------------------------------------------
# Transición de altura al entrar/salir el hover
# ---------------------------------------------------------------------------

def _con_resize(cuerpo, expanded=True):
    """Widget persistente que emula la vía de redimensionado real.

    `on_resize` registra el alto pedido y actualiza el size request, igual que
    hace `WaylandPopup._resize_card` — así el size request del widget es la
    altura que la window tiene en pantalla (la referencia para detectar que el
    alto cambió)."""
    pedidas = []
    w = NotificationWidget(
        "App", "", "Titulo", cuerpo, None, None, "#80cbc4",
        on_click=lambda: None, on_resize=None, persistent=True,
    )

    def _resize(h):
        pedidas.append(h)
        w.set_size_request(W, h)

    w._on_resize = _resize
    w._expanded = expanded
    w.set_size_request(W, w.desired_height())   # lo que hace _build_ui
    return w, pedidas


def test_hover_cambia_el_alto_por_la_via_de_resize(monkeypatch):
    """Entrar al hover re-wrappea a 288 px y, si el alto cambia, se pide el
    redimensionado por la vía existente (la de toggle_expanded)."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)
    w, pedidas = _con_resize(LONG)
    h_sin = w.get_size_request()[1]

    w._on_enter(w, None)
    assert pedidas, "entrar al hover debe pedir el resize si el alto cambió"
    h_con = pedidas[-1]
    assert h_con > h_sin, (
        "el re-wrap a 288 px debe agrandar el card (expandido: %s → %s)"
        % (h_sin, h_con)
    )

    w._on_leave(w, None)
    assert len(pedidas) == 2, "salir del hover debe pedir volver al alto anterior"
    assert pedidas[-1] == h_sin, (
        "al salir del hover el card debe volver EXACTAMENTE a su alto (%s), "
        "no a %s" % (h_sin, pedidas[-1])
    )


def test_hover_sin_cambio_de_alto_no_redimensiona(monkeypatch):
    """Un body que no cambia de líneas al re-wrappear NO dispara resize (evita
    loops de hover en el card más común: el cuerpo corto)."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)
    w, pedidas = _con_resize(SHORT, expanded=False)
    w._on_enter(w, None)
    w._on_leave(w, None)
    assert not pedidas, (
        "sin cambio de alto no debe haber resize: se piden %s" % (pedidas,)
    )


def test_hover_no_persistente_no_redimensiona(monkeypatch):
    """Los toasts con auto-expiración nunca cambian de columna: el hover no
    puede pedir un resize."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)
    pedidas = []
    w = NotificationWidget(
        "App", "", "Titulo", LONG, None, None, "#80cbc4",
        on_click=lambda: None, on_resize=pedidas.append, persistent=False,
    )
    w.set_size_request(W, w.desired_height())
    w._on_enter(w, None)
    w._on_leave(w, None)
    assert not pedidas, "sin franja que reclame ancho, el hover no redimensiona"


def test_hover_repetido_converge(monkeypatch):
    """Entrar y salir varias veces seguidas converge siempre al mismo estado:
    el alto de la ventana y el de la columna no derivan (no hay oscilación)."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)
    w, pedidas = _con_resize(LONG)
    h_sin = w.get_size_request()[1]
    for _ in range(4):
        w._on_enter(w, None)
        h_con = w.get_size_request()[1]
        assert h_con == pedidas[-1] and h_con > h_sin
        w._on_leave(w, None)
        assert w.get_size_request()[1] == h_sin, (
            "el ciclo hover debe volver siempre al alto inicial, no derivar"
        )


def test_el_card_resizeado_no_solapa_bloques(monkeypatch):
    """Con el alto del hover, ningún bloque del card se solapa ni desborda: la
    barra "Ver más" sigue anclada al padding inferior (mismo invariante que
    test_layout_consistency, evaluado en el estado de hover)."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop", lambda app_name, size=80, mode="cover": None)
    w, _ = _con_resize(LONG)
    w._hover = True
    h = w.desired_height()
    alloc_and_draw(w, W, h, hover=True)
    assert w._expand_rect is not None, "con body largo debe haber barra Ver más"
    assert h - wp._PAD - w._expand_rect[3] == 0, (
        "con hover la barra queda %d px sobre el padding inferior"
        % (h - wp._PAD - w._expand_rect[3])
    )
    assert w._expand_rect[2] <= W - STRIP, (
        "la barra no puede invadir la franja de 44 px"
    )


def _is_x_rosa(r, g, b, a):
    """Píxel del trazo de la X (#f38ba8 compuesto sobre el tinte).

    El trazo se dibuja con alpha 0.95 sobre el fondo del card, así que se
    busca el rosa dominio (rojo alto, azul > verde, opaco) y no el valor
    exacto del source."""
    return a > 200 and r > 180 and b > g + 40 and b < 220
