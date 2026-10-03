"""
RED: contrato de la imagen izquierda y de la columna única
(spec `toast-imagen-izquierda` del change layout-imagen-izquierda).

Un test por escenario del spec, con el requisito citado en el mensaje del
assert para que el rojo sea auto-explicativo:

  - "La imagen izquierda siempre está presente": cadena imagen → icono de app →
    placeholder 80×80 con la inicial; el slot nunca desaparece ni queda vacío.
  - "El bloque de texto arranca al top de la imagen izquierda": el top de la
    fila de app coincide con el top del slot (±1 px) y la distancia app→título
    es la misma en todos los toasts (muere el respiro de 18 px).
  - "Columna de texto única": 240 px siempre (196 con franja en hover), el body
    wrappea igual con placeholder que con imagen y la barra "Ver más" aterriza
    en la misma posición.

Las mediciones son de RENDER headless (render_helpers), no de números internos:
se lee dónde aparece la tinta del slot, de la fila de app y del título. La
proveniencia del slot (imagen del sender vs logo de app vs placeholder) se lee
por COLOR, con iconos inyectados en rojo/verde sólidos.
"""
import os


# wayland_popup PRIMERO: fija Gdk 3.0 antes de que un import suelto de Gdk
# cargue 4.0 y crashee (pitfall documentado en AGENTS.md).
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import pytest

import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import alloc_and_draw, surface_pixels

W = wp._CARD_WIDTH              # 360
PAD = wp._PAD                   # 14
SLOT = 80                       # ancho del slot de imagen izquierda
# Gap slot → texto (12). Derivado de la columna única del contrato en vez de
# leer la constante de src: así el módulo sobrevive al rename
# `_AVATAR_GAP` → `_IMAGE_LEFT_GAP` sin un error de colección.
GAP = W - 2 * wp._PAD - wp._TEXT_COL_W - SLOT   # 360 - 28 - 240 - 80 = 12
TEXT_X = PAD + SLOT + GAP       # 106: columna de texto con el slot presente
# Columnas de escaneo del slot: su cuarto central. Se evita el borde izquierdo
# a propósito — en el contrato viejo (sin slot) el logo de 16 px vivía en
# PAD..PAD+16 y un escaneo desde PAD+4 lo confundía con el slot.
SLOT_X0 = PAD + SLOT // 4       # 34
SLOT_X1 = PAD + SLOT - SLOT // 4   # 74
LOGO_X0 = TEXT_X + 2            # centro del logo de 16 px de la fila de app
LOGO_X1 = TEXT_X + 14

LONG = "Cuerpo largo " * 40    # desborda el cap de 3 líneas → barra "Ver más"
SHORT = "hola"

SENDER_RED = (255, 0, 0)
APP_GREEN = (0, 255, 0)
# El placeholder (del slot y del logo de 16 px) lo sintetiza src con estos
# colores; el fondo de la card queda a >4 de ellos, así que tol=4 no lo
# confunde con tinta.
PLACEHOLDER_BG = (0x31, 0x32, 0x44)
PLACEHOLDER_FG = (0xA6, 0xAD, 0xC8)


# ── helpers ──────────────────────────────────────────────────────────────

def _slot_pb(w):
    """Pixbuf del slot de imagen izquierda, con el nombre viejo o el nuevo.

    C renombra `_avatar_pb` → `_image_left_pb` (task 4.1). Estos tests miden el
    CONTRATO (el slot existe, mide 80, y dibuja la tinta que corresponde), no el
    nombre del atributo, por eso aceptan los dos. El rename sigue forzado por
    test_image_left_fallback.py, que sí usa el nombre nuevo.
    """
    return getattr(w, "_image_left_pb", None) or getattr(w, "_avatar_pb", None)


def _cerca(rgb, objetivo, tol=4):
    return all(abs(a - b) <= tol for a, b in zip(rgb, objetivo))


def _ink_top(px, x0, x1, objetivo, tol=4, min_px=1):
    """Primera fila con `min_px` píxeles del color pedido dentro de [x0, x1).

    `min_px` > 1 descarta el fringe antialiased del texto, que sobre el fondo
    oscuro cruza en un par de píxeles sueltos los colores del placeholder; la
    fila 14 del slot de 80 px trae 8 px reales.
    """
    for y in range(len(px)):
        n = sum(1 for x in range(x0, x1) if _cerca(px[y][x][:3], objetivo, tol))
        if n >= min_px:
            return y
    return None


def _diff_top(a, b, x0, x1):
    """Primera fila donde dos renders difieren dentro de [x0, x1]."""
    for y in range(min(len(a), len(b))):
        for x in range(x0, x1):
            if a[y][x] != b[y][x]:
                return y
    return None


def _png(tmp_path, name, rgb=SENDER_RED, size=64):
    """PNG sólido del color dado (procedencia del slot, comprobada por píxel)."""
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
    pb.fill((rgb[0] << 24) | (rgb[1] << 16) | (rgb[2] << 8) | 0xFF)
    path = os.path.join(str(tmp_path), name)
    pb.savev(path, "png", [], [])
    return path


def _render(icon_path=None, cuerpo=SHORT, titulo="Titulo", app_name="App"):
    """Widget + altura + grilla de píxeles del render headless."""
    w = NotificationWidget(
        app_name, "", titulo, cuerpo, icon_path, None, "#80cbc4")
    h = w.desired_height()
    return w, h, surface_pixels(alloc_and_draw(w, W, h))


def _filas_above_body(icon_path=None, cuerpo=SHORT):
    """(widget, alto, píxeles, top_de_la_fila_de_app, top_del_título).

    Ambas medidas salen de un render DIFFERENCIAL contra el mismo toast sin logo
    de 16 px y sin título (`_app_icon_pb = None` + titulo vacío): lo único que
    cambia es esa caja del logo y esa línea, así que la primera fila que difiere
    en cada región es su tinta exacta. Es a prueba del color (el logo puede ser
    un icono inyectado o el placeholder) y no mueve la fila de app, a diferencia
    de usar `hide_title`, que cambia el stack entero y con él `ty`."""
    w, h, px = _render(icon_path=icon_path, cuerpo=cuerpo)
    ref = NotificationWidget("App", "", "", cuerpo, icon_path, None, "#80cbc4")
    ref._app_icon_pb = None
    px_ref = surface_pixels(alloc_and_draw(ref, W, ref.desired_height()))
    text_x = TEXT_X if _slot_pb(w) else PAD   # sin slot, el texto va al pad
    return (w, h, px,
            _diff_top(px, px_ref, text_x, text_x + 20),      # fila de app
            _diff_top(px, px_ref, text_x + 20, W - PAD))     # título


def _inyectar_desktop(app_name, icon_path):
    """Cache de .desktop con match EXACTO por Name (patrón de
    test_image_left_fallback): determinista, no depende de qué esté instalado."""
    d = os.path.dirname(icon_path)
    p = os.path.join(d, app_name.lower() + ".desktop")
    with open(p, "w") as f:
        f.write("[Desktop Entry]\nName={}\nIcon={}\nStartupWMClass=\n".format(
            app_name, icon_path))
    wp._desktop_cache = {
        app_name.lower(): [{
            "path": p, "Name": app_name, "Icon": icon_path,
            "StartupWMClass": "",
        }]
    }


@pytest.fixture(autouse=True)
def _sin_tema(monkeypatch):
    """El tema de iconos del equipo no puede decidir la procedencia del slot."""
    monkeypatch.setattr(wp, "_icon_from_theme", lambda name, size=16: None)


@pytest.fixture
def nada_resuelve(monkeypatch):
    """Ni .desktop ni tema: el último eslabón de la cadena es el placeholder."""
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop",
        lambda app_name, size=80, mode="cover": None)


@pytest.fixture
def _cache_limpio():
    yield
    wp._desktop_cache = None


# ── "La imagen izquierda siempre está presente" ───────────────────────────

def test_la_imagen_de_la_notificacion_gana_al_icono_de_app(tmp_path,
                                                           _cache_limpio):
    """Scenario "La imagen de la notificación gana siempre".

    Con imagen del sender (el icono del tab, rojo inyectado) Y app con .desktop
    resolvible (verde inyectado), el slot dibuja la imagen de la notificación.
    (El caso "sin imagen → .desktop" vive en test_image_left_fallback.)"""
    _inyectar_desktop("App", _png(tmp_path, "app.png", rgb=APP_GREEN))
    w, h, px = _render(icon_path=_png(tmp_path, "tab.png"))
    top = _ink_top(px, SLOT_X0, SLOT_X1, SENDER_RED, tol=8, min_px=6)
    assert top is not None and abs(top - PAD) <= 2, (
        "spec toast-imagen-izquierda / 'La imagen de la notificación gana "
        "siempre': con imagen del sender y app resoluble, el slot dibuja la "
        "imagen de la notificación (rojo inyectado) desde el pad; la tinta "
        "apareció en y=%s" % (top,)
    )


def test_app_con_desktop_muestra_el_logo_de_app(tmp_path, _cache_limpio):
    """Scenario "App con .desktop o icono de tema": sin imagen del sender, el
    slot dibuja el logo de la app (verde inyectado por .desktop exacto)."""
    _inyectar_desktop("App", _png(tmp_path, "app.png", rgb=APP_GREEN))
    w, h, px = _render()          # sin imagen del sender
    top = _ink_top(px, SLOT_X0, SLOT_X1, APP_GREEN, tol=8, min_px=6)
    assert top is not None and abs(top - PAD) <= 2, (
        "spec toast-imagen-izquierda / 'App con .desktop o icono de tema': el "
        "slot debe mostrar el logo de la app inyectado (verde) desde el pad; "
        "la tinta apareció en y=%s" % (top,)
    )


def test_nada_resuelve_cae_al_placeholder_con_la_inicial(nada_resuelve):
    """Scenario "Nada resuelve": sin imagen y sin icono de app el slot NO
    desaparece — cae al placeholder de 80×80 con la INICIAL del nombre.

    Rojo hoy: el slot queda en None y el layout salta a la variante ancha."""
    w, h, px = _render()
    slot = _slot_pb(w)
    assert slot is not None, (
        "spec toast-imagen-izquierda / 'Nada resuelve': sin imagen y sin icono "
        "de app el slot debe caer al placeholder con la inicial, nunca "
        "desaparecer"
    )
    assert (slot.get_width(), slot.get_height()) == (SLOT, SLOT), (
        "el placeholder del slot mide 80x80, no %sx%s"
        % (slot.get_width(), slot.get_height())
    )
    # La INICIAL es legible: hay tinta del color de texto del placeholder
    # (#a6adc8) dentro de la caja del slot. Se cuenta por píxeles, no por
    # filas: el clip circular y la escala cambian dónde cae la glifo.
    tinta = sum(
        1
        for y in range(PAD, PAD + SLOT)
        for x in range(PAD, PAD + SLOT)
        if _cerca(px[y][x][:3], PLACEHOLDER_FG, tol=6)
    )
    assert tinta >= 40, (
        "spec toast-imagen-izquierda / 'Nada resuelve': la inicial del "
        "placeholder debe ser legible dentro del slot (tinta #a6adc8 hallada "
        "en %d px del slot; se esperaban decenas)" % tinta
    )


def test_el_slot_nunca_queda_vacio(nada_resuelve):
    """El slot no solo existe: DIBUJA. Con nada resuelto la caja del slot tiene
    el placeholder en su borde superior (y no el logo de 16 px, que vive en
    otra columna), y el texto arranca en la columna de 240 px.

    Rojo hoy: sin slot, la caja 14..94 está vacía y la columna es 332 px."""
    w, h, px = _render()
    top = _ink_top(px, SLOT_X0, SLOT_X1, PLACEHOLDER_BG, min_px=6)
    assert top is not None and abs(top - PAD) <= 2, (
        "spec toast-imagen-izquierda / 'La imagen izquierda siempre está "
        "presente': el slot de 80 px debe dibujar su placeholder desde el pad, "
        "no quedar en blanco; la tinta apareció en y=%s" % (top,)
    )
    assert w._eff_text_width() == 240, (
        "con el slot presente la columna de texto es la del contrato (240 "
        "px); %s px significa que el layout saltó a la variante sin imagen"
        % (w._eff_text_width(),)
    )


# ── "El bloque de texto arranca al top de la imagen izquierda" ───────────

def test_la_fila_de_app_arranca_al_top_del_slot(tmp_path, _cache_limpio):
    """Scenario "Fila de app al top del slot".

    Con contenido corto (el bloque de texto cabe holgado en la fila de 80 px),
    el borde superior de la fila de app coincide con el del slot (±1 px), sin
    el hundimiento `(row_h - text_h) / 2`.

    La app trae un icono inyectado en rojo, así que el slot (80 px) y el logo
    de la fila (16 px) se miden con el MISMO color y no hace falta distinguir
    el placeholder del logo real.

    Rojo hoy: el texto arranca ~10 px más abajo que el slot."""
    _inyectar_desktop("App", _png(tmp_path, "app.png"))
    w, h, px, top_logo, _ = _filas_above_body()
    top_slot = _ink_top(px, SLOT_X0, SLOT_X1, SENDER_RED, tol=8, min_px=6)
    assert top_slot is not None, (
        "el slot debe dibujar el logo de la app inyectado (rojo) para poder "
        "comparar su borde superior"
    )
    assert top_logo is not None, (
        "la fila de app debe dibujar su logo de 16 px en la columna de texto "
        "(x=%d..%d): no hay tinta" % (LOGO_X0, LOGO_X1)
    )
    assert abs(top_logo - top_slot) <= 1, (
        "spec toast-imagen-izquierda / 'El bloque de texto arranca al top de "
        "la imagen izquierda': la fila de app arranca en y=%s y el slot en "
        "y=%s (Δ=%s px); el centrado vertical del bloque de texto tiene que "
        "salir de _draw (ty = pad)"
        % (top_logo, top_slot, top_logo - top_slot)
    )


def test_sin_respiro_de_la_variante_sin_imagen(tmp_path, _cache_limpio):
    """Scenario "Sin respiro de la variante sin imagen".

    La distancia de la fila de app al título es la misma en TODOS los toasts:
    con imagen del sender, con logo de app y con placeholder. El respiro de
    18 px que sólo existía en la variante sin imagen desaparece.

    Rojo hoy: 26 px con imagen contra 45 px con logo/placeholder."""
    casos = {}
    # 1) imagen del sender (icono del tab)
    casos["imagen del sender"] = _filas_above_body(
        icon_path=_png(tmp_path, "tab.png"))
    # 2) logo de app por .desktop exacto
    _inyectar_desktop("App", _png(tmp_path, "app.png", rgb=APP_GREEN))
    casos["logo de app"] = _filas_above_body()
    # 3) nada resuelve → placeholder
    wp._desktop_cache = None
    casos["placeholder"] = _filas_above_body()

    dists = {}
    for nombre, (w, h, px, logo_top, titulo_top) in casos.items():
        assert logo_top is not None and titulo_top is not None, (
            "no pude medir la fila de app / el título del caso %r "
            "(logo_top=%s, titulo_top=%s)" % (nombre, logo_top, titulo_top)
        )
        dists[nombre] = titulo_top - logo_top

    assert len(set(dists.values())) == 1, (
        "spec toast-imagen-izquierda / 'Sin respiro de la variante sin "
        "imagen': la distancia app→título debe ser la misma en todos los "
        "toasts; medido %s — el respiro de 18 px que sólo tenía la variante "
        "sin imagen tiene que morir" % (dists,)
    )


# ── "Columna de texto única" ─────────────────────────────────────────────

def test_columna_unica_240_y_196_con_hover(nada_resuelve):
    """240 px siempre; 196 px sólo en persistente con hover (franja de 44).

    Rojo hoy: sin nada resuelto la columna es 332 px."""
    w = NotificationWidget(
        "App", "", "T", LONG, None, None, "#80cbc4", persistent=True)
    w._hover = False
    assert w._eff_text_width() == 240, (
        "spec toast-imagen-izquierda / 'Columna de texto única': la columna es "
        "240 px para todos los toasts (con o sin imagen resuelta), no %s px"
        % (w._eff_text_width(),)
    )
    w._hover = True
    assert w._eff_text_width() == 196, (
        "con la franja de descarte (hover en persistente) la columna baja a "
        "196 px: %s" % (w._eff_text_width(),)
    )


def test_el_body_wrapea_igual_con_placeholder_que_con_imagen(tmp_path,
                                                             _cache_limpio):
    """Scenario "Body al mismo ancho con placeholder que con imagen": misma
    columna, mismas fuentes y por lo tanto misma altura de card.

    Rojo hoy: 240 px con imagen contra 332 px con placeholder, y fuentes 11
    contra 13 (el body del placeholder wrappea en más líneas)."""
    w_img, h_img, _ = _render(icon_path=_png(tmp_path, "tab.png"), cuerpo=LONG)
    wp._desktop_cache = None
    w_ph, h_ph, _ = _render(cuerpo=LONG)
    assert w_ph._eff_text_width() == w_img._eff_text_width() == 240, (
        "la columna de texto es la misma con imagen y con placeholder: "
        "%s vs %s" % (w_img._eff_text_width(), w_ph._eff_text_width())
    )
    assert h_ph == h_img, (
        "con la misma columna y las mismas fuentes el body wrappea en las "
        "mismas líneas: la card del placeholder mide %s px y la de la imagen "
        "%s px (las fuentes 11/13 de la variante ancha aún no se unificaron)"
        % (h_ph, h_img)
    )


def test_la_barra_ver_mas_aterriza_igual(tmp_path, _cache_limpio):
    """Scenario "La barra 'Ver más' aterriza igual": con body largo, la barra
    ocupa la misma posición (x0, y0, x1, y1) con imagen real y con placeholder.

    Rojo hoy: la barra del placeholder cae 26 px más abajo (stack y wrap
    distintos)."""
    w_img, h_img, _ = _render(icon_path=_png(tmp_path, "tab.png"), cuerpo=LONG)
    wp._desktop_cache = None
    w_ph, h_ph, _ = _render(cuerpo=LONG)
    assert w_img._expand_rect is not None and w_ph._expand_rect is not None, (
        "con un body que desborda el cap deben verse las dos barras 'Ver más'"
    )
    assert w_ph._expand_rect == w_img._expand_rect, (
        "spec toast-imagen-izquierda / 'La barra \"Ver más\" aterriza igual': "
        "con placeholder la barra cae en %s y con imagen real en %s — la "
        "posición relativa al contenido tiene que ser la misma"
        % (w_ph._expand_rect, w_img._expand_rect)
    )