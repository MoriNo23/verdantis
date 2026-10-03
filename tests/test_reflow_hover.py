"""
RED: el hover se resetea de forma confiable cuando la ventana se MUEVE bajo un
puntero quieto (spec toast-franja-descarte: "El estado de hover se resetea de
forma confiable").

Bug real (verificado en vivo con el daemon, task 6.2): al cerrarse un toast de la
pila, los de abajo reflowean (suben) vía `set_stack_margin`. KWin **no** entrega
`leave-notify` cuando la surface se aparta del puntero quieto, así que el card
quedaba con `_hover=True` stale: la franja y la X seguían dibujadas con el
puntero AFUERA del card (X "pegada").

El contrato (ambas direcciones, según el spec):
  - el puntero quedó FUERA de la nueva área → la franja desaparece;
  - el puntero sigue DENTRO → la franja se mantiene (no debe quedar oculta
    teniéndola).
"""


# wayland_popup PRIMERO: fija Gdk 3.0 (pitfall de AGENTS.md).
import wayland_popup as wp
from wayland_popup import NotificationWidget, WaylandPopup

W = wp._CARD_WIDTH
LONG = ("Cuerpo largo para que el re-wrap a 288 px cambie el número de líneas "
        "y con él el alto del card, que es lo que dispara el resize.")


def _widget(persistent=True):
    w = NotificationWidget(
        "App", "", "Titulo", LONG, None, None, "#80cbc4",
        on_click=lambda: None, on_close=lambda: None, persistent=persistent,
    )
    w._expanded = True
    w.set_size_request(W, w.desired_height())
    return w


def _fix_puntero(w, x, y):
    """Simula el puntero en (x, y) dentro de la ventana del card."""
    w._puntero_en_card = lambda: (True, x, y)


def _fix_puntero_fuera(w):
    """Simula el puntero consultado y FUERA del card."""
    w._puntero_en_card = lambda: (False, 0, 0)


# ── El puntero quedó fuera tras el reflow → la franja se va ────────────────

def test_reflow_fuera_del_puntero_resetea_la_franja():
    """El card baja/reflowea y el puntero (quieto) queda fuera de su nueva área:
    la franja desaparece y, si el wrap cambia de líneas, el alto vuelve al de
    sin hover."""
    w = _widget()
    w._hover = True                       # estaba hoverado antes del reflow
    alto_hover = w.get_size_request()[1]
    alto_sin_hover = w.desired_height()   # con _hover aún True → es el de hover
    w._hover = False
    alto_solo_sin = w.desired_height()
    w._hover = True
    # El puntero estaba cerca del BORDE INFERIOR del card; el card sube 187 px.
    _fix_puntero(w, x=200, y=alto_hover - 4)
    w._sincronizar_hover_tras_desplazar(dy=-187)
    assert w._hover is False, (
        "el card se movió y el puntero quedó fuera: la franja/X no debe "
        "quedarse pegada (spec: el estado se resetea si el puntero sale)"
    )
    assert w._close_rect is None
    # El alto converge al valor sin hover (si el wrap cambió de líneas, además
    # se pidió el resize por la vía existente).
    assert w.desired_height() == alto_solo_sin, (
        "tras perder el hover el card vuelve a su alto/columna sin franja"
    )
    if alto_solo_sin != alto_hover:
        assert w.get_size_request()[1] == alto_solo_sin, (
            "el cambio de alto debe pasar por la vía de resize existente"
        )


def test_reflow_fuera_dibuja_sin_franja():
    """Tras el reseteo, el render no tiene ni un píxel de la X."""
    from render_helpers import alloc_and_draw, surface_pixels
    w = _widget()
    w._hover = True
    alto_hover = w.get_size_request()[1]
    _fix_puntero(w, x=200, y=alto_hover - 4)
    w._sincronizar_hover_tras_desplazar(dy=-187)
    px = surface_pixels(alloc_and_draw(w, W, w.get_size_request()[1], hover=False))
    rosa = [(x, y) for y, row in enumerate(px) for x, p in enumerate(row)
            if p[0] > 225 and 110 < p[1] < 175 and 140 < p[2] < 205]
    assert not rosa, (
        "tras perder el hover quedan píxeles de la X en %s" % rosa[:5]
    )


# ── El puntero sigue dentro → la franja se mantiene ────────────────────────

def test_reflow_dentro_del_puntero_mantiene_la_franja():
    """El card se mueve pero el puntero sigue dentro de su nueva área: la franja
    NO debe desaparecer (spec: ni quede oculta teniéndolo)."""
    w = _widget()
    w._hover = True
    alto = w.get_size_request()[1]
    # Puntero a 10 px del borde inferior; el card sube solo 4 px → el puntero
    # sigue dentro (queda a 14 px del borde nuevo).
    _fix_puntero(w, x=200, y=alto - 10)
    w._sincronizar_hover_tras_desplazar(dy=-4)
    assert w._hover is True, (
        "el puntero sigue dentro del card tras un desplazamiento menor: la "
        "franja debe mantenerse"
    )


def test_reflow_sin_puntero_conocido_no_toca_el_estado():
    """Si no se puede consultar el puntero (sin seat/ventana → `None`), no se
    inventa un cambio de estado: se deja el hover como estaba."""
    w = _widget()
    w._hover = True
    w._puntero_en_card = lambda: None
    w._sincronizar_hover_tras_desplazar(dy=-187)
    assert w._hover is True, (
        "sin posición de puntero conocida no se debe resetear a ciegas"
    )


def test_reflow_puntero_fuera_consultado_resetea():
    """`_puntero_en_card` distingue "fuera" (consultado) de "no consultable":
    con `(False, 0, 0)` el puntero se sabe fuera → el hover se resetea."""
    w = _widget()
    w._hover = True
    _fix_puntero_fuera(w)
    w._sincronizar_hover_tras_desplazar(dy=0)
    assert w._hover is False, (
        "un puntero consultado y fuera del card debe resetear el hover, aunque "
        "el desplazamiento sea 0"
    )


def test_puntero_en_card_usa_la_api_real():
    """Guarda de API: `_puntero_en_card` debe apoyarse en
    `Gdk.Window.get_device_position`, que es la vía que funciona bajo Wayland
    (las GdkWindow de layer-shell no tienen `get_origin`/`translate_coordinates`
    fiable). El método debe invocarse SOBRE LA WINDOW (`win.get_device_position`),
    no sobre el device (`pointer.get_device_position`, que no existe y hacía que
    el fix quedara mudo devolviendo el fallback)."""
    import inspect
    src = inspect.getsource(wp.NotificationWidget._puntero_en_card)
    assert "win.get_device_position(pointer)" in src, (
        "el puntero debe consultarse con win.get_device_position(pointer) "
        "(Gdk.Window), la única vía fiable bajo Wayland"
    )
    assert "pointer.get_device_position" not in src, (
        "get_device_position es método de Gdk.Window, no de Gdk.Device: "
        "llamarlo sobre el device rompe el fix en silencio"
    )
    assert "translate_coordinates" not in src, (
        "translate_coordinates/get_origin no son fiables en GdkWindow de "
        "layer-shell bajo Wayland (devuelven 0,0 o no existen)"
    )


def test_reflow_no_persistente_deja_el_estado():
    """Un no persistente nunca dibuja franja; el helper no debe alterarlo."""
    w = _widget(persistent=False)
    w._hover = True
    _fix_puntero(w, x=200, y=10)
    w._sincronizar_hover_tras_desplazar(dy=40)
    assert w._strip_w() == 0


# ── La pila llama al reseteo al reflowear ─────────────────────────────────

def test_apply_margins_sincroniza_el_hover():
    """`set_stack_margin` (el reflow de la pila) debe re-sincronizar el hover
    del card: es el único punto donde la ventana se mueve por reflow."""
    import inspect
    src = inspect.getsource(WaylandPopup._apply_margins)
    assert "_sincronizar_hover_tras_desplazar" in src, (
        "el reflow de la pila debe re-sincronizar el hover del card: KWin no "
        "entrega leave-notify cuando la ventana se aparta del puntero quieto"
    )
