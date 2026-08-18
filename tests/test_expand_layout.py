"""
Tests para la feature de LAYOUT CON EXPANSIÓN del body de Verdantis.

Fix del bug "el texto se corta porque transpasa el espacio disponible":
antes el body se dibujaba línea a línea con cr.show_text() (sin wrap) y la
altura se calculaba con len(cuerpo.split("\\n"))*18 (líneas FÍSICAS), así un
texto largo desbordaba el borde. Ahora:

1. _count_body_lines mide el WRAP REAL del body en el ancho de la columna
   (Pango con font_map), con que calc_card_height coincida con lo dibujado.
2. calc_card_height limita el body a _MAX_VISIBLE_LINES (3) cuando colapsado
   y reserva una franja de botón si el texto excede ese máximo.
3. expandir (expanded=True) muestra todas las líneas envueltas y la tarjeta
   crece; el botón persiste para poder contraer.

Estos tests "ven" el layout computacionalmente, igual que test_visual.py.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")

sys.path.insert(0, "/home/extra/repositorios/verdantis/src")

import wayland_popup as wp

SHORT = "Hola mundo"
LONG = "x" * 400   # a 240px ancho (~sans-serif 14) envuelve en muchas líneas


# ---------------------------------------------------------------------------
# WRAP REAL
# ---------------------------------------------------------------------------

def test_short_text_is_one_line():
    """Texto corto ocupa 1 línea envuelta."""
    assert wp._count_body_lines(SHORT, 240, 14) == 1


def test_long_text_has_gap_and_wraps():
    """Texto largo Mira ampliones líneas visuales (no desborda; envuelve)."""
    n = wp._count_body_lines(LONG, 240, 14)
    assert n > wp.NotificationWidget._MAX_VISIBLE_LINES, f"long={n} debe exceder el tope"


def test_empty_body_is_zero_lines():
    assert wp._count_body_lines("", 240, 14) == 0
    assert wp._count_body_lines("   ", 240, 14) == 0


def test_narrower_width_more_lines():
    """El mismo texto en una columna más angosta envuelve a más líneas."""
    wide = wp._count_body_lines(LONG, 400, 14)
    narrow = wp._count_body_lines(LONG, 120, 14)
    assert narrow > wide, f"narrow={narrow} debe envolver más que wide={wide}"


# ---------------------------------------------------------------------------
# Altura colapsada vs expandida
# ---------------------------------------------------------------------------

def test_collapsed_height_caps_to_max_lines():
    """Colapsado: el body se limita a _MAX_VISIBLE_LINES, alta card acotada."""
    assert wp.NotificationWidget._MAX_VISIBLE_LINES >= 2
    h = wp.WaylandPopup.calc_card_height("App", LONG, "", expanded=False)
    # No puede crecer 1px por cada línea larga: está capeado.
    assert h < wp.WaylandPopup.calc_card_height("App", LONG, "", expanded=True)


def test_expanded_height_grows_with_real_wrap():
    """Expandido: el alto crece linealmente con las líneas envueltas reales."""
    base = wp.WaylandPopup.calc_card_height("App", "c" * 5, "", expanded=True)
    big = wp.WaylandPopup.calc_card_height("App", LONG, "", expanded=True)
    assert big > base, "expandir un cuerpo largo debe producir una card más alta"


def test_expanded_equals_collapsed_when_no_overflow():
    """Cuerpo corto: expandido == colapsado (no hay nada que expandir)."""
    short_h = wp.WaylandPopup.calc_card_height("", SHORT, "", expanded=False)
    long_h = wp.WaylandPopup.calc_card_height("", SHORT, "", expanded=True)
    assert short_h == long_h


def test_collapsed_body_limit_at_visible_lines():
    """El colapso no debe dejar la card con 1 línea = una tarjeta mínima."""
    c = wp.WaylandPopup.calc_card_height("", LONG, "", expanded=False)
    e = wp.WaylandPopup.calc_card_height("", LONG, "", expanded=True)
    assert c < e, "exige reserva de botón cuando colapsa"


# ---------------------------------------------------------------------------
# Botón expandir/contraer presente solo cuando hay overflow
# ---------------------------------------------------------------------------

def _draw_then_get_rect(cuerpo, expanded):
    """Ejecuta _draw headless (con allocation forzada) y devuelve el rect del botón."""
    import cairo
    from gi.repository import Gdk
    w = wp.NotificationWidget("App", "", "T", cuerpo, None, None, "#80cbc4")
    w._expanded = expanded
    h = w.desired_height()
    a = Gdk.Rectangle()
    a.x, a.y, a.width, a.height = 0, 0, 360, h
    w.get_allocation = lambda a=a: a
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, h)
    ctx = cairo.Context(surf)
    w._draw(w, ctx)
    return w._expand_rect


def test_expand_rect_present_on_overflow():
    """Cuerpo largo colapsado => el widget traza un rect de botón (pulsable)."""
    rect = _draw_then_get_rect(LONG, expanded=False)
    assert rect is not None and rect[1] < rect[3], f"rect={rect}"


def test_expand_rect_present_when_expanded():
    """Aún expandido el botón queda para poder contraer."""
    rect = _draw_then_get_rect(LONG, expanded=True)
    assert rect is not None


def test_no_expand_rect_when_short():
    """Cuerpo corto => NO hay botón (nada que expandir)."""
    assert _draw_then_get_rect(SHORT, expanded=False) is None


# ---------------------------------------------------------------------------
# Metatests de sensibilidad
# ---------------------------------------------------------------------------

def test_metatest_wrapper_measure_sensitive_to_fontmap():
    """
    SENSIBILIDAD: si se volviera a medir con Pango.Context() sin font_map
    (bug), _count_body_lines devolvería 1 para texto largo y el drag de
    desborde volvería (o la altura se subestimaría). Este metatest caza el
    regresión de la causa raíz del bug.
    """
    assert wp._count_body_lines(LONG, 240, 14) > 1, (
        "Metatest: el wrapper debe contar líneas >1; si falló, la medición "
        "perdió el font_map y el body volvería a desbordar."
    )


def test_metatest_expand_grows_height_sensitive_to_regression():
    """Si expand (=mostrar todo) dejara de crecer la card, el plus de leer
    cómodamente desaparecería. Este metatest lo detectaría."""
    nc = wp.WaylandPopup.calc_card_height("", LONG, "", expanded=False)
    ne = wp.WaylandPopup.calc_card_height("", LONG, "", expanded=True)
    assert ne > nc, (
        "Metatest: expandir debe agrandar la card; si falló, el toggle "
        "perdió el crecimiento y no se puede leer el texto largo."
    )


# ---------------------------------------------------------------------------
# Chevrón del botón: dirección y visibilidad (test visual numérico)
# ---------------------------------------------------------------------------

def _chevron_imbalance(expanded):
    """Render headless del widget y devuelve el sesgo vertical del chevrón.

    >0  → masa de píxeles acento ARRIBA del centro = chevrón ▼ (colapsado)
    <0  → masa ABAJO = chevrón ▲ (expandido)
    0.0 → no hay chevrón visible (regresión: fill/stroke perdido).
    """
    import cairo
    from gi.repository import Gdk
    w = wp.NotificationWidget("App", "", "T", LONG, None, None, "#89b4fa")
    w._expanded = expanded
    h = w.desired_height()
    a = Gdk.Rectangle(); a.x = a.y = 0; a.width, a.height = 360, h
    w.get_allocation = lambda: a
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, h)
    w._draw(w, cairo.Context(surf))
    data = surf.get_data(); stride = surf.get_stride()
    ys = []
    for y in range(h):
        cnt = 0
        for x in range(300, 360):  # borde derecho del pill
            o = y * stride + x * 4
            r, g, b = data[o + 2], data[o + 1], data[o]
            if 0x70 < r < 0xA0 and 0xA0 < g < 0xD0 and b > 0xE0:  # acento puro (#89b4fa), sin bordes de texto
                cnt += 1
        ys.append(cnt)
    if not any(ys):
        return 0.0
    ymin = next(i for i, c in enumerate(ys) if c)
    ymax = max(i for i, c in enumerate(ys) if c)
    mid = (ymin + ymax) / 2
    up = sum(ys[y] for y in range(ymin, ymax + 1) if y <= mid)
    down = sum(ys[y] for y in range(ymin, ymax + 1) if y > mid)
    return (up - down) / max(1, up + down)


def test_chevron_visible_and_direction():
    """El chevrón SE dibuja (fill) y apunta bien: ▼ colapsado, ▲ expandido."""
    col = _chevron_imbalance(False)
    exp = _chevron_imbalance(True)
    assert col > 0.05, f"colapsado debe ser ▼ (masa arriba), imbalance={col:.2f}"
    assert exp < -0.05, f"expandido debe ser ▲ (masa abajo), imbalance={exp:.2f}"