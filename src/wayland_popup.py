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


def _get_app_icon_from_desktop(app_name, size=80):
    """Icono de la app desde .desktop, SOLO con match EXACTO.

    (Igual regla que _get_app_display_name: el match difuso de _find_desktop_file
    resuelve "brave" al primer PWA instalado —brave-<appid>.desktop— y el toast
    mostraba el icono de la web app xat. Exacto o nada → cae al tema.)"""
    path = _exact_desktop_file(app_name)
    if not path:
        return None
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        icon_name = cp.get("Desktop Entry", "Icon", fallback="")
        if icon_name:
            if icon_name.startswith("/") and os.path.exists(icon_name):
                raw = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_name, size, size, True)
                if raw:
                    return raw
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
    if not icon_name:
        return None
    try:
        # En Wayland, Gtk.IconTheme.get_default() a menudo no resuelve el
        # tema (no tiene screen asociada) y devuelve None. Usar
        # get_for_screen() con la screen por defecto es lo correcto en GTK3.
        screen = Gdk.Screen.get_default()
        if screen is not None:
            theme = Gtk.IconTheme.get_for_screen(screen)
        else:
            theme = Gtk.IconTheme.new()
        info = theme.lookup_icon(icon_name, size, 0)
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
    s = min(pixbuf.get_width(), pixbuf.get_height())
    square = GdkPixbuf.Pixbuf.new_subpixbuf(
        pixbuf, (pixbuf.get_width() - s) // 2,
        (pixbuf.get_height() - s) // 2, s, s)
    scaled = square.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    surface = _c.ImageSurface(_c.FORMAT_ARGB32, size, size)
    ctx = _c.Context(surface)
    ctx.arc(size / 2, size / 2, size / 2, 0, 2 * 3.14159)
    ctx.clip()
    Gdk.cairo_set_source_pixbuf(ctx, scaled, 0, 0)
    ctx.paint()
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


class NotificationWidget(Gtk.DrawingArea):
    # Constantes de layout / colapso
    _MAX_VISIBLE_LINES = 3      # líneas visibles del body antes de colapsar
    _BTN_H = 20                 # alto de la franja del botón expandir/contraer

    # Fuente: Manrope (geométrica, moderna). Empaquetada en src/fonts/ y
    # registrada via fontconfig al importar (sin instalar system-wide).
    # Más legible que Cantarell a tamaños chicos en fondo oscuro.
    _BODY_FONT = "Manrope 13"
    _TITLE_FONT = "Manrope Bold 12"
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
        self._avatar_pb = None
        self._image_pb = None

        if app_icon and os.path.exists(app_icon):
            try:
                self._app_icon_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    app_icon, 16, 16, True)
            except Exception:
                pass

        if not self._app_icon_pb:
            icon_from_desktop = _get_app_icon_from_desktop(app_name, 16)
            if icon_from_desktop:
                self._app_icon_pb = icon_from_desktop.scale_simple(16, 16, GdkPixbuf.InterpType.BILINEAR)
            else:
                self._app_icon_pb = _icon_from_theme(app_icon, 16)
                if not self._app_icon_pb:
                    self._app_icon_pb = _icon_from_theme(app_name, 16)

        if icon_path and os.path.exists(icon_path):
            try:
                raw = GdkPixbuf.Pixbuf.new_from_file(icon_path)
                self._avatar_pb = _make_circular(raw, 80)
            except Exception:
                pass

        # Avatar = ICONO DEL TAB (lo que manda el navegador como image-data).
        # Antes image-data iba al banner grande (favicon gigante estirado) y el
        # slot izquierdo caía al icono de escritorio (Brave). Ahora: image-data
        # primero; sin imagen real → SIN slot (no se reserva espacio por nada).
        if not self._avatar_pb and image_data_raw:
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
                self._avatar_pb = _make_circular(raw, 80)
            except Exception:
                pass

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

    def _on_leave(self, widget, event):
        self._hover = False
        self._hover_close = False
        self.queue_draw()

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

    def _eff_text_width(self):
        """Ancho real de la columna de texto en el estado actual.

        Con avatar: 360 - 14 - 80 - 12 - 14 = 240 (igual que _TEXT_COL_W).
        Sin avatar (no hay imagen): texto a ancho completo (~332)."""
        base = _CARD_WIDTH - 14 - 14
        if self._avatar_pb:
            base -= 80 + 12
        return base

    def desired_height(self):
        """Altura en el estado actual (colapsado/expandido) para redimensionar la window.
        Incluye la altura del banner de imagen si el widget lo tiene cargado (equivale
        a lo que calc_card_height suma cuando existe image_path)."""
        h = WaylandPopup.calc_card_height(
            self._app_name, self._cuerpo, "",
            text_width=self._eff_text_width(), expanded=self._expanded,
            hide_title=self._hide_title, font_scale=self._font_scale,
            has_avatar=bool(self._avatar_pb),
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
        wx = self._wipe_x(W)
        pad = 14
        gap = 12
        # Slot izquierdo SOLO si hay avatar real (icono del tab). Sin imagen:
        # no se reserva espacio (texto a ancho completo).
        icon_size = 80 if self._avatar_pb else 0
        text_col_x = pad + icon_size + (gap if icon_size else 0)
        text_col_w = W - text_col_x - pad

        # Circle-cut (avatar) steals ~80px of horizontal space: shrink body &
        # summary fonts so the same text stays legible at the narrower width.
        # Also apply screen-resolution scaling (self._font_scale).
        has_avatar = bool(self._avatar_pb)
        fs = self._font_scale
        _title_fs = max(9, round((11 if has_avatar else 12) * fs))
        _body_fs = max(9, round((11 if has_avatar else 13) * fs))
        _app_fs = max(8, round(10 * fs))

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

        # Subtle translucent edge (shadow-like) — borde sutil blanco estilo Linear
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.5)
        rrect(cr, 0.5, 0.5, W - 1, H - 1, r)
        cr.stroke()

        # --- Layout: real wrapped line count (coincide con _draw) ---
        total_lines = _count_body_lines(self._cuerpo, text_col_w, _body_fs)
        expanded = self._expanded
        cap = min(total_lines, self._MAX_VISIBLE_LINES)
        if expanded:
            _, body_h = _body_metrics(self._cuerpo, text_col_w, _body_fs, max_lines=None)
        else:
            _, body_h = _body_metrics(self._cuerpo, text_col_w, _body_fs, max_lines=cap)
        has_more = total_lines > self._MAX_VISIBLE_LINES   # overflow => mostrar botón (debe persistir al expandir para poder contraer)

        text_h = 0
        if self._app_name:
            text_h += 20
        if not self._hide_title:
            text_h += 22
        text_h += body_h
        if has_more:
            text_h += self._BTN_H + 8   # franja del botón expandir/contraer
        row_h = max(text_h, icon_size)

        # Avatar (slot izquierdo, centrado verticalmente) — solo si hay imagen real.
        # El pixbuf YA viene circular (lo recorta _make_circular); el blit rect es
        # transparente en las esquinas. Se agrega un anillo sutil en el borde.
        if self._avatar_pb:
            cy = pad + (row_h - icon_size) / 2
            Gdk.cairo_set_source_pixbuf(cr, self._avatar_pb, pad, cy)
            cr.rectangle(pad, cy, icon_size, icon_size)
            cr.fill()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.15)
            cr.set_line_width(1.0)
            cr.arc(pad + icon_size / 2, cy + icon_size / 2, icon_size / 2 - 0.5,
                   0, 2 * math.pi)
            cr.stroke()

        # --- Text in two passes ---
        ty = pad + (row_h - text_h) / 2
        hr_info = None  # coordenadas del HR, calculadas en draw_text_pass, trazadas 1 vez afuera

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
                # App icon
                if self._app_icon_pb:
                    Gdk.cairo_set_source_pixbuf(cr, self._app_icon_pb, text_col_x, yy)
                    cr.rectangle(text_col_x, yy, 16, 16)
                    cr.fill()
                cr.set_source_rgb(*acol)
                # Label de app (puede ser "Brave - <tab>") con elipsis real de Pango
                label = self._app_label or self._app_name
                tx = text_col_x + (20 if self._app_icon_pb else 0)
                ll = PangoCairo.create_layout(cr)
                ll.set_font_description(Pango.FontDescription("Manrope " + str(_app_fs)))
                ll.set_text(label, -1)
                ll.set_width(int(max(1, text_col_w - tx + text_col_x) * Pango.SCALE))
                ll.set_ellipsize(Pango.EllipsizeMode.END)
                cr.move_to(tx, yy + 3)
                PangoCairo.show_layout(cr, ll)
                yy += 20

            # Barely-visible hairline under the app_name row (separation cue)
            if self._app_name:
                # Sin avatar: el separador ocupa TODO el ancho de la card
                # (es el único divisor visual entre app y contenido).
                # El app-name es un label chiquito (10px): necesita aire para
                # no romper la jerarquía. HR ~14px debajo del fin de la fila,
                # y 8px más antes del título/body (buenas prácticas de espaciado).
                # Con avatar: el bloque de 80px ya da aire, HR angosto al lado.
                # Se calcula aquí (para que yy refleje el layout) pero se traza
                # UNA vez afuera del closure, sin clip (ver abajo de los 2 passes).
                if has_avatar:
                    _hr_y = yy - 6
                    _hr_x0, _hr_x1 = text_col_x, text_col_x + text_col_w
                    _hr_alpha = 0.12
                else:
                    _hr_y = yy + 14
                    _hr_x0, _hr_x1 = pad, W - pad
                    _hr_alpha = 0.28
                    yy += 18  # respiración: 14 gap al HR + 4 antes del título/body
                hr_info = (_hr_y, _hr_x0, _hr_x1, _hr_alpha)

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
                yy += 22

            # Body con wrap real + ellipsis cuando colapsa
            cr.set_source_rgb(*bcol)
            self._draw_text(cr, self._cuerpo, text_col_x, yy, text_col_w, _body_fs,
                            bcol, bcol, bold=False,
                            max_lines=(0 if expanded else cap))

        # Botón expandir/contraer (si hay overflow), una sola pasada
        self._expand_rect = None
        if has_more:
            body_top = ty + 20  # fila del app-name
            if not self._hide_title:
                body_top += 22  # fila del título
            # El HR sin-avatar empuja el body 18px abajo (respiración). El gap
            # debe reflejarse aquí o el botón cae encima del texto.
            if not self._avatar_pb:
                body_top += 18
            btn_y = body_top + body_h
            btn_h = self._BTN_H
            label = "Ver menos" if expanded else "Ver más"
            btn_x1 = text_col_x + text_col_w
            accent_r, accent_g, accent_b = self._accent_rgb

            # Pill COMPACTO alineado a la derecha: ancho = contenido real medido
            pad_x = 8
            cr.select_font_face("Manrope", 0, 0)
            cr.set_font_size(max(9, round(11 * fs)))
            ext = cr.text_extents(label)
            fe = cr.font_extents()
            chev_size, chev_gap, inner_pad = 10, 3, 10
            pill_w = inner_pad + ext[4] + chev_gap + chev_size + inner_pad
            pill_x0 = btn_x1 - pill_w - pad_x
            # Área clickeable = el pill (no toda la fila)
            self._expand_rect = (pill_x0, btn_y, pill_x0 + pill_w, btn_y + btn_h)

            for clip_x, is_dark in ((wx, False), (W - wx, True)):
                if clip_x <= 0:
                    continue
                cr.save()
                if clip_x < W:
                    cr.rectangle((0 if not is_dark else wx), 0,
                                 (clip_x if not is_dark else W - wx), H)
                    cr.clip()
                cr.set_source_rgba(accent_r, accent_g, accent_b, 0.18)
                rrect(cr, pill_x0, btn_y, pill_w, btn_h, btn_h / 2)
                cr.fill()
                # borde sutil del pill
                cr.set_source_rgba(accent_r, accent_g, accent_b, 0.35)
                cr.set_line_width(1.0)
                rrect(cr, pill_x0, btn_y, pill_w, btn_h, btn_h / 2)
                cr.stroke()
                if is_dark:  # dark pass: texto en la parte cubierta
                    cr.set_source_rgb(0.85, 0.95, 0.85)
                else:
                    cr.set_source_rgb(*self._left_title)
                # Texto anclado al padding interno izquierdo del pill
                tx0 = pill_x0 + inner_pad
                base_y = btn_y + btn_h / 2 + (fe[0] - fe[1]) / 2
                cr.move_to(tx0, base_y)
                cr.show_text(label)
                # Chevrón relleno (triángulo) a la derecha del texto, centrado en el pill.
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

        # Hairline del app_name: se traza UNA vez, fuera de los 2 passes
        # (sin clip) para que no se recorte por el wipe ni se duplique.
        if hr_info:
            _hr_y, _hr_x0, _hr_x1, _hr_alpha = hr_info
            cr.set_source_rgba(1.0, 1.0, 1.0, _hr_alpha)
            cr.set_line_width(1.0)
            cr.move_to(_hr_x0, _hr_y + 0.5)
            cr.line_to(_hr_x1, _hr_y + 0.5)
            cr.stroke()

        # Separador sutil entre línea de app y título (solo si ambos existen)
        if self._app_name and not self._hide_title:
            sep_y = ty + 20 - 1
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.06)
            cr.set_line_width(1.0)
            cr.move_to(text_col_x, sep_y)
            cr.line_to(text_col_x + text_col_w, sep_y)
            cr.stroke()

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

        # --- Pill de cerrar (X) — solo persistentes + hover ---
        # Pill rojizo semi-transparente 28x28, esquina superior-derecha.
        # NO ocupa todo el toast — es un botón chico esquinado.
        # Hover del pill: fondo más sólido + scale 1.08 (simulado con padding).
        self._close_rect = None
        if self._persistent and self._hover:
            cs = 28                                   # close button size
            cx_r = W - pad - 6                        # right edge (margen 6)
            cy_t = 6                                  # top edge
            cx0 = cx_r - cs
            cy0 = cy_t
            cx1 = cx_r
            cy1 = cy_t + cs
            self._close_rect = (cx0, cy0, cx1, cy1)
            cr.save()
            # Cairo: save/restore NO guarda el path actual (no es parte del
            # graphics state), así que un sub-path residual de bloques previos
            # (texto Pango, wipe clip, HR...) sobreviviría al restore y el
            # próximo stroke/fill del pill lo dibujaría como "línea fantasma".
            # new_path() descarta cualquier sub-path huérfano de este frame.
            cr.new_path()
            # Pixel-center: translate 0.5px so pill + X strokes land on pixel
            # boundaries (elimina el blur sub-pixel de line_width=2.5 centrado
            # en coords enteros; sin esto los bordes de la X se pixelan con
            # fringed AA que se lee como ghosting).
            cr.translate(0.5, 0.5)
            rrect(cr, cx0, cy0, cs, cs, 8)
            if self._hover_close:
                cr.set_source_rgba(0.86, 0.15, 0.15, 0.32)   # hover: más sólido
            else:
                cr.set_source_rgba(0.86, 0.15, 0.15, 0.18)   # normal hover del card
            cr.fill()
            # NOTE: se eliminó el borde rojo explícito (set_source_rgba(0.86, 0.15,
            # 0.15, 0.35) + stroke) que generaba el artifact de "línea roja" en
            # hover: su alpha (0.35) era mucho mayor que el del fill (0.18-0.32),
            # leyéndose como un contorno rojo flotante. El feedback de hover se
            # mantiene vía el cambio de opacidad del fill (0.18 -> 0.32 en
            # pill-hover), ya presente en el bloque.
            # X con dos trazos stroke (no fill): más limpio que path cerrado.
            # ANTIALIAS_NONE en la X: los round caps a 2.5px en un 28x28 crean
            # fringed semi-transparent pixels (blur). Sin AA la X es nítida y
            # el pixel-center (translate 0.5) mantiene las esquinas alineadas.
            mx = cx0 + cs / 2
            my = cy0 + cs / 2
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
        self.window.set_title("Verdantis")
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
        GtkLayerShell.set_namespace(self.window, "verdantis")
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

    def _resize_card(self, new_h):
        """Redimensiona la window (layer-shell) al alto pedido por toggle expandir/contraer."""
        if not self.window or not self._card:
            return
        self._card.set_size_request(_CARD_WIDTH, new_h)
        self.window.set_size_request(_CARD_WIDTH, new_h)
        self.window.queue_resize()
        self.window.show_all()          # reactiva layout
        GtkLayerShell.try_force_commit(self.window)

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
                         expanded=False, hide_title=False, font_scale=1.0,
                         has_avatar=False):
        """Altura de la card según el wrap REAL del cuerpo.

        `text_width` es el ancho de la columna de texto (card 360 − pad 14 − icon
        80 − gap 12 − pad 14 = 240). Antes se contaban líneas físicas (split
        "\\n") y el texto desbordaba el borde; ahora se cuentan las líneas
        visuales envolviéndolo. Si `expanded`, se muestran todas las líneas;
        si no, se limitan a _MAX_VISIBLE_LINES y se reserva la franja del botón.
        `font_scale` aplica la misma escala de resolución que usa _draw.
        `has_avatar` suma el gap del HR full-width (18px) que se dibuja en
        _draw cuando NO hay avatar — si no se suma, el stack colisiona."""
        _body_fs = max(9, round(13 * font_scale))
        text_h = 0
        if app_name:
            text_h += 20
        if not hide_title:
            text_h += 22
        # Gap del HR full-width (sin avatar) debe coincidir con _draw
        if app_name and not has_avatar:
            text_h += 18
        total = _count_body_lines(cuerpo, text_width, _body_fs)
        if expanded:
            _, body_h = _body_metrics(cuerpo, text_width, _body_fs, max_lines=None)
        else:
            cap = min(total, NotificationWidget._MAX_VISIBLE_LINES)
            _, body_h = _body_metrics(cuerpo, text_width, _body_fs, max_lines=cap)
        text_h += body_h
        if total > NotificationWidget._MAX_VISIBLE_LINES:
            text_h += NotificationWidget._BTN_H + 8
        row_h = max(text_h, 80)
        h = 14 + row_h + 14
        if image_path and os.path.exists(image_path):
            h += 8 + 140
        return h

    def set_stack_margin(self, index):
        self._stack_margin = index
        if self.window:
            self._apply_margins()

    def _apply_margins(self):
        if not self.window:
            return
        base_top, base_right, base_bottom, base_left = self._MARGIN_MAP.get(self.corner, (16, 16, 0, 0))
        gap = 12
        if self._card:
            card_h = self._card.desired_height()
        else:
            card_h = WaylandPopup.calc_card_height(self.app_name, self.cuerpo, self.image_path,
                                                  has_avatar=False)
        offset = self._stack_margin * (card_h + gap)
        if "top" in self.corner:
            t, b = base_top + offset, base_bottom
        else:
            t, b = base_top, base_bottom + offset
        if t: GtkLayerShell.set_margin(self.window, self._EDGES["top"], t)
        if b: GtkLayerShell.set_margin(self.window, self._EDGES["bottom"], b)
        r, l = base_right, base_left
        if r: GtkLayerShell.set_margin(self.window, self._EDGES["right"], r)
        if l: GtkLayerShell.set_margin(self.window, self._EDGES["left"], l)

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
