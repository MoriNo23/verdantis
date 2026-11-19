"""Métricas de layout y primitivas GSK del toast (fuente única).

Extraído de `toast_window.py`: nada acá toca ventanas ni el layer-shell.
"""
import math
import re
import cairo
from typing import NamedTuple

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, Gsk, GdkPixbuf, Pango, PangoCairo, Graphene

from app_info import DEFAULT_ACCENT

_CARD_WIDTH = 360
# 240 = columna de texto completa; el rail de cierre (28) vive dentro de ella.
_TEXT_COL_W = _CARD_WIDTH - 14 - 80 - 12 - 14  # 240
_CLOSE_RAIL_W = 28      # rail de descarte reservado siempre (WCAG 2.5.8 ≥ 24)

# ── Métricas de layout — FUENTE ÚNICA ────────────────────────────────────
_PAD = 14
_IMAGE_LEFT_W = 80
_IMAGE_LEFT_GAP = 12
_ROW_MIN_H = 80
_APP_ROW_H = 20
_APP_ICON_BOX = 16
_TITLE_ROW_H = 22
_BTN_GAP = 8
_ACTIONS_ROW_H = 28
_ACTIONS_GAP = 8
_CARD_RADIUS = 14          # 12 → 14: radio "card física" (estilo Mac)
_TITLE_FS = 13
_BODY_FS = 10
_APP_FS = 10

_PLACEHOLDER_BG = "#313244"
_PLACEHOLDER_FG = "#a6adc8"

# Paleta — se conservan los nombres que miden los tests de contraste.
_CARD_BG_HEX = "#1e1e2e"
_TXT_TITLE_L = "#e6e9f2"
_TXT_BODY_L = "#cdd6f4"
_TXT_APP_L = "#b8bfd0"   # subido de #a6adc8: el gradiente vibrancia al 90%
                         # sobre wallpaper claro bajaba el app-label a 3.89:1
_TXT_TITLE_R = "#d4edd4"
_TXT_BODY_R = "#c8e6c8"
_TXT_APP_R = "#8cb88c"
_TXT_BANDA_R = (0.85, 0.95, 0.85)

# ── Vibrancia oscura (tokens del rediseño GSK) ───────────────────────────
_VIB_TOP = (58 / 255, 60 / 255, 74 / 255, 0.90)     # rgba(58,60,74,.90)
_VIB_BOTTOM = (30 / 255, 30 / 255, 44 / 255, 0.94)  # rgba(30,30,44,.94)
_VIB_BORDER = (1.0, 1.0, 1.0, 0.13)                 # hairline
_VIB_SHADOW = (0.0, 0.0, 0.0, 0.52)
_VIB_SHADOW_DY = 8
_VIB_SHADOW_BLUR = 18
# Botones: superficie blanca translúcida (neutra). El acento tiñe el wipe y la
# X de descarte, no los botones: al 18 % sobre la card salía un gris verdoso
# (#41575F) que chocaba con el gris azulado del fondo.
_VIB_BTN_ALPHA = 0.07
_VIB_BTN_HOVER = 0.11
_VIB_BTN_PRESSED = 0.04
_VIB_INSET = (1.0, 1.0, 1.0, 0.06)
_MIN_ALPHA = 0.90   # spec toast-contraste: AA sobre el fondo real

# La sombra (`_VIB_SHADOW_DY=8`, blur 18) se dibuja FUERA de la card. Si la
# surface del layer-shell mide exactamente la card, el compositor la recorta.
# Agrandamos la surface y metemos la card con márgenes: abajo hace falta más
# sitio porque la sombra cae 8 px; arriba/lados alcanza con el blur parcial.
_SHADOW_PAD = {"top": 12, "right": 12, "bottom": 28, "left": 12}


def close_style(hover=False, pressed=False):
    """(fill, alpha del glifo, hundido) del botón circular de descarte.

    Reutiliza los tokens de los botones de acción: mismo lenguaje, cero
    inundaciones rojas en el rail y sin salto de 30 % a 95 % en la X.
    """
    fill = (_VIB_BTN_PRESSED if pressed
            else _VIB_BTN_HOVER if hover else _VIB_BTN_ALPHA)
    glyph = 0.85 if pressed else 1.0 if hover else 0.70
    return fill, glyph, bool(pressed)


def surface_size(card_w, card_h):
    """Tamaño de la surface layer-shell para que la sombra no se recorte."""
    return (card_w + _SHADOW_PAD["left"] + _SHADOW_PAD["right"],
            card_h + _SHADOW_PAD["top"] + _SHADOW_PAD["bottom"])


def x11_geometry(corner, card_h, margin, screen_w, screen_h, card_w=360):
    """(ancho, alto, x, y) de la ventana X11 con sitio para la sombra.

    Igual critério que `layer_margins`: la card sigue a `margin` px del borde
    aunque la ventana crezca con el padding del shadow.
    """
    w, h = surface_size(card_w, card_h)
    pad = _SHADOW_PAD
    x = (screen_w - margin + pad["right"] - w if "right" in corner
         else margin - pad["left"])
    y = (screen_h - margin + pad["bottom"] - h if "bottom" in corner
         else margin - pad["top"])
    return w, h, x, y


def layer_margins(corner, margin, offset=0):
    """Márgenes del layer-shell: la card queda donde estaba, sin el pad."""
    top = right = bottom = left = 0
    if "top" in corner:
        top = max(0, margin + offset - _SHADOW_PAD["top"])
    else:
        bottom = max(0, margin + offset - _SHADOW_PAD["bottom"])
    if "right" in corner:
        right = max(0, margin - _SHADOW_PAD["right"])
    else:
        left = max(0, margin - _SHADOW_PAD["left"])
    return top, right, bottom, left


def rrect(cr, x, y, w, h, r):
    """Rounded rect path (usado por los helpers de pixbuf offscreen)."""
    r = min(r, w / 2, h / 2)
    cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


# El AA en grises ya no se fija acá: GSK rasteriza los glyphs con su renderer.
# Se conserva el símbolo para compatibilidad con specs/tests que lo citan.
_FONT_OPTIONS = cairo.FontOptions()
_FONT_OPTIONS.set_antialias(cairo.ANTIALIAS_GRAY)


def _create_layout(cr=None):
    """Pango Layout con el font map de PangoCairo (sin contexto de cairo).

    ElAntialiasing lo resuelve GSK al renderizar el layout. Este helper es el
    punto único de creación de layouts del card.
    """
    ctx = Pango.Context()
    ctx.set_font_map(PangoCairo.font_map_get_default())
    return Pango.Layout(ctx)


def _parse_actions(raw):
    """Lista plana D-Bus (pares key/label) → pares, cap 3, sin default.

    El spec manda `actions` como lista PLANA [key, label, key, label]; también
    se aceptan pares ya armados (tests y llamadas internas). Sin esta
    normalización cada string se partía en sus dos primeros caracteres y los
    botones del desktop mostraban "a"/"e" en vez del label real.
    """
    if not raw:
        return []
    out = []
    seen = set()
    try:
        items = list(raw)
    except Exception:
        return []
    if items and isinstance(items[0], str):
        items = list(zip(items[0::2], items[1::2]))
    for item in items:
        try:
            key, label = item[0], item[1]
        except Exception:
            continue
        if not key or not label or key in seen:
            continue
        seen.add(key)
        out.append((str(key), str(label)))
        if len(out) >= 3:
            break
    return out


def _rows_above_body(app_name, hide_title):
    """Filas apiladas por encima del body — fuente única del stack."""
    rows = 0
    if app_name:
        rows += _APP_ROW_H
    if not hide_title:
        rows += _TITLE_ROW_H
    return rows


class _Layout(NamedTuple):
    total_lines: int
    expanded: bool
    cap: int
    body_h: float
    has_more: bool
    content_h: float
    bands_h: float
    piso: float
    text_h: float
    row_h: float


class _Frame(NamedTuple):
    W: int
    H: int
    wx: float
    pad: int
    strip_w: int
    text_col_x: int
    text_col_w: int
    fs: float
    title_fs: int
    body_fs: int
    app_fs: int
    r: int


def _layout_metrics(cuerpo, text_col_w, body_fs, app_name, hide_title,
                    expanded, has_actions, icon_size, max_lines, btn_h):
    """Métrica de layout PURA (no toca GSK ni el widget)."""
    total_lines = _count_body_lines(cuerpo, text_col_w, body_fs)
    cap = min(total_lines, max_lines)
    if expanded:
        _, body_h = _body_metrics(cuerpo, text_col_w, body_fs, max_lines=None)
    else:
        _, body_h = _body_metrics(cuerpo, text_col_w, body_fs, max_lines=cap)
    has_more = total_lines > max_lines
    content_h = _rows_above_body(app_name, hide_title) + body_h
    bands_h = (btn_h + _BTN_GAP if has_more else 0)
    if has_actions:
        bands_h += _ACTIONS_ROW_H + _ACTIONS_GAP
    piso = max(content_h, icon_size)
    text_h = piso + bands_h
    row_h = max(text_h, _ROW_MIN_H)
    return _Layout(total_lines, expanded, cap, body_h, has_more, content_h,
                   bands_h, piso, text_h, row_h)


_PANGO_TAGS = ("b>", "i>", "u>", "s>", "big>", "small>", "tt>", "sub>",
               "sup>", "span", "strikethrough>")


def _sanitize_pango_markup(text):
    """<a href> → label plano (el toast ES el botón)."""
    text = re.sub(r'<a\s+[^>]*>(.*?)</a>', r'\1', text, flags=re.S | re.I)
    return text


def _has_pango_markup(text):
    return "<" in text and any(t in text for t in _PANGO_TAGS)


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _body_metrics(cuerpo, width, font_size=13, max_lines=None):
    """(líneas visuales, altura_px) con el mismo wrap que el dibujado."""
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        return 0, 0
    cuerpo = _sanitize_pango_markup(cuerpo)
    layout = _create_layout()
    layout.set_font_description(Pango.FontDescription("Manrope " + str(font_size)))
    if _has_pango_markup(cuerpo):
        try:
            layout.set_markup(cuerpo, -1)
        except Exception:
            layout.set_text(cuerpo, -1)
    else:
        layout.set_text(cuerpo, -1)
    layout.set_width(int(max(1.0, width) * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    layout.set_justify(True)
    if max_lines:
        line_h = layout.get_line_readonly(0).get_pixel_extents()[1].height
        layout.set_height(int(max_lines * line_h) * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
    lines = layout.get_line_count()
    _, logical = layout.get_pixel_extents()
    return lines, max(0.0, logical.height)


def _count_body_lines(cuerpo, width, font_size=13):
    return _body_metrics(cuerpo, width, font_size)[0]



def _luminancia(rgb):
    """Luminancia relativa WCAG de un RGB normalizado."""
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])


def _icon_tint(pixbuf):
    """Color promedio del icono, aclarado hasta cumplir AA sobre la card."""
    base = _hex_rgb(_TXT_APP_L)
    if pixbuf is None:
        return base
    try:
        px, ch, fila = pixbuf.get_pixels(), pixbuf.get_n_channels(), pixbuf.get_rowstride()
        w, h = pixbuf.get_width(), pixbuf.get_height()
        total = w * h
        paso = max(1, total // 512)      # como máximo ~512 muestras
        sr = sg = sb = n = 0
        for i in range(0, total, paso):
            y, x = divmod(i, w)
            off = y * fila + x * ch
            if ch >= 4 and px[off + 3] < 128:
                continue
            sr += px[off]; sg += px[off + 1]; sb += px[off + 2]
            n += 1
        if not n:
            return base
        tono = (sr / n / 255, sg / n / 255, sb / n / 255)
        for _ in range(16):
            if _luminancia(tono) >= 0.25:
                break
            tono = tuple(c + (1.0 - c) * 0.12 for c in tono)
        return tono
    except Exception:
        return base


def _recortar_transparente(pixbuf):
    """Quita el padding transparente para que `cover` centre el SUJETO.

    Los iconos de tab y los SVG suelen traer mucho espacio vacío: sin esto el
    círculo de 80 px muestra la imagen chica y descentrada dentro del hueco.
    """
    if not pixbuf.get_has_alpha():
        return pixbuf
    w, h = pixbuf.get_width(), pixbuf.get_height()
    # Tope: recorrer millones de píxeles en Python congela el daemon. Las
    # fotos grandes no traen padding que centrar; los iconos sí y son chicos.
    if w * h > 512 * 512:
        return pixbuf
    px, canales, fila = pixbuf.get_pixels(), pixbuf.get_n_channels(), pixbuf.get_rowstride()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        base = y * fila
        for x in range(w):
            if px[base + x * canales + canales - 1]:
                minx, maxx = min(minx, x), max(maxx, x)
                miny, maxy = min(miny, y), max(maxy, y)
    if maxx < minx:
        return None
    if minx == 0 and miny == 0 and maxx == w - 1 and maxy == h - 1:
        return pixbuf
    return GdkPixbuf.Pixbuf.new_subpixbuf(
        pixbuf, minx, miny, maxx - minx + 1, maxy - miny + 1)


def _cover_pixbuf(pixbuf, w, h):
    """Escala con `cover` al rectángulo w×h y recorta por el centro."""
    util = _recortar_transparente(pixbuf)
    src = util if util is not None else pixbuf
    sw, sh = src.get_width(), src.get_height()
    if sw <= 0 or sh <= 0:
        return src
    escala = max(w / sw, h / sh)
    nw, nh = max(w, round(sw * escala)), max(h, round(sh * escala))
    escalado = src.scale_simple(nw, nh, GdkPixbuf.InterpType.HYPER)
    return GdkPixbuf.Pixbuf.new_subpixbuf(
        escalado, (nw - w) // 2, (nh - h) // 2, w, h)


def _make_circular(pixbuf, size):
    """Pixbuf circular (se dibuja luego como Gdk.Texture con clip redondeado)."""
    import cairo as _c
    util = _recortar_transparente(pixbuf)
    scaled = _resample(util if util is not None else pixbuf, size)
    surface = _c.ImageSurface(_c.FORMAT_ARGB32, size, size)
    ctx = _c.Context(surface)
    ctx.arc(size / 2, size / 2, size / 2, 0, 2 * 3.14159)
    ctx.clip()
    Gdk.cairo_set_source_pixbuf(ctx, scaled, 0, 0)
    ctx.paint()
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


def _resample(pixbuf, size, interp=GdkPixbuf.InterpType.HYPER, mode="cover"):
    """Escala al slot `size`×`size` con HYPER (cover o contain)."""
    w0, h0 = pixbuf.get_width(), pixbuf.get_height()
    if w0 <= 0 or h0 <= 0:
        return pixbuf
    if mode == "contain":
        scale = min(size / w0, size / h0)
        nw, nh = max(1, round(w0 * scale)), max(1, round(h0 * scale))
        out = pixbuf.scale_simple(nw, nh, interp)
        canvas = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
        canvas.fill(0x00000000)
        out.copy_area(0, 0, nw, nh, canvas, (size - nw) // 2, (size - nh) // 2)
        return canvas
    scale = max(size / w0, size / h0)
    nw, nh = max(size, round(w0 * scale)), max(size, round(h0 * scale))
    scaled = pixbuf.scale_simple(nw, nh, interp)
    x, y = (nw - size) // 2, (nh - size) // 2
    return GdkPixbuf.Pixbuf.new_subpixbuf(scaled, x, y, size, size)


def _make_placeholder_icon(label, size=16):
    """Square redondeado con la inicial (misma cadena que un logo real)."""
    import cairo as _c
    surface = _c.ImageSurface(_c.FORMAT_ARGB32, size, size)
    ctx = _c.Context(surface)
    ctx.set_source_rgba(*_hex_rgb(_PLACEHOLDER_BG))
    r = min(max(3, size // 4), size / 2)
    ctx.arc(size - r, r, r, 3 * math.pi / 2, 2 * math.pi)
    ctx.arc(size - r, size - r, r, 0, math.pi / 2)
    ctx.arc(r, size - r, r, math.pi / 2, math.pi)
    ctx.arc(r, r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    ctx.fill()
    inicial = (label or "").strip()[:1].upper() or "?"
    ctx.select_font_face("Manrope", _c.FONT_SLANT_NORMAL, _c.FONT_WEIGHT_BOLD)
    ctx.set_font_size(round(size * 0.56))
    ctx.set_source_rgba(*_hex_rgb(_PLACEHOLDER_FG))
    ext = ctx.text_extents(inicial)
    ctx.move_to((size - ext[4]) / 2 - ext[0], (size - ext[3]) / 2 - ext[1])
    ctx.show_text(inicial)
    surface.flush()
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


# ── Helpers GSK ───────────────────────────────────────────────────────────
def _rect(x, y, w, h):
    r = Graphene.Rect()
    r.init(float(x), float(y), float(max(0, w)), float(max(0, h)))
    return r


def _rounded(x, y, w, h, radius):
    rr = Gsk.RoundedRect()
    sz = Graphene.Size().init(float(radius), float(radius))
    rr.init(_rect(x, y, w, h), sz, sz, sz, sz)
    return rr


def _rgba(rgb, alpha=None):
    c = Gdk.RGBA()
    a = alpha if alpha is not None else (rgb[3] if len(rgb) == 4 else 1.0)
    c.red, c.green, c.blue, c.alpha = (
        float(rgb[0]), float(rgb[1]), float(rgb[2]), float(a))
    return c


def _stop(offset, rgb_with_alpha):
    s = Gsk.ColorStop()
    s.offset = float(offset)
    s.color = _rgba(rgb_with_alpha)
    return s


def _round_fill(snapshot, x, y, w, h, radius, color):
    snapshot.save()
    snapshot.push_rounded_clip(_rounded(x, y, w, h, radius))
    snapshot.append_color(_rgba(color), _rect(x, y, w, h))
    snapshot.pop()
    snapshot.restore()


def _append_text(snapshot, layout, x, y, color):
    snapshot.save()
    snapshot.translate(Graphene.Point().init(float(x), float(y)))
    snapshot.append_layout(layout, _rgba(color))
    snapshot.restore()


def _append_sink(snapshot, x, y, w):
    """Sombra interior que hunde el botón al presionarlo (2 px arriba)."""
    snapshot.append_color(_rgba((0.0, 0.0, 0.0, 0.28)), _rect(x, y, w, 2))


def _body_layout(cuerpo, fs, width, max_lines=0):
    """Layout del body: bandera derecha, nunca justificado.

    A 212 px el justificado abre ríos entre palabras y el texto deja de
    escanearse; el cap de líneas se aplica con ellipsize en `_layout_for`.
    """
    return _layout_for(
        cuerpo, Pango.FontDescription("Manrope " + str(fs)),
        width=width, wrap=True, justify=False, markup=True,
        ellipsize=bool(max_lines), max_lines=max_lines)


def _texture(pixbuf):
    return Gdk.Texture.new_for_pixbuf(pixbuf)


def _layout_for(text, font_desc, width=None, ellipsize=False, wrap=False,
                justify=False, markup=False, max_lines=0):
    lay = _create_layout()
    lay.set_font_description(font_desc)
    if markup:
        text = _sanitize_pango_markup(text)
        try:
            lay.set_markup(text, -1) if _has_pango_markup(text) else lay.set_text(text, -1)
        except Exception:
            lay.set_text(text, -1)
    else:
        lay.set_text(text or "", -1)
    if width is not None:
        lay.set_width(int(max(1.0, width) * Pango.SCALE))
    if wrap:
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
    if justify:
        lay.set_justify(True)
    if max_lines > 0:
        line_h = lay.get_line_readonly(0).get_pixel_extents()[1].height
        lay.set_height(int(max_lines * line_h) * Pango.SCALE)
    if ellipsize:
        lay.set_ellipsize(Pango.EllipsizeMode.END)
    return lay


__all__ = ['_SHADOW_PAD', '_icon_tint', '_luminancia', '_cover_pixbuf', 'close_style', 'layer_margins', 'surface_size', 'x11_geometry', '_ACTIONS_GAP', '_ACTIONS_ROW_H', '_APP_FS', '_APP_ICON_BOX', '_APP_ROW_H', '_BODY_FS', '_BTN_GAP', '_CARD_BG_HEX', '_CARD_RADIUS', '_CARD_WIDTH', '_CLOSE_RAIL_W', '_FONT_OPTIONS', '_Frame', '_IMAGE_LEFT_GAP', '_IMAGE_LEFT_W', '_Layout', '_MIN_ALPHA', '_PAD', '_PANGO_TAGS', '_PLACEHOLDER_BG', '_PLACEHOLDER_FG', '_ROW_MIN_H', '_TEXT_COL_W', '_TITLE_FS', '_TITLE_ROW_H', '_TXT_APP_L', '_TXT_APP_R', '_TXT_BANDA_R', '_TXT_BODY_L', '_TXT_BODY_R', '_TXT_TITLE_L', '_TXT_TITLE_R', '_VIB_BORDER', '_VIB_BOTTOM', '_VIB_BTN_ALPHA', '_VIB_BTN_HOVER', '_VIB_BTN_PRESSED', '_VIB_INSET', '_VIB_SHADOW', '_VIB_SHADOW_BLUR', '_VIB_SHADOW_DY', '_VIB_TOP', '_append_sink', '_append_text', '_body_layout', '_body_metrics', '_count_body_lines', '_create_layout', '_has_pango_markup', '_hex_rgb', '_layout_for', '_layout_metrics', '_make_circular', '_make_placeholder_icon', '_parse_actions', '_rect', '_resample', '_rgba', '_round_fill', '_rounded', '_rows_above_body', '_sanitize_pango_markup', '_stop', '_texture', 'rrect']
