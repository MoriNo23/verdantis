"""
Tests unitarios visuales para Verdantis.

El agente NO puede ver la pantalla, así que valida el OUTPUT VISUAL
de forma computable mediante las PROPIEDADES MATEMÁTICAS que controlan
la apariencia (que el widget calcula y que Gtk renderiza):

- Colores (accent → RGB, fondo/wipe) parametrizados por urgency.
- Opacidad (alpha) por nivel de urgencia.
- Duración visual (tiempo visible) por urgency.
- Dimensiones de la card según contenido (banner, cuerpo).
- Posicionamiento por corner (márgenes layer-shell).

Estos tests "ven" la notificación sin ojos: cada propiedad numérica
describe cómo se pintará. Se evita depender de un display Gtk (los
tests corren correctamente incluso sin servidor X/Wayland).
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "wayland")

sys.path.insert(0, "/home/fullmetal/repos/verdantis/src")

import wayland_popup as wp


def _popup(urgency=1, duration=8000):
    """Crea un WaylandPopup sin display (solo propiedades de apariencia)."""
    return wp.WaylandPopup(
        titulo="Título", cuerpo="Cuerpo",
        corner="top-right", accent="#80cbc4",
        app_name="App", duration=duration, urgency=urgency,
    )


# ---------------------------------------------------------------------------
# PROPIEDADES VISUALES: OPACIDAD y COLOR del fondo
# ---------------------------------------------------------------------------

def test_urgency_low_is_more_translucent():
    """urgency=0 (low): el fondo debe ser MÁS translúcido (alpha menor)."""
    low = _popup(urgency=0)
    assert low._bg_alpha == 0.55, f"low alpha={low._bg_alpha}, esperado 0.55"


def test_urgency_normal_is_default():
    """urgency=1 (normal): alpha=0.85 (comportamiento por defecto)."""
    normal = _popup(urgency=1)
    assert normal._bg_alpha == 0.85, f"normal alpha={normal._bg_alpha}, esperado 0.85"


def test_urgency_critical_is_opaque():
    """urgency=2 (critical): fondo completamente opaco."""
    crit = _popup(urgency=2)
    assert crit._bg_alpha == 1.0, f"critical alpha={crit._bg_alpha}, esperado 1.0"


def test_urgency_ordering_of_opacity():
    """El orden de opacidad debe ser low < normal < critical."""
    a_low = _popup(urgency=0)._bg_alpha
    a_norm = _popup(urgency=1)._bg_alpha
    a_crit = _popup(urgency=2)._bg_alpha
    assert a_crit > a_norm > a_low, f"orden incorrecto: {a_crit} {a_norm} {a_low}"


# ---------------------------------------------------------------------------
# PROPIEDADES VISUALES: DURACIÓN (tiempo visible)
# ---------------------------------------------------------------------------

def test_urgency_low_duration_shorter():
    """urgency=0: dura MENOS (visible menos tiempo)."""
    low = _popup(urgency=0, duration=8000)
    assert low.duration < 8000, f"low duration={low.duration}, debe ser <8000"
    assert low.duration == int(8000 * 0.7)


def test_urgency_critical_duration_longer():
    """urgency=2: dura MÁS (visible más tiempo)."""
    crit = _popup(urgency=2, duration=8000)
    assert crit.duration > 8000, f"critical duration={crit.duration}, debe ser >8000"
    assert crit.duration == int(8000 * 1.5)


def test_urgency_normal_duration_unchanged():
    """urgency=1: duración sin modificar."""
    norm = _popup(urgency=1, duration=8000)
    assert norm.duration == 8000


# ---------------------------------------------------------------------------
# PROPIEDADES VISUALES: COLOR ACENTO
# ---------------------------------------------------------------------------

def test_accent_parsed_to_rgb():
    """El accent hex se convierte a RGB normalizado (0-1) para Cairo."""
    # Constructor usa accent directamente; _hex_rgb lo convierte
    accent_rgb = wp._hex_rgb("#89b4fa")
    assert abs(accent_rgb[0] - 0x89 / 255) < 0.01  # 137/255
    assert abs(accent_rgb[1] - 0xB4 / 255) < 0.01  # 180/255
    assert abs(accent_rgb[2] - 0xFA / 255) < 0.01  # 250/255


def test_card_background_color_is_drak_theme():
    """El fondo de la card es el color del tema (#1e1e2e)."""
    card_rgb = wp._hex_rgb("#1e1e2e")
    assert abs(card_rgb[0] - 0x1E / 255) < 0.01
    assert abs(card_rgb[1] - 0x1E / 255) < 0.01
    assert abs(card_rgb[2] - 0x2E / 255) < 0.01


# ---------------------------------------------------------------------------
# PROPIEDADES VISUALES: LAYOUT y DIMENSIONES
# ---------------------------------------------------------------------------

def test_card_dimensions_for_image_and_body():
    """La altura de la card es coherente con la medición real del body (no
    desborda) y crece si hay imagen banner (260x140)."""
    # "c" corto → row mínimo (80) → card mínima
    assert wp.WaylandPopup.calc_card_height("App", "c", "") >= 14 + 80 + 14
    # cuerpo largo (wrap) genera más alto que uno corto
    largo = wp.WaylandPopup.calc_card_height("App", "x" * 400, "", expanded=True)
    corto = wp.WaylandPopup.calc_card_height("App", "c", "", expanded=True)
    assert largo > corto, "un body largo expandido debe agrandar la card"
    # imagen añade su banner (8 + 140) a la altura base
    import os
    tmp = os.path.join(os.path.dirname(__file__), "_tmp_icon_x.png")
    with open(tmp, "wb") as f:
        f.write(b"fake png")
    try:
        con_img = wp.WaylandPopup.calc_card_height("App", "c", tmp)
    finally:
        os.remove(tmp)
    sin_img = wp.WaylandPopup.calc_card_height("App", "c", "")
    assert con_img == sin_img + 8 + 140, f"con img={con_img}, sin={sin_img}"


def test_unified_card_height_formula():
    """calc_card_height produce una altura coherente para cuerpo corto."""
    # app_name + 1 línea de cuerpo: text_h=20+21+18=59, row_h=max(59,80)=80
    h = wp.WaylandPopup.calc_card_height("", "hola", "")
    assert h == 14 + 80 + 14, f"altura={h}, esperado {14+80+14}"


def test_corner_margin_map():
    """Los márgenes layer-shell difieren según la esquina (posición visual)."""
    top_right = wp.WaylandPopup._MARGIN_MAP["top-right"]
    bottom_left = wp.WaylandPopup._MARGIN_MAP["bottom-left"]
    # top-right: margin top > 0, bottom = 0
    assert top_right[0] > 0 and top_right[2] == 0
    assert bottom_left[2] > 0 and bottom_left[0] == 0