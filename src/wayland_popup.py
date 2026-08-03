import math
import os
import configparser
os.environ['GDK_BACKEND'] = 'wayland'

import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, GtkLayerShell, GLib, Gdk, GdkPixbuf, Pango, PangoCairo


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
    path = _find_desktop_file(app_name)
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


def _get_app_display_name(app_name):
    path = _find_desktop_file(app_name)
    if not path:
        return app_name
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        return cp.get("Desktop Entry", "Name", fallback=app_name)
    except Exception:
        return app_name


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

_LINK_COLOR = "#89b4fa"


def _sanitize_pango_markup(text):
    """Convierte markup de body (freedesktop 1.2) a markup que Pango entienda.

    - <a href="URL">label</a> → <span underline="single" color="...">label</span>
      (Pango no tiene <a>; el subrayado mantiene la semántica de link y la
      URL ya la extrae _extract_markup_url para el click).
    - Devuelve el texto tal cual si no hay tags reconocibles."""
    import re
    text = re.sub(
        r'<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r'<span underline="single" color="%s">\2</span>' % _LINK_COLOR,
        text, flags=re.S | re.I)
    return text


def _has_pango_markup(text):
    """True si el texto contiene al menos una tag de markup que Pango soporta."""
    return "<" in text and any(t in text for t in _PANGO_TAGS)


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _body_metrics(cuerpo, width, font_size=14, max_lines=None):
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
    fd = Pango.FontDescription("sans-serif " + str(font_size))
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


def _count_body_lines(cuerpo, width, font_size=14):
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

    def __init__(self, app_name, app_icon, titulo, cuerpo, icon_path, image_path, accent,
                 image_data_raw=None, on_click=None, on_resize=None):
        super().__init__()
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self._expanded = False
        self._expand_rect = None
        self._on_resize = on_resize
        self._fraction = 1.0
        self._on_click = on_click
        self._app_name = _get_app_display_name(app_name)
        self._titulo = titulo
        self._cuerpo = cuerpo
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

        if not self._avatar_pb:
            avatar_from_desktop = _get_app_icon_from_desktop(app_name, 80)
            if avatar_from_desktop:
                self._avatar_pb = _make_circular(avatar_from_desktop, 80)
            else:
                avatar_from_theme = _icon_from_theme(app_icon, 80)
                if not avatar_from_theme:
                    avatar_from_theme = _icon_from_theme(app_name, 80)
                if avatar_from_theme:
                    self._avatar_pb = _make_circular(avatar_from_theme, 80)

        if image_data_raw:
            try:
                w, h, rowstride, has_alpha, bps, n_channels, data = image_data_raw
                self._image_pb = GdkPixbuf.Pixbuf.new_from_bytes(
                    GLib.Bytes.new(data),
                    GdkPixbuf.Colorspace.RGB,
                    has_alpha,
                    bps,
                    w, h,
                    rowstride,
                )
                self._image_pb = self._image_pb.scale_simple(
                    260, 140, GdkPixbuf.InterpType.BILINEAR)
            except Exception:
                pass

        if image_path and os.path.exists(image_path):
            try:
                self._image_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    image_path, 260, 140, True)
            except Exception:
                pass

        self.connect("draw", self._draw)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_button_press)

    def _on_button_press(self, widget, event):
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

    def desired_height(self):
        """Altura en el estado actual (colapsado/expandido) para redimensionar la window.
        Incluye la altura del banner de imagen si el widget lo tiene cargado (equivale
        a lo que calc_card_height suma cuando existe image_path)."""
        h = WaylandPopup.calc_card_height(
            self._app_name, self._cuerpo, "",
            text_width=_TEXT_COL_W, expanded=self._expanded,
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
        fd = Pango.FontDescription("sans-serif " + str(font_size))
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
        icon_size = 80
        text_col_x = pad + icon_size + gap
        text_col_w = W - text_col_x - pad

        # Helper: rounded rect path (clockwise, outer corners)
        def rrect(cr, x, y, w, h, r):
            r = min(r, w / 2, h / 2)
            cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
            cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
            cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
            cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
            cr.close_path()

        r = 12   # radio card: 8→12 (más moderno/redondeado, Linear usa 8-12)

        # Background
        cr.set_source_rgba(self._card_bg[0], self._card_bg[1], self._card_bg[2], 0.85)
        rrect(cr, 0, 0, W, H, r)
        cr.fill()

        # Wipe: clip to card shape, fill right portion
        if wx < W:
            dr = self._accent_rgb[0] * 0.2
            dg = self._accent_rgb[1] * 0.4
            db = self._accent_rgb[2] * 0.2
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
        total_lines = _count_body_lines(self._cuerpo, text_col_w, 14)
        expanded = self._expanded
        cap = min(total_lines, self._MAX_VISIBLE_LINES)
        if expanded:
            _, body_h = _body_metrics(self._cuerpo, text_col_w, 14, max_lines=None)
        else:
            _, body_h = _body_metrics(self._cuerpo, text_col_w, 14, max_lines=cap)
        has_more = total_lines > self._MAX_VISIBLE_LINES   # overflow => mostrar botón (debe persistir al expandir para poder contraer)

        text_h = 0
        if self._app_name:
            text_h += 20
        text_h += 22
        text_h += body_h
        if has_more:
            text_h += self._BTN_H + 6   # franja del botón expandir/contraer
        row_h = max(text_h, icon_size)
        cy = pad + (row_h - icon_size) / 2

        # Avatar (container izquierdo, centrado verticalmente)
        if self._avatar_pb:
            Gdk.cairo_set_source_pixbuf(cr, self._avatar_pb, pad, cy)
            cr.rectangle(pad, cy, icon_size, icon_size)
            cr.fill()
        else:
            cr.set_source_rgb(0.19, 0.20, 0.27)
            cr.rectangle(pad, cy, icon_size, icon_size)
            cr.fill()

        # --- Text in two passes ---
        ty = pad + (row_h - text_h) / 2

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
                cr.select_font_face("sans-serif", 0, 0)
                cr.set_font_size(10)
                tx = text_col_x + (20 if self._app_icon_pb else 0)
                cr.move_to(tx, yy + 13)
                cr.show_text(self._app_name)
                yy += 20

            cr.set_source_rgb(*tcol)
            cr.select_font_face("sans-serif", 0, 1)
            cr.set_font_size(12)
            cr.move_to(text_col_x, yy + 11)
            cr.show_text(self._titulo)
            yy += 22

            # Body con wrap real + ellipsis cuando colapsa
            cr.set_source_rgb(*bcol)
            self._draw_text(cr, self._cuerpo, text_col_x, yy, text_col_w, 14,
                            bcol, bcol, bold=False,
                            max_lines=(0 if expanded else cap))

        # Botón expandir/contraer (si hay overflow), una sola pasada
        self._expand_rect = None
        if has_more:
            body_top = ty
            if self._app_name:
                body_top += 20
            body_top += 22
            # Ancla justo debajo del body medido (altura lógica real), nunca se solapa
            btn_y = body_top + body_h
            btn_h = self._BTN_H
            label = "Ver menos" if expanded else "Ver más"
            btn_x0 = text_col_x
            btn_x1 = text_col_x + text_col_w
            self._expand_rect = (btn_x0, btn_y, btn_x1, btn_y + btn_h)
            # Pill background sutil del color acento (+ borde fino, estilo Linear)
            accent_r = self._accent_rgb[0]
            accent_g = self._accent_rgb[1]
            accent_b = self._accent_rgb[2]
            # Pill con padding horizontal interno: margen de 8px a cada lado
            pad_x = 8
            pill_x0 = btn_x0 + pad_x
            pill_w = (btn_x1 - btn_x0) - 2 * pad_x
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
                # Texto "Ver más / Ver menos" + chevrón dibujado con cairo (siempre visible)
                cr.select_font_face("sans-serif", 0, 0)
                cr.set_font_size(11)
                tw = len(label) * 6 + 10      # texto + 5px de chevrón + gap
                tx0 = pill_x0 + pill_w - tw
                cr.move_to(tx0, btn_y + btn_h / 2 + 4)
                cr.show_text(label)
                # Chevron cairo (triángulo) a la derecha del texto, verticalmente centrado
                cx0 = tx0 + len(label) * 6 + 2
                cy_mid = btn_y + btn_h / 2 - 1 if not expanded else btn_y + btn_h / 2 + 1
                if expanded:
                    cr.move_to(cx0, cy_mid - 4)
                    cr.line_to(cx0 + 5, cy_mid + 2.5)
                    cr.line_to(cx0 + 10, cy_mid - 4)   # apunta arriba = "ver menos"
                else:
                    cr.move_to(cx0, cy_mid + 4)
                    cr.line_to(cx0 + 5, cy_mid - 2.5)
                    cr.line_to(cx0 + 10, cy_mid + 4)   # apunta abajo = "ver más"
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
            Gdk.cairo_set_source_pixbuf(cr, self._image_pb, pad, iy)
            cr.rectangle(pad, iy, iw, ih)
            cr.fill()


class WaylandPopup:
    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, margin=16, corner="top-right", accent="#89b4fa",
                 app_name="", app_icon="", on_close=None, image_data_raw=None,
                 on_click=None, urgency=1):
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
        )
        h = WaylandPopup.calc_card_height(self.app_name, self.cuerpo, self.image_path)
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
        elapsed = (time.time() - self._start) * 1000
        remaining = max(0, self.duration - elapsed)
        self._card.set_fraction(remaining / self.duration)
        if remaining <= 0:
            self._close()
            return False
        return True

    @staticmethod
    def calc_card_height(app_name, cuerpo, image_path, text_width=_TEXT_COL_W,
                         expanded=False):
        """Altura de la card según el wrap REAL del cuerpo.

        `text_width` es el ancho de la columna de texto (card 360 − pad 14 − icon
        80 − gap 12 − pad 14 = 240). Antes se contaban líneas físicas (split
        "\\n") y el texto desbordaba el borde; ahora se cuentan las líneas
        visuales envolviéndolo. Si `expanded`, se muestran todas las líneas;
        si no, se limitan a _MAX_VISIBLE_LINES y se reserva la franja del botón."""
        text_h = 0
        if app_name:
            text_h += 20
        text_h += 22
        total = _count_body_lines(cuerpo, text_width, 14)
        if expanded:
            # Altura NATURAL del body completo (toda la envoltura)
            _, body_h = _body_metrics(cuerpo, text_width, 14, max_lines=None)
        else:
            # Altura CAPPED + ellipsis (la que dibuja _draw_text al colapsar)
            cap = min(total, NotificationWidget._MAX_VISIBLE_LINES)
            _, body_h = _body_metrics(cuerpo, text_width, 14, max_lines=cap)
        text_h += body_h
        if total > NotificationWidget._MAX_VISIBLE_LINES:
            text_h += NotificationWidget._BTN_H + 6
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
        gap = 8
        card_h = WaylandPopup.calc_card_height(self.app_name, self.cuerpo, self.image_path)
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
