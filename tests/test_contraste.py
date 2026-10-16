"""Contraste AA del texto del card (spec `toast-contraste`).

WCAG 2.x: luminancia relativa + ratio, medidos contra el FONDO EFECTIVO de
cada zona — los hex REALES que dibuja el render (constantes de módulo de
`wayland_popup`, no copias):

- Zona clara (sin wipe): el card se pinta con #1e1e2e a alpha 0.85 (reposo)
  o 0.92 (hover) compositado sobre el fondo de referencia #1e1e2e — con ese
  reference el compositado da EXACTO #1e1e2e en ambos estados, así que la
  medición no depende del wallpaper (PRODUCT.md: "no contra negro puro").
- Zona del wipe: blend opaco bg→acento al 15% (lo que pinta _draw_background).
- Bandas ("Ver más" + labels de acciones): fill acento 22% sobre el fondo de
  la zona; label _TXT_TITLE_L en la clara, _TXT_BANDA_R en la oscura.

El acento es el de identidad (app_info.DEFAULT_ACCENT): los hints del sender
pueden pisarlo, la promesa AA es con el acento del producto. No hay texto
grande en el card (todas las fuentes son 10-11px): todo exige 4.5:1.
"""
import app_info
import wayland_popup as wp

AA = 4.5


def _lum(rgb):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(fg, bg):
    l1, l2 = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _mezcla(bg, fg, a):
    """Composita fg sobre bg con alpha a (blending en gamma, como cairo)."""
    return tuple(a * f + (1 - a) * b for f, b in zip(fg, bg))


_BG = wp._hex_rgb(wp._CARD_BG_HEX)
_ACC = wp._hex_rgb(app_info.DEFAULT_ACCENT)
_BG_WIPE = _mezcla(_BG, _ACC, 0.15)          # tinte del wipe (opaco)
_BG_BANDA_L = _mezcla(_BG, _ACC, 0.22)      # fill de banda, zona clara
_BG_BANDA_R = _mezcla(_BG_WIPE, _ACC, 0.22)  # fill de banda, zona wipe


def _assert_aa(nombre, fg, bg):
    r = _ratio(fg, bg)
    assert r >= AA, (
        "{}: contraste {:.2f}:1 < {} contra fondo efectivo {}".format(
            nombre, r, AA, bg)
    )


def test_zona_clara_contraste_aa():
    """Título, body y app label sobre el card compositado (#1e1e2e exacto
    con alpha 0.85 o 0.92 sobre el reference #1e1e2e)."""
    _assert_aa("título (claro)", wp._hex_rgb(wp._TXT_TITLE_L), _BG)
    _assert_aa("body (claro)", wp._hex_rgb(wp._TXT_BODY_L), _BG)
    _assert_aa("app label (claro)", wp._hex_rgb(wp._TXT_APP_L), _BG)


def test_zona_wipe_contraste_aa():
    """La paleta 'right' sobre el blend opaco del 15% hacia el acento."""
    _assert_aa("título (wipe)", wp._hex_rgb(wp._TXT_TITLE_R), _BG_WIPE)
    _assert_aa("body (wipe)", wp._hex_rgb(wp._TXT_BODY_R), _BG_WIPE)
    _assert_aa("app label (wipe)", wp._hex_rgb(wp._TXT_APP_R), _BG_WIPE)


def test_bandas_contraste_aa():
    """Labels de 'Ver más' y de los botones sobre el fill 22% del acento."""
    _assert_aa("banda (claro)", wp._hex_rgb(wp._TXT_TITLE_L), _BG_BANDA_L)
    _assert_aa("banda (wipe)", wp._TXT_BANDA_R, _BG_BANDA_R)


def test_la_medicion_no_usa_negro_puro():
    """El fondo efectivo de la zona clara es el compositado real: si se
    midiera contra negro puro (0,0,0) el ratio inflaría — el test fija el
    método comparando ambos cálculos."""
    fg = wp._hex_rgb(wp._TXT_BODY_L)
    assert _ratio(fg, _BG) < _ratio(fg, (0.0, 0.0, 0.0)), (
        "la medición debe usar el fondo compositado, no negro puro"
    )
