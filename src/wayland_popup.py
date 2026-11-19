import math
import os
import re
import sys
import subprocess
import ctypes
import configparser
import cairo
from typing import NamedTuple

# ── GTK4 Layer Shell: cargar ANTES de gi ───────────────────────────────────
#gtk4-layer-shell debe linkearse antes que libwayland-client o is_supported()
#da False ("Failed to initialize layer surface"). RTLD_GLOBAL lo fuerza sin
#necesitar LD_PRELOAD en el service. Verificado en Debian 13 / KWin 6.
try:
    ctypes.CDLL("libgtk4-layer-shell.so.0", mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

os.environ.setdefault("GDK_BACKEND", "wayland")

import time
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import (Gtk, Gdk, Gsk, GLib, GdkPixbuf, Pango,
                           PangoCairo, Gtk4LayerShell, Graphene)

from app_info import APP_ID, APP_NAME, DEFAULT_ACCENT


# ── Bundled font: Manrope (OFL) ──────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _register_bundled_font():
    """Registra los TTF de Manrope en fontconfig al importar (idempotente)."""
    try:
        fc = ctypes.CDLL("libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        # Sin restype c_void_p, ctypes trunca el puntero de 64 bits a int y
        # FcConfigAppFontAddFile segfaulta (GTK4 cambia el layout de memoria).
        fc.FcConfigGetCurrent.argtypes = []
        fc.FcConfigGetCurrent.restype = ctypes.c_void_p
        cfg = fc.FcConfigGetCurrent()
        for name in ("Manrope-Regular.ttf", "Manrope-Bold.ttf"):
            path = os.path.join(_FONT_DIR, name)
            if os.path.exists(path):
                fc.FcConfigAppFontAddFile(cfg, path.encode())
    except Exception:
        pass


_register_bundled_font()


_DESKTOP_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/local/share/applications",
    "/usr/share/applications",
]

_desktop_cache = None


def _rebuild_desktop_cache():
    global _desktop_cache
    _desktop_cache = {}
    for d in _DESKTOP_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            for f in os.listdir(d):
                if not f.endswith(".desktop"):
                    continue
                path = os.path.join(d, f)
                try:
                    cp = configparser.ConfigParser()
                    cp.read(path)
                    entry = {
                        "path": path,
                        "Name": cp.get("Desktop Entry", "Name", fallback=""),
                        "Icon": cp.get("Desktop Entry", "Icon", fallback=""),
                        "StartupWMClass": cp.get(
                            "Desktop Entry", "StartupWMClass", fallback=""),
                    }
                    stem = f[:-8].lower()
                    _desktop_cache.setdefault(stem, []).append(entry)
                    wm = entry["StartupWMClass"].lower()
                    if wm:
                        _desktop_cache.setdefault(wm, []).append(entry)
                    nm = entry["Name"].lower()
                    if nm:
                        _desktop_cache.setdefault(nm, []).append(entry)
                except Exception:
                    pass
        except Exception:
            pass


def _get_app_icon_from_desktop(app_name, size=80, mode="cover"):
    """Icono de la app desde .desktop, SOLO con match EXACTO."""
    path = _exact_desktop_file(app_name)
    if not path:
        return None
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        icon_name = cp.get("Desktop Entry", "Icon", fallback="")
        if icon_name:
            if icon_name.startswith("/") and os.path.exists(icon_name):
                return _resample(
                    GdkPixbuf.Pixbuf.new_from_file(icon_name), size, mode=mode)
            return _icon_from_theme(icon_name, size)
    except Exception:
        pass
    return None


def _exact_desktop_file(app_name):
    """Resuelve el .desktop con match EXACTO (stem/WMClass/Name), sin substring."""
    if not app_name:
        return None
    if _desktop_cache is None:
        _rebuild_desktop_cache()
    entries = _desktop_cache.get(app_name.lower().strip())
    if entries:
        return entries[0]["path"]
    _rebuild_desktop_cache()
    entries = _desktop_cache.get(app_name.lower().strip())
    if entries:
        return entries[0]["path"]
    return None


def _get_app_display_name(app_name):
    """Nombre visible de la app (match exacto de .desktop, sino el raw)."""
    if not app_name:
        return ""
    path = _exact_desktop_file(app_name)
    if not path:
        return app_name
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        return cp.get("Desktop Entry", "Name", fallback=app_name)
    except Exception:
        return app_name


_URL_RE = re.compile(r'https?://[^\s<>"\'\)\]]+', re.IGNORECASE)
_BARE_HOST_RE = re.compile(
    r'(?<![\w./-])(?:[a-z][\w-]*\.)+[a-z]{2,}(?::\d+)?(?:/[^\s<>"\'\)\]]*)?'
    r'|\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/[^\s<>"\'\)\]]*)?',
    re.IGNORECASE,
)


def _strip_urls(text):
    """Quita URLs del TEXTO VISIBLE del body (el destino es para el click)."""
    if not text:
        return text
    parts = re.split(r'(<[^>]*>)', text)
    out = "".join(
        (_BARE_HOST_RE.sub("", _URL_RE.sub("", part))
         if not part.startswith("<") else part)
        for part in parts
    )
    out = re.sub(r'<a\s+[^>]*>\s*</a>', '', out)
    return re.sub(r'\n{2,}', '\n', out).strip("\n")


def _icon_from_theme(icon_name, size=16):
    """Icono del tema hicolor/Breeze por nombre (reintento en minúsculas)."""
    if not icon_name:
        return None
    attempts = [icon_name]
    lowered = icon_name.lower()
    if lowered != icon_name:
        attempts.append(lowered)
    for attempt in attempts:
        try:
            display = Gdk.Display.get_default()
            theme = (Gtk.IconTheme.get_for_display(display) if display
                     else Gtk.IconTheme.new())
            info = theme.lookup_icon(attempt, size, 0)
            if info:
                return info.load_icon()
        except Exception:
            pass
    return None


# Patrones para copiar códigos de verificación SIN falsos positivos.
# Un número suelto no es un código: en el historial real hay años (1991),
# versiones (b200148) y menciones (@usuario4161). Solo contamos un número
# cuando una palabra de verificación aparece CERCA (misma frase, ±40 chars).
_CODE_WORDS = (
    r"c[oó]digo|verificaci[oó]n|confirmaci[oó]n|validaci[oó]n|"
    r"clave|pin|otp|c[oó]digo de acceso|codigo"
)
_CODE_RE = re.compile(
    r"(?<![\d/])(?P<code>\d{4,8})(?![\d/-])", re.UNICODE)
_CODE_CONTEXT_RE = re.compile(_CODE_WORDS, re.IGNORECASE | re.UNICODE)


def _find_code(text):
    """Devuelve el código de verificación del body, o None si no hay.

    Exige que una palabra clave de verificación esté a ±40 caracteres del
    número. Así un año ("Wyeth, 1991") o una versión ("b200148") no se
    confunden con un código.
    """
    if not text:
        return None
    for m in _CODE_RE.finditer(text):
        lo = max(0, m.start() - 40)
        hi = min(len(text), m.end() + 40)
        if _CODE_CONTEXT_RE.search(text[lo:hi]):
            return m.group("code")
    return None





def _copy_to_clipboard(text):
    """Copia al portapapeles sin robar foco (wl-copy en Wayland, xclip/xsel en X11).

    A diferencia de KDE (que necesita takeFocus para QClipboard), wl-copy
    habla con el compositor directamente: compatible con keyboard_mode=NONE.
    """
    if not text:
        return False
    if os.environ.get("WAYLAND_DISPLAY"):
        cmd = ["wl-copy", text]
    elif _tiene_comando("xclip"):
        cmd = ["xclip", "-selection", "clipboard"]
    else:
        cmd = ["xsel", "--clipboard", "--input"]
    try:
        if cmd[0] in ("xclip", "xsel"):
            subprocess.run(cmd, input=text, text=True, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, check=False, input=text, text=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _tiene_comando(nombre):
    """True si `nombre` está en PATH (sin lanzar nada)."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isfile(os.path.join(d, nombre)) and os.access(
                os.path.join(d, nombre), os.X_OK):
            return True
    return False


def _extract_markup_url(text):
    """Extrae el href del primer <a href="..."> en un body con markup."""
    if not text or "<a " not in text:
        return ""
    m = re.search(r'<a\s+[^>]*href=["\']([^"\']+)["\']', text, re.IGNORECASE)
    if m:
        url = m.group(1)
        if url.startswith(("http://", "https://", "mailto:", "tel:")):
            return url
    return ""


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
_BODY_FS = 12
_APP_FS = 11

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


def _make_circular(pixbuf, size):
    """Pixbuf circular (se dibuja luego como Gdk.Texture con clip redondeado)."""
    import cairo as _c
    scaled = _resample(pixbuf, size)
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
        max_lines=max_lines)


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


class NotificationWidget(Gtk.Widget):
    """Toast: widget GSK puro. Dibuja en do_snapshot, interactúa con controllers."""

    _MAX_VISIBLE_LINES = 3
    _BTN_H = 28
    # Antes el hover reservaba 80 px de franja: la columna de texto pasaba de
    # 240 a 160, el botón Copiar se corría y la card cambiaba de alto con el
    # mouse encima. Ahora el rail es fijo y el hover solo lo tiñe.
    _CLOSE_RAIL_W = _CLOSE_RAIL_W

    def __init__(self, app_name, app_icon, titulo, cuerpo, icon_path, image_path,
                 accent, image_data_raw=None, on_click=None, on_resize=None,
                 on_close=None, app_label=None, hide_title=False,
                 persistent=False, actions=None, action_icons=False,
                 buttons_actionable=True):
        super().__init__()
        self.set_name("verdantis-toast")

        self._actions = _parse_actions(actions)
        self._action_rects = []
        self._hover_action_idx = None
        self._action_icon_pbs = {}
        if action_icons:
            for key, _label in self._actions:
                icono = _icon_from_theme(key, 16)
                if icono is not None:
                    self._action_icon_pbs[key] = _resample(icono, 16, mode="contain")

        # Escala de fuente por resolución: Gdk4 no tiene Screen.
        sw = 0
        try:
            display = Gdk.Display.get_default()
            monitors = display.get_monitors() if display else None
            if monitors and monitors.get_n_items():
                sw = monitors.get_item(0).get_geometry().width
        except Exception:
            sw = 0
        if sw and sw < 1280:
            self._font_scale = 0.85
        elif sw and sw < 1600:
            self._font_scale = 0.92
        else:
            self._font_scale = 1.0

        self._expanded = False
        self._expand_rect = None
        self._image_left_rect = None
        self._on_resize = on_resize
        self._fraction = 1.0
        self._on_click = on_click
        self._on_close = on_close
        self._persistent = persistent
        self._buttons_actionable = buttons_actionable
        self._hover = False
        self._hover_close = False
        self._close_rect = None
        self._pressed_close = False
        self._pressed_action_idx = None
        # Botón local "Copiar" (no es action D-Bus: no emite ActionInvoked).
        self._copy_rect = None
        self._pressed_copy = False
        self._hover_copy = False
        self._copy_text = None          # se fija después de sanitizar _cuerpo
        self._copy_done = False         # confirmación "Copiado" transitoria
        self._cursor_hand = False
        self._last_pointer = None       # (x, y) local del último motion/enter

        self._app_label = app_label
        self._hide_title = hide_title
        self._app_name = _get_app_display_name(app_name)
        self._titulo = (titulo or "").replace("\n", " ").replace("\t", " ").strip()
        self._cuerpo = _strip_urls(cuerpo)
        # Solo con código de verificación: el botón es para pegar el código en
        # la app, no un "copiar todo" que aparecería en casi todos los toasts.
        self._copy_text = _find_code(self._cuerpo)
        self._accent_rgb = _hex_rgb(accent)
        self._card_bg = _hex_rgb(_CARD_BG_HEX)

        self._left_title = _hex_rgb(_TXT_TITLE_L)
        self._left_body = _hex_rgb(_TXT_BODY_L)
        self._left_app = _hex_rgb(_TXT_APP_L)
        self._right_title = _hex_rgb(_TXT_TITLE_R)
        self._right_body = _hex_rgb(_TXT_BODY_R)
        self._right_app = _hex_rgb(_TXT_APP_R)

        self._app_icon_pb = None
        self._image_left_pb = None
        self._image_pb = None

        if app_icon and os.path.exists(app_icon):
            try:
                self._app_icon_pb = _resample(
                    GdkPixbuf.Pixbuf.new_from_file(app_icon), 16, mode="contain")
            except Exception:
                pass
        if not self._app_icon_pb:
            icon_from_desktop = _get_app_icon_from_desktop(app_name, 16, mode="contain")
            if icon_from_desktop:
                self._app_icon_pb = _resample(icon_from_desktop, 16, mode="contain")
            else:
                theme_icon = (_icon_from_theme(app_icon, 16)
                              or _icon_from_theme(app_name, 16))
                if theme_icon:
                    self._app_icon_pb = _resample(theme_icon, 16, mode="contain")
        if not self._app_icon_pb:
            self._app_icon_pb = _make_placeholder_icon(self._app_name, 16)

        if icon_path and os.path.exists(icon_path):
            try:
                raw = GdkPixbuf.Pixbuf.new_from_file(icon_path)
                self._image_left_pb = _make_circular(raw, _IMAGE_LEFT_W)
            except Exception:
                pass
        if not self._image_left_pb and image_data_raw:
            try:
                w, h, rowstride, has_alpha, bps, n_channels, data = image_data_raw
                raw = GdkPixbuf.Pixbuf.new_from_bytes(
                    GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB,
                    has_alpha, bps, w, h, rowstride)
                self._image_left_pb = _make_circular(raw, _IMAGE_LEFT_W)
            except Exception:
                pass
        if not self._image_left_pb:
            icon_from_desktop = _get_app_icon_from_desktop(app_name, _IMAGE_LEFT_W)
            if icon_from_desktop:
                self._image_left_pb = _make_circular(icon_from_desktop, _IMAGE_LEFT_W)
            if not self._image_left_pb:
                theme_icon = (_icon_from_theme(app_icon, _IMAGE_LEFT_W)
                              or _icon_from_theme(app_name, _IMAGE_LEFT_W))
                if theme_icon:
                    self._image_left_pb = _make_circular(theme_icon, _IMAGE_LEFT_W)
        if not self._image_left_pb:
            self._image_left_pb = _make_circular(
                _make_placeholder_icon(self._app_name, _IMAGE_LEFT_W), _IMAGE_LEFT_W)

        if image_path and os.path.exists(image_path):
            try:
                self._image_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    image_path, 260, 140, True)
            except Exception:
                pass

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", lambda _c, x, y: self._on_enter_xy(x, y))
        motion.connect("leave", lambda _c: self._on_leave_evt())
        motion.connect("motion", lambda _c, x, y: self._on_motion_xy(x, y))
        self.add_controller(motion)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("pressed", lambda _c, n, x, y: self._on_press_xy(x, y))
        click.connect("released", lambda _c, n, x, y: self._on_release_xy(x, y))
        self.add_controller(click)

    # ──尺寸 / GTK vfuncs ─────────────────────────────────────────────────
    def do_measure(self, orientation, for_size):
        rw, rh = self.get_size_request()
        if orientation == Gtk.Orientation.HORIZONTAL:
            w = rw if rw > 0 else _CARD_WIDTH
            return (w, w, -1, -1)
        h = rh if rh > 0 else self.desired_height()
        return (h, h, -1, -1)

    def do_snapshot(self, snapshot):
        W, H = self.get_width(), self.get_height()
        if W < 10 or H < 10:
            return
        fr = self._frame(W, H)
        lay = _layout_metrics(
            cuerpo=self._cuerpo, text_col_w=fr.text_col_w, body_fs=fr.body_fs,
            app_name=self._app_name, hide_title=self._hide_title,
            expanded=self._expanded, has_actions=bool(self._actions),
            icon_size=_IMAGE_LEFT_W, max_lines=self._MAX_VISIBLE_LINES,
            btn_h=self._BTN_H,
        )
        self._snapshot_background(snapshot, fr)
        self._snapshot_image_left(snapshot, fr, lay)
        self._snapshot_actions(snapshot, fr, lay)
        self._snapshot_copy(snapshot, fr, lay)
        self._snapshot_expand_bar(snapshot, fr, lay)
        self._snapshot_text_passes(snapshot, fr, lay)
        self._snapshot_banner(snapshot, fr, lay)
        self._snapshot_close_strip(snapshot, fr)

    # ──Interacción ───────────────────────────────────────────────────────
    # Wrappers de compatibilidad: los controllers GTK4 pasan (x, y), pero la
    # suite y el código heredado llaman con (widget, event.x, event.y).
    def _on_button_press(self, widget, event):
        return self._on_press_xy(event.x, event.y)

    def _on_button_release(self, widget, event):
        return self._on_release_xy(event.x, event.y)

    def _on_enter(self, widget, event):
        return self._on_enter_xy(event.x, event.y)

    def _on_leave(self, widget, event=None):
        return self._on_leave_evt()

    def _on_motion(self, widget, event):
        return self._on_motion_xy(event.x, event.y)

    def _on_enter_xy(self, x, y):
        self._hover = True
        self._hover_close = self._in_close_rect(x, y)
        self._last_pointer = (x, y)
        self._aplicar_cursor(x, y)
        self.queue_draw()
        self._resize_por_hover()

    def _on_leave_evt(self):
        self._hover = False
        self._hover_close = False
        self._hover_action_idx = None
        self._pressed_close = False
        self._pressed_action_idx = None
        self._cursor_hand = False
        self._last_pointer = None
        self._set_cursor(False)
        self.queue_draw()
        self._resize_por_hover()

    def _resize_por_hover(self):
        if not self._on_resize:
            return
        h = self.desired_height()
        if h != self.get_size_request()[1]:
            self._on_resize(h)

    def _sincronizar_hover_tras_desplazar(self, dy):
        """Re-evalúa hover tras mover la window (KWin no entrega leave)."""
        if self._last_pointer is None:
            return
        x, y = self._last_pointer
        rw, rh = self.get_size_request()
        w = rw if rw > 0 else (self.get_width() or _CARD_WIDTH)
        h = rh if rh > 0 else (self.get_height() or self.desired_height())
        dentro = (0 <= x < w) and (0 <= y - dy < h)
        if dentro == self._hover:
            return
        self._hover = dentro
        if dentro:
            self._aplicar_cursor(x, y)
        else:
            self._hover_close = False
            self._cursor_hand = False
            self._set_cursor(False)
        self.queue_draw()
        self._resize_por_hover()

    def _on_motion_xy(self, x, y):
        self._last_pointer = (x, y)
        over_action = None
        for i, rect in enumerate(self._action_rects):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                over_action = i
                break
        if over_action != self._hover_action_idx:
            self._hover_action_idx = over_action
            self.queue_draw()
        over_close = self._in_close_rect(x, y)
        if over_close != self._hover_close:
            self._hover_close = over_close
            self.queue_draw()
        over_copy = self._in_copy_rect(x, y)
        if over_copy != getattr(self, "_hover_copy", False):
            self._hover_copy = over_copy
            self.queue_draw()
        self._aplicar_cursor(x, y)

    def _set_cursor(self, hand):
        try:
            cursor = Gdk.Cursor.new_from_name(
                "pointer" if hand else "default", None)
            if cursor:
                self.set_cursor(cursor)
        except Exception:
            pass

    def _in_close_rect(self, x, y):
        if not self._close_rect:
            return False
        x0, y0, x1, y1 = self._close_rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def _in_copy_rect(self, x, y):
        if not getattr(self, "_copy_rect", None):
            return False
        x0, y0, x1, y1 = self._copy_rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def _cursor_por_posicion(self, x, y):
        if self._in_close_rect(x, y):
            return True
        if self._in_copy_rect(x, y):
            return False   # acción local, siempre habilitada (no depende del sender)
        en_boton = any(r[0] <= x <= r[2] and r[1] <= y <= r[3]
                       for r in self._action_rects)
        if en_boton:
            return bool(self._buttons_actionable and self._on_click)
        return self._on_click is not None

    def _aplicar_cursor(self, x, y):
        hand = self._cursor_por_posicion(x, y)
        if hand != self._cursor_hand:
            self._cursor_hand = hand
            self._set_cursor(hand)

    def _on_press_xy(self, x, y):
        if self._in_close_rect(x, y):
            self._pressed_close = True
            self.queue_draw()
            return True
        # Botón Copiar: se ejecuta al SOLTAR (release-based), como la X.
        if self._in_copy_rect(x, y):
            self._pressed_copy = True
            self.queue_draw()
            return True
        if self._expand_rect:
            x0, y0, x1, y1 = self._expand_rect
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.toggle_expanded()
                return True
        for i, rect in enumerate(self._action_rects):
            x0, y0, x1, y1, _key = rect
            if x0 <= x <= x1 and y0 <= y <= y1:
                if self._buttons_actionable and self._on_click:
                    self._pressed_action_idx = i
                    self.queue_draw()
                return True
        if self._on_click and self._on_click(None):
            self._close("action")
        return True

    def _on_release_xy(self, x, y):
        if getattr(self, "_pressed_copy", False):
            dentro = self._in_copy_rect(x, y)
            self._pressed_copy = False
            self.queue_draw()
            if dentro and self._copy_text and _copy_to_clipboard(self._copy_text):
                self._marcar_copiado()
            return True
        if self._pressed_close:
            dentro = self._in_close_rect(x, y)
            self._pressed_close = False
            self.queue_draw()
            if dentro and self._on_close:
                self._on_close("user")
            return True
        if self._pressed_action_idx is not None:
            i = self._pressed_action_idx
            self._pressed_action_idx = None
            dentro = False
            if 0 <= i < len(self._action_rects):
                x0, y0, x1, y1, key = self._action_rects[i]
                dentro = x0 <= x <= x1 and y0 <= y <= y1
            self.queue_draw()
            if dentro and self._buttons_actionable and self._on_click:
                self._on_click(key)
            return True
        return False

    def toggle_expanded(self):
        self._expanded = not self._expanded
        self.queue_draw()
        if self._on_resize:
            self._on_resize(self.desired_height())

    def _strip_w(self):
        return self._CLOSE_RAIL_W

    def _eff_text_width(self):
        return _TEXT_COL_W - self._strip_w()

    def desired_height(self):
        h = WaylandPopup.calc_card_height(
            self._app_name, self._cuerpo, "",
            text_width=self._eff_text_width(), expanded=self._expanded,
            hide_title=self._hide_title, font_scale=self._font_scale,
            actions_count=len(self._actions),
            has_copy=bool(self._copy_text),
        )
        if self._image_pb is not None:
            h += 8 + 140
        return h

    def set_fraction(self, f):
        self._fraction = f
        self.queue_draw()

    def _wipe_x(self, w):
        return w * self._fraction

    def _frame(self, W, H):
        pad = _PAD
        text_col_x = pad + _IMAGE_LEFT_W + _IMAGE_LEFT_GAP
        strip_w = self._strip_w()
        fs = self._font_scale
        return _Frame(W=W, H=H, wx=self._wipe_x(W), pad=pad, strip_w=strip_w,
                      text_col_x=text_col_x,
                      text_col_w=W - text_col_x - pad - strip_w, fs=fs,
                      title_fs=max(9, round(_TITLE_FS * fs)),
                      body_fs=max(9, round(_BODY_FS * fs)),
                      app_fs=max(8, round(_APP_FS * fs)), r=_CARD_RADIUS)

    # ──Dibujo GSK ────────────────────────────────────────────────────────
    def _snapshot_background(self, s, fr):
        # Sombra difusa (estilo "card apoyada"), debajo de todo.
        s.append_outset_shadow(
            _rounded(0, 0, fr.W, fr.H, fr.r),
            _rgba(_VIB_SHADOW), 0, _VIB_SHADOW_DY, 0, _VIB_SHADOW_BLUR)
        # Hairline: rounded rect 1px mayor en color borde.
        _round_fill(s, 0, 0, fr.W, fr.H, fr.r, _VIB_BORDER)
        # Superficie: gradiente vertical con alpha ≥ 0.90.
        s.save()
        s.push_rounded_clip(_rounded(1, 1, fr.W - 2, fr.H - 2, fr.r - 1))
        s.append_linear_gradient(
            _rect(0, 0, fr.W, fr.H),
            Graphene.Point().init(0, 0), Graphene.Point().init(0, fr.H),
            [_stop(0.0, _VIB_TOP), _stop(1.0, _VIB_BOTTOM)])
        # Wipe: tinte sutil del acento en la parte ya transcurrida.
        if fr.wx < fr.W:
            bg = self._card_bg
            acc = self._accent_rgb
            blend = 0.15
            tint = (bg[0] + (acc[0] - bg[0]) * blend,
                    bg[1] + (acc[1] - bg[1]) * blend,
                    bg[2] + (acc[2] - bg[2]) * blend, 1.0)
            s.push_clip(_rect(fr.wx, 0, fr.W - fr.wx, fr.H))
            s.append_color(_rgba(tint), _rect(0, 0, fr.W, fr.H))
            s.pop()
        s.pop()
        s.restore()

    def _snapshot_image_left(self, s, fr, lay):
        offset = min(max((lay.piso - _IMAGE_LEFT_W) / 2, 0),
                     lay.row_h - _IMAGE_LEFT_W)
        cy = fr.pad + offset
        self._image_left_rect = (fr.pad, cy, fr.pad + _IMAGE_LEFT_W,
                                 cy + _IMAGE_LEFT_W)
        if self._image_left_pb is None:
            return
        s.save()
        s.push_rounded_clip(_rounded(fr.pad, cy, _IMAGE_LEFT_W,
                                     _IMAGE_LEFT_W, _IMAGE_LEFT_W / 2))
        s.append_texture(_texture(self._image_left_pb),
                         _rect(fr.pad, cy, _IMAGE_LEFT_W, _IMAGE_LEFT_W))
        s.pop()
        s.restore()

    def _snapshot_actions(self, s, fr, lay):
        self._action_rects = []
        n = len(self._actions)
        if not n:
            return
        actions_y = fr.pad + lay.piso + _ACTIONS_GAP
        x0, x1 = fr.pad, fr.W - fr.pad - fr.strip_w
        gap = 8
        seg_w = ((x1 - x0) - gap * (n - 1)) / n
        for i, (key, _label) in enumerate(self._actions):
            sx0 = x0 + i * (seg_w + gap)
            self._action_rects.append((sx0, actions_y, sx0 + seg_w,
                                       actions_y + _ACTIONS_ROW_H, key))
        for i, (key, label) in enumerate(self._actions):
            sx0, sy0, sx1, sy1, _ = self._action_rects[i]
            if self._pressed_action_idx == i:
                alpha = _VIB_BTN_PRESSED
            elif self._hover_action_idx == i:
                alpha = _VIB_BTN_HOVER
            else:
                alpha = _VIB_BTN_ALPHA
            _round_fill(s, sx0, sy0, sx1 - sx0, _ACTIONS_ROW_H, 8,
                        (1.0, 1.0, 1.0, alpha))
            # Brillo interior (affordance "física") y sombra que hunde.
            s.save()
            s.push_rounded_clip(_rounded(sx0, sy0, sx1 - sx0,
                                         _ACTIONS_ROW_H, 8))
            s.append_color(_rgba(_VIB_INSET),
                           _rect(sx0, sy0, sx1 - sx0, 1))
            if self._pressed_action_idx == i:
                _append_sink(s, sx0, sy0, sx1 - sx0)
            s.pop()
            s.restore()
            icono = self._action_icon_pbs.get(key)
            btn_fs = max(10, round(11 * fr.fs))
            fdesc = Pango.FontDescription("Manrope " + str(btn_fs))
            fdesc.set_weight(Pango.Weight.SEMIBOLD)
            lay_txt = _layout_for(
                label, fdesc,
                width=(sx1 - sx0) - 16 - (22 if icono else 0),
                ellipsize=True)
            ink, _ = lay_txt.get_pixel_extents()
            icon_w = _APP_ICON_BOX + 6 if icono else 0
            content_w = icon_w + ink.width
            tx = sx0 + ((sx1 - sx0) - content_w) / 2
            centro_y = sy0 + _ACTIONS_ROW_H / 2
            self._snapshot_text_clipped(
                s, fr, lay_txt, tx + icon_w,
                centro_y - (ink.y + ink.height / 2),
                self._left_title, _TXT_BANDA_R)
            if icono:
                s.save()
                s.push_rounded_clip(_rounded(
                    tx, sy0 + (_ACTIONS_ROW_H - _APP_ICON_BOX) / 2,
                    _APP_ICON_BOX, _APP_ICON_BOX, 3))
                s.append_texture(
                    _texture(icono),
                    _rect(tx, sy0 + (_ACTIONS_ROW_H - _APP_ICON_BOX) / 2,
                          _APP_ICON_BOX, _APP_ICON_BOX))
                s.pop()
                s.restore()

    _COPY_CONFIRM_MS = 1400

    def _copy_label(self):
        return "Copiado" if self._copy_done else "Copiar código"

    def _marcar_copiado(self):
        """Confirmación visual breve: el botón dice 'Copiado' 1.4 s."""
        self._copy_done = True
        self.queue_draw()
        GLib.timeout_add(self._COPY_CONFIRM_MS, self._fin_copiado)

    def _fin_copiado(self):
        self._copy_done = False
        self.queue_draw()
        return False

    def _snapshot_copy(self, s, fr, lay):
        """Botón local 'Copiar código/texto' anclado bajo el body.

        Reutiliza la banda de acciones (_ACTIONS_ROW_H): cuando ya hay botones
        D-Bus, se dibuja en la misma fila como un segmento adicional; cuando
        no los hay, ocupa la fila entera. No cambia ninguna métrica de layout.
        """
        self._copy_rect = None
        if not self._copy_text:
            return
        x0 = fr.pad
        x1 = fr.W - fr.pad - fr.strip_w
        row_y = fr.pad + lay.piso + _ACTIONS_GAP
        if self._actions:
            # Comparte renglón: a la derecha de los botones D-Bus.
            x0 = (self._action_rects[-1][2] + 8) if self._action_rects else x0
            if x1 - x0 < 60:
                return
        else:
            row_y = fr.pad + lay.piso + _ACTIONS_GAP
        self._copy_rect = (x0, row_y, x1, row_y + _ACTIONS_ROW_H)
        ax0, ay0, ax1, ay1 = self._copy_rect
        # Botón neutro: superficie blanca translúcida (sin tinte del acento,
        # que sobre la card sale verde) + hairline. El acento queda para el
        # wipe y la X de descarte.
        alpha = (_VIB_BTN_PRESSED if getattr(self, "_pressed_copy", False)
                 else _VIB_BTN_HOVER if getattr(self, "_hover_copy", False)
                 else _VIB_BTN_ALPHA)
        _round_fill(s, ax0, ay0, ax1 - ax0, _ACTIONS_ROW_H, 8,
                    (1.0, 1.0, 1.0, alpha))
        s.save()
        s.push_rounded_clip(_rounded(ax0, ay0, ax1 - ax0, _ACTIONS_ROW_H, 8))
        s.append_color(_rgba(_VIB_INSET), _rect(ax0, ay0, ax1 - ax0, 1))
        if getattr(self, "_pressed_copy", False):
            _append_sink(s, ax0, ay0, ax1 - ax0)
        s.pop()
        s.restore()
        label = self._copy_label()
        fs = max(10, round(12 * fr.fs))
        fdesc = Pango.FontDescription("Manrope " + str(fs))
        fdesc.set_weight(Pango.Weight.SEMIBOLD)
        lt = _layout_for(
            label, fdesc, width=(ax1 - ax0) - 16, ellipsize=True)
        ink, _ = lt.get_pixel_extents()
        tx = ax0 + ((ax1 - ax0) - ink.width) / 2
        centro = ay0 + _ACTIONS_ROW_H / 2
        self._snapshot_text_clipped(
            s, fr, lt, tx, centro - (ink.y + ink.height / 2),
            self._left_title, _TXT_BANDA_R)

    def _snapshot_expand_bar(self, s, fr, lay):
        self._expand_rect = None
        if not lay.has_more:
            return
        btn_y = fr.pad + lay.piso + _BTN_GAP
        if self._actions:
            btn_y += _ACTIONS_ROW_H + _ACTIONS_GAP
        bar_x0, bar_x1 = fr.pad, fr.W - fr.pad - fr.strip_w
        bar_w = bar_x1 - bar_x0
        self._expand_rect = (bar_x0, btn_y, bar_x1, btn_y + self._BTN_H)
        _round_fill(s, bar_x0, btn_y, bar_w, self._BTN_H, 8,
                    (1.0, 1.0, 1.0, _VIB_BTN_ALPHA))
        s.save()
        s.push_rounded_clip(_rounded(bar_x0, btn_y, bar_w, self._BTN_H, 8))
        s.append_color(_rgba(_VIB_INSET), _rect(bar_x0, btn_y, bar_w, 1))
        s.pop()
        s.restore()

        label = "Ver menos" if lay.expanded else "Ver más"
        btn_fs = max(9, round(11 * fr.fs))
        lay_txt = _layout_for(label, Pango.FontDescription("Manrope " + str(btn_fs)))
        ink, _ = lay_txt.get_pixel_extents()
        chev, gap = 10, 3
        content_w = ink.width + gap + chev
        tx0 = bar_x0 + (bar_w - content_w) / 2
        centro_y = btn_y + self._BTN_H / 2
        self._snapshot_text_clipped(
            s, fr, lay_txt, tx0,
            centro_y - (ink.y + ink.height / 2),
            self._left_title, _TXT_BANDA_R)
        path = Gsk.Path.parse(
            "M 0 3 L 5 -3 L 10 3 Z" if lay.expanded else "M 0 -3 L 5 3 L 10 -3 Z")
        s.save()
        s.translate(Graphene.Point().init(tx0 + ink.width + gap, centro_y))
        for clip_x, is_dark in ((fr.wx, False), (fr.W, True)):
            s.save()
            s.push_clip(_rect(0 if not is_dark else fr.wx - (tx0 + ink.width + gap),
                              0, clip_x, fr.H))
            s.append_stroke(path, Gsk.Stroke.new(1.5),
                            _rgba(_TXT_BANDA_R if is_dark else acc))
            s.pop()
            s.restore()
        s.restore()

    def _snapshot_text_clipped(self, s, fr, layout, x, y, light, dark):
        """Mismo texto en dos paletas, recortado a cada lado del wipe."""
        for clip_x, is_dark in ((fr.wx, False), (fr.W, True)):
            s.save()
            if is_dark:
                s.push_clip(_rect(fr.wx, 0, fr.W - fr.wx, fr.H))
            else:
                s.push_clip(_rect(0, 0, clip_x, fr.H))
            _append_text(s, layout, x, y, dark if is_dark else light)
            s.pop()
            s.restore()

    def _snapshot_text_passes(self, s, fr, lay):
        ty = fr.pad

        def draw_pass(s, is_dark):
            tcol = self._right_title if is_dark else self._left_title
            bcol = self._right_body if is_dark else self._left_body
            acol = self._right_app if is_dark else self._left_app
            yy = ty
            if self._app_name:
                if self._app_icon_pb:
                    s.save()
                    s.push_rounded_clip(_rounded(
                        fr.text_col_x, yy, _APP_ICON_BOX, _APP_ICON_BOX, 3))
                    s.append_texture(_texture(self._app_icon_pb),
                                     _rect(fr.text_col_x, yy,
                                           _APP_ICON_BOX, _APP_ICON_BOX))
                    s.pop()
                    s.restore()
                label = self._app_label or self._app_name
                tx = fr.text_col_x + 20
                lay_app = _layout_for(
                    label, Pango.FontDescription("Manrope " + str(fr.app_fs)),
                    width=fr.text_col_w - 20, ellipsize=True)
                ink, _ = lay_app.get_pixel_extents()
                centro = yy + _APP_ICON_BOX / 2
                _append_text(s, lay_app, tx, centro - (ink.y + ink.height / 2), acol)
                yy += _APP_ROW_H
            if not self._hide_title:
                lay_title = _layout_for(
                    self._titulo or "",
                    Pango.FontDescription("Manrope Bold " + str(fr.title_fs)),
                    width=fr.text_col_w, ellipsize=True)
                _append_text(s, lay_title, fr.text_col_x, yy + 2, tcol)
                yy += _TITLE_ROW_H
            lay_body = _body_layout(
                self._cuerpo, fr.body_fs, fr.text_col_w,
                max_lines=(0 if lay.expanded else lay.cap))
            # Con max_lines>0 el ellipsize lo aplica _layout_for.
            _append_text(s, lay_body, fr.text_col_x, yy, bcol)

        for is_dark in (False, True):
            s.save()
            if is_dark:
                s.push_clip(_rect(fr.wx, 0, fr.W - fr.wx, fr.H))
            else:
                s.push_clip(_rect(0, 0, fr.wx, fr.H))
            draw_pass(s, is_dark)
            s.pop()
            s.restore()

    def _snapshot_banner(self, s, fr, lay):
        if not self._image_pb:
            return
        iy = fr.pad + lay.row_h + 8
        ih, iw = 140, min(260, fr.W - fr.pad * 2)
        s.save()
        s.push_rounded_clip(_rounded(fr.pad, iy, iw, ih, 8))
        s.append_texture(_texture(self._image_pb), _rect(fr.pad, iy, iw, ih))
        s.append_linear_gradient(
            _rect(fr.pad, iy + ih - 30, iw, 30),
            Graphene.Point().init(0, iy + ih - 30),
            Graphene.Point().init(0, iy + ih),
            [_stop(0.0, (0, 0, 0, 0)), _stop(1.0, (0, 0, 0, 0.4))])
        s.pop()
        s.restore()

    def _snapshot_close_strip(self, s, fr):
        sw = self._CLOSE_RAIL_W
        sx0 = fr.W - sw
        self._close_rect = (sx0, 0, fr.W, fr.H)
        if self._hover_close or self._pressed_close:
            tint = ((0.86, 0.15, 0.15, 0.45) if self._pressed_close
                    else (0.86, 0.15, 0.15, 0.32))
            s.save()
            s.push_rounded_clip(_rounded(0, 0, fr.W, fr.H, fr.r))
            s.append_color(_rgba(tint), _rect(sx0, 0, sw, fr.H))
            s.pop()
            s.restore()
        mx, my = sx0 + sw / 2, fr.H / 2
        inset = 9   # 18 px: con 12 la X rozaba la esquina redondeada
        path = Gsk.Path.parse(
            "M %d %d L %d %d M %d %d L %d %d" % (
                mx - inset, my - inset, mx + inset, my + inset,
                mx + inset, my - inset, mx - inset, my + inset))
        alpha = (0.45 if self._pressed_close
                 else 0.95 if self._hover_close else 0.30)
        s.append_stroke(path, Gsk.Stroke.new(2.5),
                        _rgba(_hex_rgb("#f38ba8") + (alpha,)))


class WaylandPopup:
    """Popup layer-shell GTK4. La cola/FIFO la maneja el daemon."""

    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, margin=16, corner="top-right",
                 accent=DEFAULT_ACCENT, app_name="", app_icon="",
                 on_close=None, image_data_raw=None, on_click=None, urgency=1,
                 app_label=None, hide_title=False, actions=None,
                 action_icons=False, buttons_actionable=True):
        self.app_name = app_name
        self.app_icon = app_icon
        self.titulo = titulo
        self.cuerpo = cuerpo.replace("\\n", "\n").replace("\\t", "\t")
        self.icon_path = icon_path
        self.actions = actions
        self.action_icons = action_icons
        self.image_path = image_path
        self.image_data_raw = image_data_raw
        self.duration = duration
        self.margin = margin
        self._margins = {
            "top-right": (margin, margin, 0, 0),
            "top-left": (margin, 0, 0, margin),
            "bottom-right": (0, margin, margin, 0),
            "bottom-left": (0, 0, margin, margin),
        }
        self.corner = corner
        self.accent = accent
        self._closed = False
        self.window = None
        self._card = None
        self._start = 0
        self._on_close = on_close
        self._on_click = on_click
        self._buttons_actionable = buttons_actionable
        self.on_resized = None
        self._stack_margin = 0
        self._hover_credit_ms = 0
        self._loop = None
        self.urgency = urgency if urgency in (0, 1, 2) else 1
        self.app_label = app_label
        self.hide_title = hide_title
        if self.urgency == 0 and duration > 0:
            self.duration = int(duration * 0.7)
        elif self.urgency == 2 and duration > 0:
            self.duration = int(duration * 1.5)

    _EDGES = {
        "top": Gtk4LayerShell.Edge.TOP,
        "bottom": Gtk4LayerShell.Edge.BOTTOM,
        "left": Gtk4LayerShell.Edge.LEFT,
        "right": Gtk4LayerShell.Edge.RIGHT,
    }
    _ANCHOR_MAP = {
        "top-right": ("top", "right"),
        "top-left": ("top", "left"),
        "bottom-right": ("bottom", "right"),
        "bottom-left": ("bottom", "left"),
    }

    def _build_ui(self):
        if not Gtk4LayerShell.is_supported():
            raise RuntimeError("wlr_layer_shell no soportado")

        self.window = Gtk.Window()
        self.window.set_title(APP_NAME)
        self.window.set_name("notify-card")
        self.window.set_decorated(False)
        self.window.set_focusable(False)   # no roba el tipeo (layer shell)

        Gtk4LayerShell.init_for_window(self.window)
        if not Gtk4LayerShell.is_layer_window(self.window):
            raise RuntimeError("gtk4-layer-shell init falló")
        Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.TOP)
        Gtk4LayerShell.set_namespace(self.window, APP_ID)
        # Sin keyboard interactivity: no le roba el tipeo a la app activa.
        Gtk4LayerShell.set_keyboard_mode(
            self.window, Gtk4LayerShell.KeyboardMode.NONE)
        for e in self._ANCHOR_MAP.get(self.corner, ("top", "right")):
            Gtk4LayerShell.set_anchor(self.window, self._EDGES[e], True)
        self._apply_margins()
        # OJO: no llamar set_exclusive_zone(-1) (auto). En KWin/GTK4 deja la
        # superficie mapeada pero INVISIBLE. El default 0 es lo correcto para
        # un toast que no debe reservar espacio de panel.

        self._card = NotificationWidget(
            self.app_name, self.app_icon,
            self.titulo, self.cuerpo,
            self.icon_path, self.image_path,
            self.accent,
            self.image_data_raw,
            self._on_click,
            on_resize=self._resize_card,
            on_close=self._close,
            app_label=self.app_label, hide_title=self.hide_title,
            persistent=(self.duration == 0),
            actions=self.actions, action_icons=self.action_icons,
            buttons_actionable=self._buttons_actionable,
        )
        h = self._card.desired_height()
        self._card.set_size_request(_CARD_WIDTH, h)
        self.window.set_child(self._card)
        # GTK4 ignora set_size_request en toplevel: hay que fijar default_size
        # (si no, la layer-shell queda con allocation 0x0 y no se ve).
        self.window.set_default_size(_CARD_WIDTH, h)

    def stack_height(self):
        if self._card:
            return self._card.desired_height()
        return WaylandPopup.calc_card_height(
            self.app_name, self.cuerpo, self.image_path,
            text_width=_CARD_WIDTH - _PAD * 2,
            has_copy=bool(getattr(self._card, "_copy_text", None)))

    def _resize_card(self, new_h):
        if not self.window or not self._card:
            return
        self._card.set_size_request(_CARD_WIDTH, new_h)
        self.window.set_default_size(_CARD_WIDTH, new_h)
        self.window.queue_resize()
        if self.on_resized:
            self.on_resized()

    def _update_progress(self):
        if self._closed:
            return False
        if self.duration <= 0:
            return False
        if self._card and self._card._hover:
            self._hover_credit_ms = min(self._hover_credit_ms + 50, self.duration)
        elapsed = (time.monotonic() - self._start) * 1000 - self._hover_credit_ms
        remaining = max(0, self.duration - elapsed)
        self._card.set_fraction(remaining / self.duration)
        if remaining <= 0:
            self._close()
            return False
        return True

    @staticmethod
    def calc_card_height(app_name, cuerpo, image_path,
                         text_width=_TEXT_COL_W - _CLOSE_RAIL_W,
                         expanded=False, hide_title=False, font_scale=1.0,
                         actions_count=0, has_copy=False):
        """Altura de la card — DELEGA en `_layout_metrics` (fuente única).

        `has_copy` reserva la misma banda que los botones D-Bus: sin ella el
        botón Copiar se dibuja fuera del card y queda recortado."""
        _body_fs = max(9, round(_BODY_FS * font_scale))
        lay = _layout_metrics(
            cuerpo, text_width, _body_fs, app_name, hide_title, expanded,
            actions_count > 0 or has_copy, _IMAGE_LEFT_W,
            NotificationWidget._MAX_VISIBLE_LINES, NotificationWidget._BTN_H,
        )
        h = _PAD + lay.row_h + _PAD
        if image_path and os.path.exists(image_path):
            h += 8 + 140
        return h

    def set_stack_margin(self, offset):
        """Fija el OFFSET vertical de esta card dentro de la pila."""
        self._stack_margin = offset
        if self.window:
            self._apply_margins()

    def _apply_margins(self):
        if not self.window:
            return
        base_top, base_right, base_bottom, base_left = self._margins.get(
            self.corner, (16, 16, 0, 0))
        offset = self._stack_margin
        if "top" in self.corner:
            t, b = base_top + offset, base_bottom
        else:
            t, b = base_top, base_bottom + offset
        if t:
            Gtk4LayerShell.set_margin(self.window, self._EDGES["top"], t)
        if b:
            Gtk4LayerShell.set_margin(self.window, self._EDGES["bottom"], b)
        r, l = base_right, base_left
        if r:
            Gtk4LayerShell.set_margin(self.window, self._EDGES["right"], r)
        if l:
            Gtk4LayerShell.set_margin(self.window, self._EDGES["left"], l)
        if self._card is not None:
            anterior = getattr(self, "_margin_offset_aplicado", offset)
            self._margin_offset_aplicado = offset
            dy = (offset - anterior) if "top" in self.corner \
                else -(offset - anterior)
            if dy:
                self._card._sincronizar_hover_tras_desplazar(dy)

    def prepare(self):
        if not os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "sin WAYLAND_DISPLAY no hay layer-shell: nada que preparar")
        self._build_ui()
        # GTK4: present() mapea y eleva la surface (show() solo la hace visible;
        # sobre un browser maximizado KWin puede dejarla detrás).
        self.window.present()
        self._start = time.monotonic()
        GLib.timeout_add(50, self._update_progress)

    def _close(self, source="timeout", *a):
        """Cierra el toast comunicando la fuente simbólica del cierre."""
        if self._closed:
            return
        self._closed = True
        cb = self._on_close
        if self.window:
            self.window.destroy()
            self.window = None
        if self._loop and self._loop.is_running():
            self._loop.quit()
        if cb:
            cb(source)

    def show(self):
        self.prepare()
        self._loop = GLib.MainLoop()
        self._loop.run()
