import math
import os
import re
import ctypes
import configparser
import cairo
os.environ.setdefault('GDK_BACKEND', 'wayland')

import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, GtkLayerShell, GLib, Gdk, GdkPixbuf, Pango, PangoCairo

from app_info import APP_ID, APP_NAME


# ── Bundled font: Manrope (OFL) ──────────────────────────────────────
# Register TTFs with fontconfig at import time so Pango resolves "Manrope"
# WITHOUT installing the font system-wide. The .ttf files live in src/fonts/.
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

def _register_bundled_font():
    """Add Manrope-Regular.ttf and Manrope-Bold.ttf to the fontconfig app set.
    Idempotent: fontconfig de-dupes by file path. Safe if fontconfig is missing."""
    try:
        fc = ctypes.CDLL("libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        cfg = fc.FcConfigGetCurrent()
        for name in ("Manrope-Regular.ttf", "Manrope-Bold.ttf"):
            path = os.path.join(_FONT_DIR, name)
            if os.path.exists(path):
                fc.FcConfigAppFontAddFile(cfg, path.encode())
    except Exception:
        pass  # fallback: Pango uses whatever "Manrope" resolves to (likely nothing)

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
                        "StartupWMClass": cp.get("Desktop Entry", "StartupWMClass", fallback=""),
                    }
                    stem = f[:-8].lower()  # remove .desktop
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


def _find_desktop_file(app_name):
    if not app_name:
        return None

    if _desktop_cache is None:
        _rebuild_desktop_cache()

    key = app_name.lower().strip()

    # 1) exact match (filename, wm class, or name)
    if key in _desktop_cache:
        return _desktop_cache[key][0]["path"]

    # 2) substring match on keys
    for k, entries in _desktop_cache.items():
        if key in k or k in key:
            return entries[0]["path"]

    # 3) substring match on Name or WMClass
    for k, entries in _desktop_cache.items():
        for e in entries:
            nm = e["Name"].lower()
            wm = e["StartupWMClass"].lower()
            if key in nm or key in wm:
                return e["path"]

    # 4) word-level: all words in key appear in Name or WMClass
    words = {w.strip("()-_. ").lower() for w in key.replace("-", " ").replace("_", " ").split()}
    words -= {""}
    if len(words) > 1:
        for entries in _desktop_cache.values():
            for e in entries:
                text = (e["Name"] + " " + e["StartupWMClass"]).lower()
                text_words = {w.strip("()-_. ").lower() for w in text.replace("-", " ").replace("_", " ").split()}
                if words.issubset(text_words):
                    return e["path"]

    return None


def _get_app_icon_from_desktop(app_name, size=80, mode="cover"):
    """Icono de la app desde .desktop, SOLO con match EXACTO.

    (Igual regla que _get_app_display_name: el match difuso de _find_desktop_file
    resuelve "brave" al primer PWA instalado —brave-<appid>.desktop— y el toast
    mostraba el icono de la web app xat. Exacto o nada → cae al tema.)

    `mode` se pasa al `_resample` del path absoluto: el logo de 16px pide
    "contain" (sin recortes) y la imagen izquierda de 80px el default
    "cover"."""
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
    """Resuelve el .desktop con match EXACTO (stem/WMClass/Name), sin substring.

    Devuelve path o None. Es la única vía segura: los PWA de navegador
    (brave-<appid>.desktop) tienen prefijos que rompen el match difuso."""
    if not app_name:
        return None
    if _desktop_cache is None:
        _rebuild_desktop_cache()
    entries = _desktop_cache.get(app_name.lower().strip())
    if entries:
        return entries[0]["path"]
    return None


def _get_app_display_name(app_name):
    """Nombre visible de la app.

    Usa SOLO match EXACTO (stem/WMClass/Name) contra los .desktop. El match
    difuso por substring de _find_desktop_file es un arma de doble filo: "brave"
    cae en el primer PWA instalado (brave-<appid>.desktop, ej "xat de masha") y
    todas las notificaciones de Brave muestran ese nombre. Si no hay match
    exacto, mostrar el app_name crudo que manda el sender (ej: "Brave").
    """
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
# Hosts desnudos: dominios (xat.com, www.foo.com/path) e IP:puerto (127.0.0.1:8766).
# Brave inyecta el link del sitio como primera línea del body
# (<a href="URL">HOST</a>) — con sanitize queda el host pelado; hay que sacarlo.
_BARE_HOST_RE = re.compile(
    # Dominios: cada label arranca con letra (evita versiones "0.1.0.tar.gz")
    r'(?<![\w./-])(?:[a-z][\w-]*\.)+[a-z]{2,}(?::\d+)?(?:/[^\s<>"\'\)\]]*)?'
    r'|\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/[^\s<>"\'\)\]]*)?',
    re.IGNORECASE,
)


def _strip_urls(text):
    """Quita URLs del TEXTO VISIBLE del body (las notificaciones son un botón:
    el destino se usa para el click, no se muestra).

    - http(s)://... (texto plano)
    - hosts desnudos (xat.com, 127.0.0.1:8766): Brave inyecta el URL del sitio
      como primera línea del body; además, el set_height+ellipsize de Pango con
      ese salto explícito colapsa TODO el body a esa única línea (el body real
      no se veía). Sacarlo arregla ambas cosas.
    - NO toca URLs dentro de atributos de markup (ej: <a href="URL">label</a>)
    - Colapsa saltos de línea seguidos (\n\n\n → \n).
    """
    if not text:
        return text
    parts = re.split(r'(<[^>]*>)', text)
    out = "".join(
        (_BARE_HOST_RE.sub("", _URL_RE.sub("", part)) if not part.startswith("<") else part)
        for part in parts
    )
    # Limpiar <a> que quedaron vacíos tras quitar el host/label
    out = re.sub(r'<a\s+[^>]*>\s*</a>', '', out)
    return re.sub(r'\n{2,}', '\n', out).strip("\n")


def _icon_from_theme(icon_name, size=16):
    """Icono del tema hicolor/Breeze por nombre.

    El lookup de IconTheme es case-sensitive y los senders mandan app_name
    capitalizado ("Brave", "YouTube") mientras los iconos del tema viven en
    minúsculas ("brave"). Sin el reintento en minúsculas el slot izquierdo
    quedaba vacío en apps reconocibles (reporte)."""
    if not icon_name:
        return None
    attempts = [icon_name]
    lowered = icon_name.lower()
    if lowered != icon_name:
        attempts.append(lowered)
    for attempt in attempts:
        try:
            # En Wayland, Gtk.IconTheme.get_default() a menudo no resuelve el
            # tema (no tiene screen asociada) y devuelve None. Usar
            # get_for_screen() con la screen por defecto es lo correcto en GTK3.
            screen = Gdk.Screen.get_default()
            if screen is not None:
                theme = Gtk.IconTheme.get_for_screen(screen)
            else:
                theme = Gtk.IconTheme.new()
            info = theme.lookup_icon(attempt, size, 0)
            if info:
                return info.load_icon()
        except Exception:
            pass
    return None


def _extract_markup_url(text):
    """Extrae el href del primer <a href="..."> en un body con markup.
    Devuelve la URL o '' si no hay. (body-hyperlinks support)"""
    if not text or "<a " not in text:
        return ""
    import re
    m = re.search(r'<a\s+[^>]*href=["\']([^"\']+)["\']', text, re.IGNORECASE)
    if m:
        url = m.group(1)
        if url.startswith(("http://", "https://", "mailto:", "tel:")):
            return url
    return ""


_CARD_WIDTH = 360
_TEXT_COL_W = _CARD_WIDTH - 14 - 80 - 12 - 14  # 240: pad, icon, gap, pad

# ── Métricas de layout — FUENTE ÚNICA ──────────────────────────────────────
# _draw (posiciones) y calc_card_height/_eff_text_width (medición de alto y
# ancho) consumen estas constantes + _rows_above_body. Si el stack se computa
# "por separado", el render desborda o deja slack — bug real cazado por
# tests/test_layout_consistency.py (la barra flotaba 8px y, sin app_name,
# desbordaba la card 30px).
_PAD = 14            # padding interior del card
_IMAGE_LEFT_W = 80   # slot izquierdo de imagen (siempre presente)
_IMAGE_LEFT_GAP = 12 # gap slot → columna de texto
_ROW_MIN_H = 80      # alto mínimo de la fila (el slot de 80 px define el piso)
_APP_ROW_H = 20      # fila del app-name
_APP_ICON_BOX = 16   # slot cuadrado del logo de app en la fila de app
_TITLE_ROW_H = 22    # fila del título
_BTN_GAP = 8         # gap body → barra expandir
_CARD_RADIUS = 12    # radio del card

# Tamaños de fuente NOMINALES del card — fuente única: los consumen `_draw`
# (dibujado) y `calc_card_height` (medición del alto), los dos escalados por
# `font_scale`. Antes cada uno hardcodeaba los suyos (11/11 en `_draw` con slot,
# 13 en `calc_card_height`): al ser siempre el slot la columna medía una cosa y
# se dibujaba otra, y la barra "Ver más" dejaba de anclar al padding inferior.
_TITLE_FS = 11
_BODY_FS = 11
_APP_FS = 10

# Placeholder del logo de 16px (último eslabón de la cadena de iconos):
# square de la surface Catppuccin del toast + inicial en el color de la fila de
# app. El slot nunca queda vacío y el layout de la fila no depende de si el
# logo resolvió o no.
_PLACEHOLDER_BG = "#313244"
_PLACEHOLDER_FG = "#a6adc8"


def _rows_above_body(app_name, hide_title):
    """Filas apiladas por encima del body — fuente única del stack.

    _draw la usa para posicionar (yy/body_top) y calc_card_height para
    reservar altura; ambos deben pasar por acá o divergen. Con el slot de
    imagen izquierda siempre presente (spec `toast-imagen-izquierda`) el stack
    es el MISMO para todos los toasts: no existe el respiro condicional que
    solo se sumaba en la variante sin imagen, así que la distancia app→título
    es idéntica venga la imagen que venga."""
    rows = 0
    if app_name:
        rows += _APP_ROW_H
    if not hide_title:
        rows += _TITLE_ROW_H
    return rows

# Tags de markup que Pango SOPORTA de verdad. Pango NO conoce <a> ni <img>:
# mandarle un body con <a href> a set_markup rompe el parseo (warning
# "Unknown tag 'a'") y el texto deja de envolverse. Por eso se sanitizan.
_PANGO_TAGS = ("b>", "i>", "u>", "s>", "big>", "small>", "tt>", "sub>",
               "sup>", "span", "strikethrough>")


def _sanitize_pango_markup(text):
    """Convierte markup de body (freedesktop 1.2) a markup que Pango entienda.

    - <a href="URL">label</a> → label plano (SIN subrayado ni color de link).
      El toast ES el botón: el único propósito es el click (action/URL que ya
      extrae el daemon). No hay links internos, nada de <a href> visible.
    - Devuelve el texto tal cual si no hay tags reconocibles."""
    import re
    text = re.sub(
        r'<a\s+[^>]*>(.*?)</a>',
        r'\1',
        text, flags=re.S | re.I)
    return text


def _has_pango_markup(text):
    """True si el texto contiene al menos una tag de markup que Pango soporta."""
    return "<" in text and any(t in text for t in _PANGO_TAGS)


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _body_metrics(cuerpo, width, font_size=13, max_lines=None):
    """Mide el layout del body: (líneas visuales, altura_px lógica).

    - Si `max_lines` es >0, aplica el mismo cap de altura + ellipsis que
      _draw_text (colapsado) y devuelve la altura CAPPED — que es la que
      realmente vemos dibujada.
    - Si `max_lines` es None, devuelve la altura natural (todo el wrap).

    Sin display (headless): Pango.Context() necesito el font_map de PangoCairo
    (imprescindible para medir estilos; un Context() pelado no envuelve). El
    markup/wrap coincide con _draw_text, así card height y botón anclan justo
    debajo del texto (solve del solape body↔botón)."""
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        return 0, 0
    cuerpo = _sanitize_pango_markup(cuerpo)
    ctx = Pango.Context()
    ctx.set_font_map(PangoCairo.font_map_get_default())
    layout = Pango.Layout(ctx)
    fd = Pango.FontDescription("Manrope " + str(font_size))
    layout.set_font_description(fd)
    if _has_pango_markup(cuerpo):
        try:
            layout.set_markup(cuerpo, -1)
        except Exception:
            layout.set_text(cuerpo, -1)
    else:
        layout.set_text(cuerpo, -1)
    layout.set_width(int(max(1.0, width) * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    if max_lines:
        layout.set_height(max_lines * int(font_size * 1.6 * Pango.SCALE))
        layout.set_ellipsize(Pango.EllipsizeMode.END)
    lines = layout.get_line_count()
    _, logical = layout.get_pixel_extents()
    return lines, max(0.0, logical.height)


def _count_body_lines(cuerpo, width, font_size=13):
    """Líneas visuales si el body se muestra COMPLETO (sin cap)."""
    return _body_metrics(cuerpo, width, font_size)[0]


def _make_circular(pixbuf, size):
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
    """Escala al slot `size`×`size` con HYPER.

    Reporte: los iconos (imagen izquierda de 80px y logo de app 16px) se veían
    blandos en pequeño — los rescale usaban BILINEAR. HYPER es nítido al reducir
    y considerablemente más limpio al agrandar favicons chicos al slot de la
    imagen izquierda (medido en el repo: upscale 32→80 HYPER +12% energía de
    borde).

    `mode` decide qué se hace con los iconos NO cuadrados:
      - "cover" (default): recorta el cuadrado central y escala. Es lo correcto
        para la imagen izquierda de 80px, cuyo clip circular es por diseño.
      - "contain": escala preservando el aspect ratio y composita centrado
        sobre un pixbuf transparente (letterbox). Es lo del logo de 16px: con
        cover, un icono panorámico perdía sus extremos laterales dentro del
        slot (el center-crop del cuadrado central se comía el logo entero).
    """
    w, h = pixbuf.get_width(), pixbuf.get_height()
    if w == size and h == size:
        return pixbuf
    if mode == "contain":
        escala = min(size / w, size / h)
        nw = max(1, int(round(w * escala)))
        nh = max(1, int(round(h * escala)))
        scaled = pixbuf.scale_simple(nw, nh, interp)
        out = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
        out.fill(0x00000000)          # bandas transparentes del letterbox
        scaled.copy_area(0, 0, nw, nh, out,
                         (size - nw) // 2, (size - nh) // 2)
        return out
    if w != h:
        s = min(w, h)
        pixbuf = GdkPixbuf.Pixbuf.new_subpixbuf(
            pixbuf, (w - s) // 2, (h - s) // 2, s, s)
    return pixbuf.scale_simple(size, size, interp)


def _make_placeholder_icon(label, size=16):
    """Placeholder del logo de la fila de app: square redondeado de la surface
    del toast con la INICIAL del nombre de la app.

    Se sintetiza al final de la cadena (si nada resuelve) para que el slot de
    16 px nunca quede vacío — la fila sin logo perdía su punto de anclaje y el
    offset del texto quedaba condicional. Va en `__init__` (no en `_draw`) para
    fluir por el mismo camino de dibujado que un logo real, y así el layout de
    la fila es idéntico en ambos casos.
    """
    import cairo as _c
    surface = _c.ImageSurface(_c.FORMAT_ARGB32, size, size)
    ctx = _c.Context(surface)
    ctx.set_source_rgba(*_hex_rgb(_PLACEHOLDER_BG))
    r = max(3, size // 4)          # radio del square
    r = min(r, size / 2)
    ctx.arc(size - r, r, r, 3 * math.pi / 2, 2 * math.pi)
    ctx.arc(size - r, size - r, r, 0, math.pi / 2)
    ctx.arc(r, size - r, r, math.pi / 2, math.pi)
    ctx.arc(r, r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    ctx.fill()
    inicial = (label or "").strip()[:1].upper() or "?"
    ctx.select_font_face("Manrope", _c.FONT_SLANT_NORMAL, _c.FONT_WEIGHT_BOLD)
    ctx.set_font_size(round(size * 0.56))          # ~9 px en un slot de 16
    ctx.set_source_rgba(*_hex_rgb(_PLACEHOLDER_FG))
    ext = ctx.text_extents(inicial)
    # Centrado por la CAJA de tinta (no por la advance): el ink box va de
    # y_bearing (negativo) a y_bearing+height, así el baseline queda en
    # (size-h)/2 - y_bearing. Centrar por la advance dejaría las iniciales con
    # descendente ("Q", "J") más altas que el resto.
    ctx.move_to((size - ext[4]) / 2 - ext[0],
                (size - ext[3]) / 2 - ext[1])
    ctx.show_text(inicial)
    surface.flush()
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


class NotificationWidget(Gtk.DrawingArea):
    # Constantes de layout / colapso
    _MAX_VISIBLE_LINES = 3      # líneas visibles del body antes de colapsar
    _BTN_H = 28                 # alto de la franja expandir/contraer (target de toque holgado)
    _CLOSE_STRIP_W = 44         # ancho de la franja vertical de descarte (persistentes)

    # Fuente: Manrope (geométrica, moderna). Empaquetada en src/fonts/ y
    # registrada via fontconfig al importar (sin instalar system-wide).
    # Más legible que Cantarell a tamaños chicos en fondo oscuro.
    # Tamaños NOMINALES: el tamaño real de cada fila lo escalan `_draw` y
    # `calc_card_height` desde las constantes de módulo (_TITLE_FS/_BODY_FS/
    # _APP_FS), que son la fuente única del par dibujado/medido.
    _BODY_FONT = "Manrope 11"
    _TITLE_FONT = "Manrope Bold 11"
    _APP_FONT = "Manrope 10"
    _BTN_FONT_SIZE = 10         # botón Ver más/menos + pill de cerrar

    def __init__(self, app_name, app_icon, titulo, cuerpo, icon_path, image_path, accent,
                 image_data_raw=None, on_click=None, on_resize=None, on_close=None,
                 app_label=None, hide_title=False, persistent=False):
        super().__init__()
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # ── Screen-resolution-aware font scaling ──────────────────────
        # On small screens (low-res / HiDPI unscaled) the same px font sizes
        # look proportionally larger. Shrink fonts so the toast reads right
        # regardless of display resolution.
        #   width < 1280  → scale 0.85  (small laptop / low-res)
        #   width < 1600  → scale 0.92  (medium)
        #   width >= 1600 → scale 1.0   (full HD / 4K)
        try:
            sw = screen.get_width()
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
        # Caja del slot de imagen izquierda, la publica _draw (como
        # _expand_rect): permite comprobar que la barra "Ver más" full-width no
        # le pisa encima.
        self._image_left_rect = None
        self._on_resize = on_resize
        self._fraction = 1.0
        self._on_click = on_click
        self._on_close = on_close
        self._persistent = persistent
        self._hover = False            # mouse sobre el card
        self._hover_close = False     # mouse sobre el pill de cerrar
        self._close_rect = None       # (x0, y0, x1, y1) del pill de cerrar
        # Label de app compuesto: "Brave - <tab>" (navegadores). Con hide_title,
        # el título va dentro del label y no se dibuja como línea aparte.
        self._app_label = app_label
        self._hide_title = hide_title
        self._app_name = _get_app_display_name(app_name)
        self._titulo = (titulo or "").replace("\n", " ").replace("\t", " ").strip()
        # El URL se usa para el click (ya lo extrae el daemon del body/hints);
        # en el TEXTO VISIBLE no se muestra (las notificaciones son un botón).
        self._cuerpo = _strip_urls(cuerpo)
        self._accent_rgb = _hex_rgb(accent)
        self._card_bg = _hex_rgb("#1e1e2e")

        # Left (uncovered) - normal colors
        # Título más claro que el body (#e6e9f2 vs #cdd6f4) para jerarquía
        self._left_title = _hex_rgb("#e6e9f2")
        self._left_body = _hex_rgb("#cdd6f4")
        self._left_app = _hex_rgb("#a6adc8")

        # Right (covered by green wipe) - readable on dark green
        self._right_title = _hex_rgb("#d4edd4")
        self._right_body = _hex_rgb("#c8e6c8")
        self._right_app = _hex_rgb("#8cb88c")
        self._app_icon_pb = None
        self._image_left_pb = None
        self._image_pb = None

        # Logo de 16px de la fila de app: cadena archivo → .desktop exacto →
        # tema por app_icon → tema por app_name. TODO pasa por contain (los
        # iconos no cuadrados no se cortan; el tema además devuelve p.ej. 32x32
        # para un slot de 16, que sin reescalar se dibujaba recortado).
        if app_icon and os.path.exists(app_icon):
            try:
                self._app_icon_pb = _resample(
                    GdkPixbuf.Pixbuf.new_from_file(app_icon), 16, mode="contain")
            except Exception:
                pass

        if not self._app_icon_pb:
            icon_from_desktop = _get_app_icon_from_desktop(
                app_name, 16, mode="contain")
            if icon_from_desktop:
                self._app_icon_pb = _resample(icon_from_desktop, 16, mode="contain")
            else:
                theme_icon = (_icon_from_theme(app_icon, 16)
                              or _icon_from_theme(app_name, 16))
                if theme_icon:
                    self._app_icon_pb = _resample(theme_icon, 16, mode="contain")

        # Último eslabón: si nada resolvió, se sintetiza el placeholder (con la
        # inicial del nombre de la app). Así el slot de 16 px nunca queda vacío
        # y el offset del texto de la fila puede ser una CONSTANTE — el layout
        # no se mueve entre un logo resuelto y uno sintetizado.
        if not self._app_icon_pb:
            self._app_icon_pb = _make_placeholder_icon(self._app_name, 16)

        if icon_path and os.path.exists(icon_path):
            try:
                raw = GdkPixbuf.Pixbuf.new_from_file(icon_path)
                self._image_left_pb = _make_circular(raw, _IMAGE_LEFT_W)
            except Exception:
                pass

        # El slot de la IZQUIERDA muestra el ICONO DEL TAB (lo que manda el
        # navegador como image-data). Antes image-data iba al banner grande
        # (favicon gigante estirado) y el slot caía al icono de escritorio
        # (Brave). Ahora el image-data es el primer eslabón de la cadena.
        if not self._image_left_pb and image_data_raw:
            try:
                w, h, rowstride, has_alpha, bps, n_channels, data = image_data_raw
                raw = GdkPixbuf.Pixbuf.new_from_bytes(
                    GLib.Bytes.new(data),
                    GdkPixbuf.Colorspace.RGB,
                    has_alpha,
                    bps,
                    w, h,
                    rowstride,
                )
                self._image_left_pb = _make_circular(raw, _IMAGE_LEFT_W)
            except Exception:
                pass

        # Segundo eslabón: sin icono del sender (image-data, image-path,
        # app_icon archivo), el slot izquierdo cae al icono de la app — match
        # EXACTO de .desktop (logo de Brave; el Name de los .desktop PWA cubre
        # "YouTube" sin match difuso), luego el tema hicolor. Los directos de
        # YouTube llegan vía service-worker SOLO con summary/body, y sin este
        # paso el slot izquierdo quedaba vacío (bug reportado).
        if not self._image_left_pb:
            icon_from_desktop = _get_app_icon_from_desktop(
                app_name, _IMAGE_LEFT_W)
            if icon_from_desktop:
                self._image_left_pb = _make_circular(
                    icon_from_desktop, _IMAGE_LEFT_W)
            if not self._image_left_pb:
                theme_icon = (_icon_from_theme(app_icon, _IMAGE_LEFT_W)
                              or _icon_from_theme(app_name, _IMAGE_LEFT_W))
                if theme_icon:
                    self._image_left_pb = _make_circular(
                        theme_icon, _IMAGE_LEFT_W)

        # Último eslabón de la cadena del slot: si NADA resolvió (ni imagen de la
        # notificación ni icono de app), se sintetiza el placeholder con la
        # INICIAL del nombre de la app — el mismo lenguaje visual del logo de
        # 16 px, escalado al slot y pasado por el clip circular como cualquier
        # otro contenido. El slot deja de poder quedar vacío, y con él la
        # variante de layout "sin imagen" (columna ancha, fuentes 12/13, gap del
        # HR): un toast sin icono resoluble se ve igual de coherente que el resto
        # (spec `toast-imagen-izquierda`, "La imagen izquierda siempre está
        # presente").
        if not self._image_left_pb:
            self._image_left_pb = _make_circular(
                _make_placeholder_icon(self._app_name, _IMAGE_LEFT_W),
                _IMAGE_LEFT_W)

        # Banner grande: SOLO image-path (imagen real de la app, ej: descarga).
        # image-data ya no va acá (es el icono, no una imagen para agrandar).
        if image_path and os.path.exists(image_path):
            try:
                self._image_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    image_path, 260, 140, True)
            except Exception:
                pass

        self.connect("draw", self._draw)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("button-press-event", self._on_button_press)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("motion-notify-event", self._on_motion)

    def _on_enter(self, widget, event):
        self._hover = True
        self._set_cursor_hand()
        self.queue_draw()
        self._resize_por_hover()

    def _on_leave(self, widget, event):
        self._hover = False
        self._hover_close = False
        self._set_cursor(False)
        self.queue_draw()
        self._resize_por_hover()

    def _resize_por_hover(self):
        """Redimensiona el card si el cambio de hover altera el wrap.

        Al entrar/salir del hover de un persistente la franja reclama (o
        devuelve) sus 44 px y el texto re-wrappea: si eso cambia el número de
        líneas, el alto requerido también. Se reutiliza la vía de resize ya
        existente (la de `toggle_expanded` → `on_resize` → `_resize_card`), y
        solo se dispara cuando el alto REALmente cambió: un body de 1-2 líneas
        no cambia de líneas al pasar de 332 a 288 y no genera ningún resize
        (sin esto, cada hover de un card chico sería un loop de eventos).
        """
        if not self._persistent or not self._on_resize:
            return
        h = self.desired_height()
        if h != self.get_size_request()[1]:
            self._on_resize(h)

    def _puntero_en_card(self):
        """¿Está el puntero dentro de este card? Una de:
          - `(True, x, y)`  → puntero dentro, coords locales del card.
          - `(False, 0, 0)` → puntero FUERA del card (consultado con éxito).
          - `None`          → NO se pudo consultar (sin seat/ventana): el
                              llamador debe dejar el estado de hover como está.

        Usa `Gdk.Window.get_device_position(device)`: devuelve la ventana bajo
        el puntero y las coords locales; si el puntero no está sobre ESTA
        window, devuelve `None` como primer valor. Es la vía correcta bajo
        Wayland (las GdkWindow de layer-shell no tienen get_origin fiable).
        """
        try:
            win = self.get_window()
            if win is None:
                return None
            display = self.get_display()
            seat = display.get_default_seat() if display else None
            pointer = seat.get_pointer() if seat else None
            if pointer is None:
                return None
            hit, x, y, _mask = win.get_device_position(pointer)
            if hit is None:
                return (False, 0, 0)   # consultado OK, puntero fuera
            return (True, x, y)
        except Exception:
            return None

    def _sincronizar_hover_tras_desplazar(self, dy):
        """Re-evalúa el hover tras un desplazamiento vertical de la window.

        Wayland/KWin NO entrega `leave-notify` cuando la surface se aparta de
        un puntero quieto: al reflowear la pila (cerrarse un toast vecino) el
        card se mueve con el cursor encima y la franja/X quedaban pegadas sin
        que llegara ningún evento (bug verificado en vivo, task 6.2).

        El margen de la pila mueve la window un delta vertical CONOCIDO, así
        que en vez de esperar un evento que no llega, se consulta dónde está el
        puntero y se decide con el delta: si quedó fuera, se resetea el hover
        (y el alto vuelve al de sin franja); si sigue dentro, se mantiene.

        `dy` > 0 = la window bajó (margen top crece); `dy` < 0 = subió (margen
        bottom crece).
        """
        pos = self._puntero_en_card()
        if pos is None:
            return                      # no consultable: no tocar el estado
        ok, x, y = pos
        if ok:
            # El tamaño de la window layer-shell es el del size request del card
            # (ver _build_ui / _resize_card). get_size_request devuelve -1 si
            # nunca se fijó, y el allocation headless es 1x1 (degradado) → no
            # sirven como fallback directo.
            req_w, req_h = self.get_size_request()
            w = req_w if req_w > 0 else (self.get_allocated_width() or _CARD_WIDTH)
            h = req_h if req_h > 0 else (self.get_allocated_height()
                                         or self.desired_height())
            # El puntero no se movió; el card se movió dy → en coords del card
            # el puntero queda a y - dy.
            dentro = (0 <= x < w) and (0 <= y - dy < h)
        else:
            dentro = False             # consultado y el puntero quedó fuera
        if dentro == self._hover:
            return
        self._hover = dentro
        if dentro:
            self._set_cursor_hand()
        else:
            self._hover_close = False
            self._set_cursor(False)
        self.queue_draw()
        self._resize_por_hover()

    def _on_motion(self, widget, event):
        if not self._persistent:
            return
        over_close = self._in_close_rect(event.x, event.y)
        if over_close != self._hover_close:
            self._hover_close = over_close
            self._set_cursor(over_close)
            self.queue_draw()

    def _set_cursor_hand(self):
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(
                self.get_display(), "pointer"))

    def _set_cursor(self, hand):
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(
                self.get_display(), "pointer" if hand else "default"))

    def _in_close_rect(self, x, y):
        if not self._close_rect:
            return False
        x0, y0, x1, y1 = self._close_rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def _on_button_press(self, widget, event):
        # Click en el pill de cerrar (X) → cierra el toast (solo persistentes).
        # NO dispara on_click/ActionInvoked: es cierre manual del usuario.
        if self._persistent and self._in_close_rect(event.x, event.y):
            if self._on_close:
                self._on_close()
            return True
        # Click en la franja Expandir/Contraer → toggle el estado (consume el evento)
        if self._expand_rect:
            x0, y0, x1, y1 = self._expand_rect
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.toggle_expanded()
                return True
        if self._on_click:
            self._on_click()
        return True

    def toggle_expanded(self):
        self._expanded = not self._expanded
        self.queue_draw()
        if self._on_resize:
            self._on_resize(self.desired_height())

    def _strip_w(self):
        """Ancho que la franja de descarte RECLAMA en el estado actual (0 o 44).

        ÚNICA autoridad del gate hover-dependiente: la consumen `_eff_text_width`
        (medición del wrap), `_draw` (columna de texto, barra y dibujado de la
        franja) y el hit-rect de cierre. La franja solo existe en persistentes
        y solo con el puntero encima: sin hover NO se dibuja (cero píxeles de
        tinte/X) y su ancho NO se reserva (la columna de texto queda completa).
        """
        if self._persistent and self._hover:
            return self._CLOSE_STRIP_W
        return 0

    def _eff_text_width(self):
        """Ancho real de la columna de texto en el estado actual.

        Con el slot de imagen izquierda SIEMPRE presente (spec
        `toast-imagen-izquierda`, "Columna de texto única") la columna es una
        sola para todos los toasts: 360 − 14 − 80 − 12 − 14 = 240. Antes un
        toast sin imagen resuelta se iba a ancho completo (~332) con otras
        fuentes, y la barra "Ver más" aterrizaba en otro lugar.
        Persistentes CON hover: menos el ancho de la franja de descarte (44px),
        que _draw reserva para que el texto no quede bajo el tinte. Sin hover
        la franja no se dibuja y no se le cede ancho al texto."""
        return _TEXT_COL_W - self._strip_w()

    def desired_height(self):
        """Altura en el estado actual (colapsado/expandido/hover) para
        redimensionar la window. Incluye la altura del banner de imagen si el
        widget lo tiene cargado (equivale a lo que calc_card_height suma
        cuando existe image_path).

        `text_width` es el ancho EFECTIVO de la columna (ya con la franja
        descontada si corresponde), así que la altura y el wrap de `_draw`
        nunca divergen."""
        h = WaylandPopup.calc_card_height(
            self._app_name, self._cuerpo, "",
            text_width=self._eff_text_width(), expanded=self._expanded,
            hide_title=self._hide_title, font_scale=self._font_scale,
        )
        if self._image_pb is not None:
            h += 8 + 140
        return h

    def set_fraction(self, f):
        self._fraction = f
        self.queue_draw()

    def _wipe_x(self, w):
        return w * self._fraction

    def _draw_text(self, cr, text, x, y, w, font_size, light_col, dark_col, bold=False, max_lines=2):
        layout = PangoCairo.create_layout(cr)
        fd = Pango.FontDescription("Manrope " + str(font_size))
        if bold:
            fd.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(fd)
        # Soportar markup (body-markup): <b>, <i>, <u> y <a href> (sanitizado a span)
        text = _sanitize_pango_markup(text)
        if _has_pango_markup(text):
            try:
                layout.set_markup(text, -1)
            except Exception:
                layout.set_text(text, -1)
        else:
            layout.set_text(text, -1)
        layout.set_width(int(w * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

        if max_lines > 0:
            layout.set_height(max_lines * int(font_size * 1.6 * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)

        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)
        ink, logical = layout.get_pixel_extents()

    def _draw(self, widget, cr):
        alloc = self.get_allocation()
        W, H = alloc.width, alloc.height
        if W < 10 or H < 10:
            return
        # Clear inicial con OPERATOR_CLEAR: deja la superficie transparente
        # (RGBA) y evita artifacts de buffering (cajas negras) cuando el card
        # redondeado no cubre la ventana POPUP entera (esquinas).
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.restore()
        wx = self._wipe_x(W)
        pad = _PAD
        # El slot de imagen izquierda está SIEMPRE (spec
        # `toast-imagen-izquierda`): la cadena termina en el placeholder con la
        # inicial, así que la columna de texto no depende de qué resolviera.
        icon_size = _IMAGE_LEFT_W
        text_col_x = pad + icon_size + _IMAGE_LEFT_GAP
        # Persistentes CON hover: la franja vertical de descarte (44px) se
        # RESERVA en la columna de texto — el texto nunca queda debajo del
        # tint. Sin hover la franja no se dibuja y no se le cede ancho.
        strip_w = self._strip_w()
        text_col_w = W - text_col_x - pad - strip_w

        # Fuentes nominales por fila, escaladas por resolución
        # (self._font_scale). Las MISMAS constantes mide calc_card_height: si
        # divergieran, la barra "Ver más" dejaría de anclar al padding inferior.
        fs = self._font_scale
        _title_fs = max(9, round(_TITLE_FS * fs))
        _body_fs = max(9, round(_BODY_FS * fs))
        _app_fs = max(8, round(_APP_FS * fs))

        # Helper: rounded rect path (clockwise, outer corners)
        def rrect(cr, x, y, w, h, r):
            r = min(r, w / 2, h / 2)
            cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
            cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
            cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
            cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
            cr.close_path()

        r = 12   # radio card: 8→12 (más moderno/redondeado, Linear usa 8-12)

        # Background — hover aclara levemente el alpha (feedback "estás sobre esto")
        bg_alpha = 0.92 if self._hover else 0.85
        cr.set_source_rgba(self._card_bg[0], self._card_bg[1], self._card_bg[2], bg_alpha)
        rrect(cr, 0, 0, W, H, r)
        cr.fill()

        # Wipe: clip to card shape, fill right portion
        if wx < W:
            # Tinte SUTIL: mezcla del acento hacia el fondo de la card (no un
            # bloque oscuro plano). blend=0.15 => variación leve del fondo.
            bg = self._card_bg
            acc = self._accent_rgb
            blend = 0.15
            dr = bg[0] + (acc[0] - bg[0]) * blend
            dg = bg[1] + (acc[1] - bg[1]) * blend
            db = bg[2] + (acc[2] - bg[2]) * blend
            cr.save()
            rrect(cr, 0, 0, W, H, r)
            cr.clip()
            cr.rectangle(wx, 0, W - wx, H)
            cr.set_source_rgb(dr, dg, db)
            cr.fill()
            cr.restore()

        # --- Layout: real wrapped line count (coincide con _draw) ---
        total_lines = _count_body_lines(self._cuerpo, text_col_w, _body_fs)
        expanded = self._expanded
        cap = min(total_lines, self._MAX_VISIBLE_LINES)
        if expanded:
            _, body_h = _body_metrics(self._cuerpo, text_col_w, _body_fs, max_lines=None)
        else:
            _, body_h = _body_metrics(self._cuerpo, text_col_w, _body_fs, max_lines=cap)
        has_more = total_lines > self._MAX_VISIBLE_LINES   # overflow => mostrar botón (debe persistir al expandir para poder contraer)

        text_h = _rows_above_body(self._app_name, self._hide_title)
        text_h += body_h
        if has_more:
            text_h += self._BTN_H + _BTN_GAP   # franja del botón expandir/contraer
        # Piso de la fila: coincide con calc_card_height (max con 80) — el slot
        # de imagen izquierda sigue respirando con contenido corto.
        row_h = max(text_h, icon_size, _ROW_MIN_H)

        # Imagen izquierda (slot de 80 px, clip circular). El pixbuf YA viene
        # circular (lo recorta _make_circular); el blit rect es transparente en
        # las esquinas. Sin anillo (rediseño: cero líneas).
        #
        # Se centra contra el BLOQUE DE TEXTO, no contra la fila entera: la barra
        # "Ver más" es full-width por diseño (anti-misclick) y ocupa la banda de
        # abajo de la MISMA fila, así que centrar contra todo el alto hundía el
        # slot hasta que la barra le pintaba encima con 3+ líneas de body.
        # `content_h` excluye la barra; el clamp mantiene el slot dentro de la
        # fila cuando el texto es más corto que el slot.
        content_h = text_h - (self._BTN_H + _BTN_GAP if has_more else 0)
        offset_slot = min(max((content_h - icon_size) / 2, 0), row_h - icon_size)
        cy = pad + offset_slot
        self._image_left_rect = (pad, cy, pad + icon_size, cy + icon_size)
        Gdk.cairo_set_source_pixbuf(cr, self._image_left_pb, pad, cy)
        cr.rectangle(pad, cy, icon_size, icon_size)
        cr.fill()

        # --- Text in two passes ---
        # El bloque de texto arranca AL TOP de la fila, alineado con el borde
        # superior del slot (spec `toast-imagen-izquierda`). Antes se centraba
        # con `(row_h - text_h) / 2` y, con el piso de 80 px del slot, la fila
        # de app y el título quedaban hundidos ~10 px. El slot conserva su
        # centrado `cy`; el sobrante queda bajo el body.
        ty = pad

        def draw_text_pass(cr, clip_x, is_dark):
            if clip_x < 0:
                return
            if is_dark:
                tcol = self._right_title
                bcol = self._right_body
                acol = self._right_app
            else:
                tcol = self._left_title
                bcol = self._left_body
                acol = self._left_app

            yy = ty
            if self._app_name:
                # App icon (logo resuelto o placeholder): el slot siempre está
                # lleno, así que el offset del texto es una constante.
                if self._app_icon_pb:
                    Gdk.cairo_set_source_pixbuf(cr, self._app_icon_pb, text_col_x, yy)
                    cr.rectangle(text_col_x, yy, _APP_ICON_BOX, _APP_ICON_BOX)
                    cr.fill()
                cr.set_source_rgb(*acol)
                # Label de app (puede ser "Brave - <tab>") con elipsis real de Pango
                label = self._app_label or self._app_name
                # tx = text_col_x + 20 (logo 16 + 4): constante, nunca condicional
                # al logo (fija tests/test_placeholder_icono.py).
                tx = text_col_x + 20
                ll = PangoCairo.create_layout(cr)
                ll.set_font_description(Pango.FontDescription("Manrope " + str(_app_fs)))
                ll.set_text(label, -1)
                ll.set_width(int(max(1, text_col_w - tx + text_col_x) * Pango.SCALE))
                ll.set_ellipsize(Pango.EllipsizeMode.END)
                # El texto se CENTRA en el logo: se mide su CAJA DE TINTA real y
                # se la alinea con la línea media del slot de 16 px. Con un
                # desplazamiento fijo el texto caía ~5 px bajo el centro (y la
                # base se salía del icono), y el error crecía con cada cambio
                # de fuente. `PangoCairo.show_layout` ancla la esquina superior
                # izquierda de la caja, no la baseline: por eso el centro se
                # corrige con los extents de tinta y no con `y + ascent`.
                # Mismo criterio que el centrado de la inicial en
                # `_make_placeholder_icon`.
                ink, _logical = ll.get_pixel_extents()
                centro_logo = yy + _APP_ICON_BOX / 2
                cr.move_to(tx, centro_logo - (ink.y + ink.height / 2))
                PangoCairo.show_layout(cr, ll)
                yy += _APP_ROW_H

            if not self._hide_title:
                cr.set_source_rgb(*tcol)
                # Título con elipsis Pango (antes cr.show_text: se salía del card)
                ll = PangoCairo.create_layout(cr)
                ll.set_font_description(Pango.FontDescription("Manrope Bold " + str(_title_fs)))
                ll.set_text(self._titulo or "", -1)
                ll.set_width(int(text_col_w * Pango.SCALE))
                ll.set_ellipsize(Pango.EllipsizeMode.END)
                cr.move_to(text_col_x, yy + 2)
                PangoCairo.show_layout(cr, ll)
                yy += _TITLE_ROW_H

            # Body con wrap real + ellipsis cuando colapsa
            cr.set_source_rgb(*bcol)
            self._draw_text(cr, self._cuerpo, text_col_x, yy, text_col_w, _body_fs,
                            bcol, bcol, bold=False,
                            max_lines=(0 if expanded else cap))

        # Botón expandir/contraer (si hay overflow), una sola pasada
        self._expand_rect = None
        if has_more:
            # body_top = MISMA fuente que el flujo de texto (yy). Antes este
            # bloque recomputaba las filas a mano: sumaba el gap del HR sin
            # fijarse en app_name (desbordaba 30px) y no aplicaba _BTN_GAP
            # (la barra flotaba 8px sobre el padding inferior).
            body_top = ty + _rows_above_body(self._app_name,
                                             self._hide_title)
            btn_y = body_top + body_h + _BTN_GAP
            btn_h = self._BTN_H
            label = "Ver menos" if expanded else "Ver más"
            accent_r, accent_g, accent_b = self._accent_rgb

            # Barra FULL-WIDTH: TODO el ancho interior de la card es clickeable
            # (anti-misclick: antes solo el pill compacto de la derecha). En
            # persistentes termina antes de la franja de descarte (sin overlap).
            bar_x0 = pad
            bar_x1 = W - pad - strip_w
            bar_w = bar_x1 - bar_x0
            self._expand_rect = (bar_x0, btn_y, bar_x1, btn_y + btn_h)

            # Contenido (label + chevrón) CENTRADO en la barra
            cr.select_font_face("Manrope", 0, 0)
            cr.set_font_size(max(9, round(11 * fs)))
            ext = cr.text_extents(label)
            fe = cr.font_extents()
            chev_size, chev_gap = 10, 3
            content_w = ext[4] + chev_gap + chev_size
            tx0 = bar_x0 + (bar_w - content_w) / 2

            for clip_x, is_dark in ((wx, False), (W - wx, True)):
                if clip_x <= 0:
                    continue
                cr.save()
                if clip_x < W:
                    cr.rectangle((0 if not is_dark else wx), 0,
                                 (clip_x if not is_dark else W - wx), H)
                    cr.clip()
                # Sin stroke de contorno; el affordance lo da el fill 22%
                # (subido de 18% al quitar el borde).
                cr.set_source_rgba(accent_r, accent_g, accent_b, 0.22)
                rrect(cr, bar_x0, btn_y, bar_w, btn_h, 8)
                cr.fill()
                if is_dark:  # dark pass: texto en la parte cubierta
                    cr.set_source_rgb(0.85, 0.95, 0.85)
                else:
                    cr.set_source_rgb(*self._left_title)
                base_y = btn_y + btn_h / 2 + (fe[0] - fe[1]) / 2
                cr.move_to(tx0, base_y)
                cr.show_text(label)
                # Chevrón relleno (triángulo) a la derecha del texto, centrado en la barra.
                # Convención: colapsado "Ver más" ▼ (más abajo), expandido "Ver menos" ▲
                cx0 = tx0 + ext[4] + chev_gap
                cy = btn_y + btn_h / 2
                if expanded:
                    cr.move_to(cx0, cy + 3)       # ▲ apunta arriba (colapsar)
                    cr.line_to(cx0 + chev_size / 2, cy - 3)
                    cr.line_to(cx0 + chev_size, cy + 3)
                else:
                    cr.move_to(cx0, cy - 3)       # ▼ apunta abajo (expandir)
                    cr.line_to(cx0 + chev_size / 2, cy + 3)
                    cr.line_to(cx0 + chev_size, cy - 3)
                cr.close_path()
                cr.set_source_rgb(*self._accent_rgb)   # chevrón en color acento (visible)
                cr.fill()
                cr.restore()

        # Draw light text in left portion (uncovered)
        cr.save()
        cr.rectangle(0, 0, wx, H)
        cr.clip()
        draw_text_pass(cr, wx, False)
        cr.restore()

        # Draw dark text in right portion (covered)
        cr.save()
        cr.rectangle(wx, 0, W - wx, H)
        cr.clip()
        draw_text_pass(cr, wx, True)
        cr.restore()

        # Image at bottom
        if self._image_pb:
            iy = pad + row_h + 8
            ih = 140
            iw = min(260, W - pad * 2)
            img_radius = 8
            cr.save()
            rrect(cr, pad, iy, iw, ih, img_radius)
            cr.clip()
            Gdk.cairo_set_source_pixbuf(cr, self._image_pb, pad, iy)
            cr.paint()
            # fade sutil hacia el fondo en el borde inferior
            grad = cairo.LinearGradient(0, iy + ih - 30, 0, iy + ih)
            grad.add_color_stop_rgba(0, 0, 0, 0, 0)
            grad.add_color_stop_rgba(1, 0, 0, 0, 0.4)
            cr.set_source(grad)
            cr.paint()
            cr.restore()

        # --- Franja de descarte vertical — solo persistentes + hover ---
        # 44px de ancho × altura del card (antes: pill 28x28 en la esquina,
        # imposible no misclickear: el fall-through abría el video/URL).
        # El gate vive en _strip_w (mismo que la reserva de arriba): sin hover
        # no se dibuja NADA de la franja. El ancho YA está reservado en
        # text_col_w — el texto nunca queda debajo del tint. El click routing
        # (_on_button_press) prioriza la franja sobre expandir y sobre
        # on_click, sin fall-through.
        # Hover directo: tint más sólido (0.18 -> 0.32), igual feedback que
        # tenía el pill.
        self._close_rect = None
        if strip_w:
            sw = self._CLOSE_STRIP_W
            sx0 = W - sw
            self._close_rect = (sx0, 0, W, H)
            cr.save()
            # Cairo: save/restore NO guarda el path actual (no es parte del
            # graphics state), así que un sub-path residual de bloques previos
            # (texto Pango, wipe clip...) sobreviviría al restore y el
            # próximo stroke/fill lo dibujaría como "línea fantasma".
            # new_path() descarta cualquier sub-path huérfano de este frame.
            cr.new_path()
            # Clip al card redondeado: el tint respeta las esquinas curvas.
            rrect(cr, 0, 0, W, H, r)
            cr.clip()
            if self._hover_close:
                cr.set_source_rgba(0.86, 0.15, 0.15, 0.32)   # hover directo: más sólido
            else:
                cr.set_source_rgba(0.86, 0.15, 0.15, 0.18)   # normal hover del card
            cr.rectangle(sx0, 0, sw, H)
            cr.fill()
            # Pixel-center: translate 0.5px so the X strokes land on
            # pixel boundaries (elimina el blur sub-pixel de strokes centrados
            # en coords enteras; sin esto los bordes se pixelan con fringed
            # AA que se lee como ghosting).
            cr.translate(0.5, 0.5)
            # X con dos trazos stroke (no fill): más limpio que path cerrado.
            # ANTIALIAS_NONE en la X: los round caps a 2.5px crean fringed
            # semi-transparent pixels (blur). Sin AA la X es nítida y el
            # pixel-center (translate 0.5) mantiene las esquinas alineadas.
            mx = sx0 + sw / 2
            my = H / 2
            inset = 7
            cr.set_antialias(cairo.ANTIALIAS_NONE)
            cr.set_source_rgba(0.953, 0.482, 0.659, 0.95)   # #f38ba8
            cr.set_line_width(2.5)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(mx - inset, my - inset)
            cr.line_to(mx + inset, my + inset)
            cr.move_to(mx + inset, my - inset)
            cr.line_to(mx - inset, my + inset)
            cr.stroke()
            cr.restore()


class WaylandPopup:
    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, margin=16, corner="top-right", accent="#89b4fa",
                 app_name="", app_icon="", on_close=None, image_data_raw=None,
                 on_click=None, urgency=1, app_label=None, hide_title=False):
        self.app_name = app_name
        self.app_icon = app_icon
        self.titulo = titulo
        self.cuerpo = cuerpo.replace("\\n", "\n").replace("\\t", "\t")
        self.icon_path = icon_path
        self.image_path = image_path
        self.image_data_raw = image_data_raw
        self.duration = duration
        self.margin = margin
        self.corner = corner
        self.accent = accent
        self._closed = False
        self.window = None
        self._card = None
        self._start = 0
        self._on_close = on_close
        self._on_click = on_click
        # Hook POST-resize: lo inyecta el manager para re-flowear la pila
        # cuando este card cambia de alto (spec `toast-stack`). None = nadie
        # escucha (uso one-shot).
        self.on_resized = None
        self._stack_margin = 0

        # Urgency (spec freedesktop 1.2): 0=low, 1=normal, 2=critical
        self.urgency = urgency if urgency in (0, 1, 2) else 1
        self.app_label = app_label
        self.hide_title = hide_title
        # Ajustes por nivel de urgencia (respeta duration=0 => nunca expirar)
        if self.urgency == 0:
            # low: más tenue y corto
            self._bg_alpha = 0.55
            if duration > 0:
                self.duration = int(duration * 0.7)
        elif self.urgency == 2:
            # critical: opaco y persistente (no expirar si duration<=0)
            self._bg_alpha = 1.0
            if duration > 0:
                self.duration = int(duration * 1.5)
        else:
            # normal: comportamiento actual
            self._bg_alpha = 0.85

    _EDGES = {
        "top": GtkLayerShell.Edge.TOP,
        "bottom": GtkLayerShell.Edge.BOTTOM,
        "left": GtkLayerShell.Edge.LEFT,
        "right": GtkLayerShell.Edge.RIGHT,
    }
    _ANCHOR_MAP = {
        "top-right": ("top", "right"),
        "top-left": ("top", "left"),
        "bottom-right": ("bottom", "right"),
        "bottom-left": ("bottom", "left"),
    }
    _MARGIN_MAP = {
        "top-right": (16, 16, 0, 0),
        "top-left": (16, 0, 0, 16),
        "bottom-right": (0, 16, 16, 0),
        "bottom-left": (0, 0, 16, 16),
    }

    def _build_ui(self):
        if not GtkLayerShell.is_supported():
            raise RuntimeError("wlr_layer_shell no soportado")

        self.window = Gtk.Window.new(Gtk.WindowType.POPUP)
        self.window.set_title(APP_NAME)
        self.window.set_name("notify-card")
        self.window.set_app_paintable(True)
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

        GtkLayerShell.init_for_window(self.window)
        if not GtkLayerShell.is_layer_window(self.window):
            raise RuntimeError("gtk-layer-shell init falló")
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.TOP)
        # Namespace para que tools de ventana (kdotool, wlr-tools) identifiquen
        # la superficie layer-shell aunque no sea ventana gestionada por KWin.
        GtkLayerShell.set_namespace(self.window, APP_ID)
        GtkLayerShell.try_force_commit(self.window)

        for e in self._ANCHOR_MAP.get(self.corner, ("top", "right")):
            GtkLayerShell.set_anchor(self.window, self._EDGES[e], True)

        self._apply_margins()
        GtkLayerShell.set_exclusive_zone(self.window, -1)

        CARD_WIDTH = 360
        if CARD_WIDTH:
            self.window.set_size_request(CARD_WIDTH, -1)

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
        )
        h = self._card.desired_height() if self._card else WaylandPopup.calc_card_height(
            self.app_name, self.cuerpo, self.image_path)
        self._card.set_size_request(CARD_WIDTH, h)
        self.window.add(self._card)
        if not self._on_close:
            self.window.connect("destroy", lambda *a: Gtk.main_quit())
        self.window.connect("key-press-event", lambda *a: self._close())

    def stack_height(self):
        """Alto con el que esta card ocupa su hueco en la pila.

        Es la altura REAL que el card pide (post-resize), no la que tenía cuando
        se apiló: la pila la suma para calcular los offsets de los de abajo
        (spec `toast-stack`, "La pila nunca solapa"). Sin card no hay estado de
        hover (nunca se ha dibujado): se estima con la columna COMPLETA — el
        mismo valor que daría `_eff_text_width` sin hover (ver `_strip_w`).
        """
        if self._card:
            return self._card.desired_height()
        return WaylandPopup.calc_card_height(
            self.app_name, self.cuerpo, self.image_path,
            text_width=_CARD_WIDTH - _PAD * 2)

    def _resize_card(self, new_h):
        """Redimensiona la window (layer-shell) al alto pedido por toggle expandir/contraer.

        Al final avisa a `on_resized`: el manager re-flowea la pila entera con el
        alto nuevo (spec `toast-stack`). El orden importa —primero se redimensiona
        esta card, después se repositionan las demás— para que `stack_height()` de
        esta popup ya devuelva el alto nuevo cuando se sumen los offsets.
        """
        if not self.window or not self._card:
            return
        self._card.set_size_request(_CARD_WIDTH, new_h)
        self.window.set_size_request(_CARD_WIDTH, new_h)
        self.window.queue_resize()
        self.window.show_all()          # reactiva layout
        GtkLayerShell.try_force_commit(self.window)
        if self.on_resized:
            self.on_resized()

    def _update_progress(self):
        if self._closed:
            return False
        # Persistent (duration=0): no hay barra de progreso ni auto-cierre.
        # El usuario cierra con la X (hover → pill rojizo).
        if self.duration <= 0:
            return False
        elapsed = (time.time() - self._start) * 1000
        remaining = max(0, self.duration - elapsed)
        self._card.set_fraction(remaining / self.duration)
        if remaining <= 0:
            self._close()
            return False
        return True

    @staticmethod
    def calc_card_height(app_name, cuerpo, image_path, text_width=_TEXT_COL_W,
                         expanded=False, hide_title=False, font_scale=1.0):
        """Altura de la card según el wrap REAL del cuerpo.

        `text_width` es el ancho EFECTIVO de la columna de texto (card 360 − pad
        14 − slot 80 − gap 12 − pad 14 = 240). Antes se contaban líneas físicas
        (split "\\n") y el texto desbordaba el borde; ahora se cuentan las
        líneas visuales envolviéndolo. Si `expanded`, se muestran todas las
        líneas; si no, se limitan a _MAX_VISIBLE_LINES y se reserva la franja
        del botón.
        NO resta la franja de descarte: el caller pasa el ancho ya efectivo
        (`NotificationWidget._eff_text_width`, que descuenta los 44px solo con
        hover) — restarla aquí además sería la divergencia altura/wrap que este
        docstring prohíbe.
        `font_scale` aplica la misma escala de resolución que usa _draw, y el
        tamaño de fuente sale de `_BODY_FS` — la MISMA constante que dibuja el
        body. Con el slot de imagen izquierda siempre presente no hay dos
        variantes de stack que medir: una sola columna, una sola fuente."""
        _body_fs = max(9, round(_BODY_FS * font_scale))
        total = _count_body_lines(cuerpo, text_width, _body_fs)
        text_h = _rows_above_body(app_name, hide_title)
        if expanded:
            _, body_h = _body_metrics(cuerpo, text_width, _body_fs, max_lines=None)
        else:
            cap = min(total, NotificationWidget._MAX_VISIBLE_LINES)
            _, body_h = _body_metrics(cuerpo, text_width, _body_fs, max_lines=cap)
        text_h += body_h
        if total > NotificationWidget._MAX_VISIBLE_LINES:
            text_h += NotificationWidget._BTN_H + _BTN_GAP
        row_h = max(text_h, _ROW_MIN_H)
        h = _PAD + row_h + _PAD
        if image_path and os.path.exists(image_path):
            h += 8 + 140
        return h

    def set_stack_margin(self, offset):
        """Fija el OFFSET vertical (px) de esta card dentro de la pila.

        El offset lo calcula el manager sumando las alturas REALES de las cards de
        arriba más el gap (spec `toast-stack`): por eso es un desplazamiento ya
        acumulado y no un índice — con alturas distintas, `índice × alto_propio`
        solapaba las cards.
        """
        self._stack_margin = offset
        if self.window:
            self._apply_margins()

    def _apply_margins(self):
        if not self.window:
            return
        base_top, base_right, base_bottom, base_left = self._MARGIN_MAP.get(self.corner, (16, 16, 0, 0))
        offset = self._stack_margin
        if "top" in self.corner:
            t, b = base_top + offset, base_bottom
        else:
            t, b = base_top, base_bottom + offset
        if t: GtkLayerShell.set_margin(self.window, self._EDGES["top"], t)
        if b: GtkLayerShell.set_margin(self.window, self._EDGES["bottom"], b)
        r, l = base_right, base_left
        if r: GtkLayerShell.set_margin(self.window, self._EDGES["right"], r)
        if l: GtkLayerShell.set_margin(self.window, self._EDGES["left"], l)

        # La window se acaba de MOVER (reflow de la pila). Con un puntero quieto
        # encima, KWin no entrega leave-notify → la franja/X quedan pegadas.
        # Como el margen mueve la ventana un delta vertical conocido, se
        # re-sincroniza el hover del card con ese delta (ver
        # _sincronizar_hover_tras_desplazar).
        if self._card is not None:
            anterior = getattr(self, "_margin_offset_aplicado", offset)
            self._margin_offset_aplicado = offset
            # margen top crece → la window baja; margen bottom crece → sube.
            dy = (offset - anterior) if "top" in self.corner \
                else -(offset - anterior)
            if dy:
                self._card._sincronizar_hover_tras_desplazar(dy)

    def prepare(self):
        if not os.environ.get("WAYLAND_DISPLAY"):
            print("[wayland] No WAYLAND_DISPLAY", file=__import__('sys').stderr)
            return
        self._build_ui()
        self.window.show_all()
        self._start = time.time()
        GLib.timeout_add(50, self._update_progress)

    def _close(self, *a):
        if self._closed:
            return
        self._closed = True
        cb = self._on_close
        if self.window:
            self.window.destroy()
            self.window = None
        if cb:
            cb()

    def show(self):
        self.prepare()
        Gtk.main()
