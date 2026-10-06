"""
RED: el slot del logo de 16 px nunca queda vacío (spec toast-iconos-app).

Hoy, si ninguna fuente resuelve el icono (sin archivo, sin `.desktop` exacto y
sin entrada en el tema), el widget queda con `_app_icon_pb = None` y la fila de
app se dibuja sin logo: el espacio del slot se "?come" y la fila pierde su
punto de anclaje visual.

Contrato:
  - cadena entera fallida → pixbuf 16×16 de PLACEHOLDER (nunca None)
  - layout de fila ESTABLE: el texto de la app arranca en el mismo
    desplazamiento horizontal con logo resuelto que con placeholder
    (offset constante de 20 px tras el slot de 16).
"""


# wayland_popup PRIMERO: fija Gdk 3.0 (pitfall de AGENTS.md).
import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import alloc_and_draw, surface_pixels

W = wp._CARD_WIDTH       # 360
SLOT = 16                # slot del logo de la fila de app
OFFSET = 20              # desplazamiento del texto tras el slot
# Slot de imagen izquierda (contrato nuevo: 80 px) + su gap: la región de
# comparación del texto tiene que empezar DESPUÉS de él, porque con placeholder
# pinta un square gris y con logo resuelto otro color.
SLOT_80 = 80
GAP = 12


def _pixbuf(w, h, rgba):
    from gi.repository import GLib
    return wp.GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(rgba) * (w * h)),
        wp.GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)


def _construir(monkeypatch, app_name="App", app_icon="", theme_icon=None):
    """Widget headless con la cadena de iconos simulada.

    `theme_icon=None` anula toda la resolución (ni .desktop ni tema): ese es el
    caso "sender desconocido" que debe caer al placeholder. Con un pixbuf, el
    tema lo devuelve solo para el slot de 16 px (si no, el fallback de la imagen
    también lo resolvería y cambiaría el ancho de la columna, que es otra cosa)."""
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop",
        lambda app_name, size=80, mode="cover": None)
    if theme_icon is None:
        monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)
    else:
        monkeypatch.setattr(
            wp, "_icon_from_theme",
            lambda name, size=16: theme_icon if size == 16 else None)
    return NotificationWidget(
        app_name, app_icon, "Titulo", "cuerpo", None, None, "#80cbc4",
        on_click=lambda key=None: None,
    )


# ---------------------------------------------------------------------------
# El slot nunca queda vacío
# ---------------------------------------------------------------------------

def test_slot_del_logo_nunca_queda_vacio(monkeypatch):
    """Cadena entera fallida → hay un pixbuf 16×16 de placeholder, no None."""
    w = _construir(monkeypatch, app_name="App", app_icon="")
    assert w._app_icon_pb is not None, (
        "sin ninguna fuente resoluble el slot del logo queda vacío: debe "
        "sintetizarse un placeholder"
    )
    assert (w._app_icon_pb.get_width(), w._app_icon_pb.get_height()) == (SLOT, SLOT), (
        "el placeholder debe ocupar el slot exacto del logo (16×16)"
    )


def test_placeholder_lleva_la_inicial_de_la_app(monkeypatch):
    """El placeholder muestra la inicial del nombre de la app: es un square
    surface con un glifo, no un rectángulo vacío."""
    from render_helpers import pixbuf_pixels
    w = _construir(monkeypatch, app_name="Netflix", app_icon="")
    px = pixbuf_pixels(w._app_icon_pb)
    distintos = {p for fila in px for p in fila if p[3] > 128}
    assert len(distintos) >= 2, (
        "el placeholder debe dibujar la inicial encima del square (al menos dos "
        "colores opacos); colores opacos hallados: %d" % len(distintos)
    )
    # La inicial es lo que da el contraste claro (#A6ADC8) sobre el square
    # (#313244): debe haber un píxel claramente más claro que el fondo.
    r, g, b, a = max(distintos, key=lambda p: p[0] + p[1] + p[2])
    assert (r + g + b) / 3 > 120, (
        "no se dibujó la inicial en claro: el placeholder es un square plano "
        "(pixel más claro = %s)" % ((r, g, b, a),)
    )


def test_placeholder_es_opaco_en_el_slot(monkeypatch):
    """El square del placeholder es opaco (no un recuadro transparente que se
    vería como el fondo del card). Las esquinas redondeadas sí son
    transparentes: se verifica el interior."""
    from render_helpers import pixbuf_pixels
    w = _construir(monkeypatch, app_name="App", app_icon="")
    px = pixbuf_pixels(w._app_icon_pb)
    centro = SLOT // 2
    assert all(px[y][centro][3] > 128 for y in range(SLOT)), (
        "el interior del placeholder debe ser opaco (square redondeado)"
    )


# ---------------------------------------------------------------------------
# Layout de fila estable
# ---------------------------------------------------------------------------

def test_offset_del_texto_constante(monkeypatch):
    """Con logo resuelto y con placeholder, el texto de la app arranca en el
    mismo x (offset constante). El label es el mismo en ambos casos: el texto
    dibujado tras el slot debe ser idéntico píxel a píxel."""
    logo = _pixbuf(SLOT, SLOT, (0xFF, 0x00, 0x00, 0xFF))  # rojo opaco
    w_ph = _construir(monkeypatch, app_name="App", app_icon="", theme_icon=None)
    w_logo = _construir(monkeypatch, app_name="App", app_icon="x", theme_icon=logo)

    assert w_ph._app_icon_pb is not None and w_logo._app_icon_pb is not None
    # Todo lo que está a la derecha del slot debe ser idéntico: el texto de la
    # app no se desplaza ni un px por tener placeholder en vez de logo.
    strip_ph = _region_texto(w_ph)
    strip_logo = _region_texto(w_logo)
    assert strip_ph == strip_logo, (
        "el texto de la app se movió con placeholder vs logo resuelto: la fila "
        "debe tener layout estable"
    )


def test_draw_usa_offset_constante(monkeypatch):
    """El dibujado no debe condicionar el offset a la existencia del logo: con
    el placeholder siempre presente el offset es el mismo en todos los casos.

    Desde `bajar-complejidad-draw` el texto de app se dibuja en
    `_draw_text_passes`, no en `_draw` (que quedó como orquestador); los
    marcadores se buscan en el source de toda la clase."""
    import inspect
    src = inspect.getsource(NotificationWidget)
    assert "20 if self._app_icon_pb else 0" not in src, (
        "el offset del texto de app sigue siendo condicional: con el "
        "placeholder debe ser una constante (layout estable)"
    )
    assert "text_col_x + %d" % OFFSET in src, (
        "el texto de la app debe dibujarse en text_col_x + %d (constante)" % OFFSET
    )


def test_fila_con_placeholder_dibuja_slot_y_texto(monkeypatch):
    """Con placeholder, la fila dibuja el slot y el texto (offset +20)."""
    w = _construir(monkeypatch, app_name="App", app_icon="")
    px = _render(w)
    # El square del placeholder aparece en el slot del texto (x = _PAD).
    assert any(px[y][wp._PAD][3] > 128 for y in range(wp._PAD, wp._PAD + 10)), (
        "el slot del logo no se dibujó (placeholder ausente en el render)"
    )


# ── helpers ────────────────────────────────────────────────────────────────

def _render(w):
    surf = alloc_and_draw(w, W, w.desired_height())
    return surface_pixels(surf)


def _region_texto(w):
    """Píxeles desde donde arranca el texto de la app hasta el borde derecho.

    Empieza DESPUÉS de todo lo que puede cambiar entre los dos casos: el logo
    de 16 px de la fila (con su hueco) y, desde el contrato nuevo, el slot de
    imagen izquierda de 80 px + su gap — que con placeholder pinta un square
    gris y con logo resuelto un icono de otro color. Lo que sigue a la derecha
    es el texto, y debe ser idéntico píxel a píxel en ambos casos."""
    px = _render(w)
    x0 = wp._PAD + SLOT_80 + GAP + OFFSET
    return tuple(px[y][x] for y in range(len(px)) for x in range(x0, W))
