import os

os.environ['GDK_BACKEND'] = 'wayland'

import sys
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, GtkLayerShell, GLib, Gdk, GdkPixbuf

CSS = """
#notify-card {
    background-color: #1e1e2e;
    border: 1px solid #585b70;
    border-radius: 14px;
}
#notify-card:hover {
    border: 1px solid %s;
}
#notify-title {
    color: #cdd6f4;
    font-size: 13px;
    font-weight: bold;
}
#notify-body {
    color: #a6adc8;
    font-size: 11px;
}
#notify-icon {
    background: #313244;
    border-radius: 6px;
}
#notify-image {
    border-radius: 8px;
}
trough {
    background-color: #45475a;
    border-radius: 4px;
    min-height: 8px;
}
progress {
    background-color: %s;
    border-radius: 4px;
    min-height: 8px;
}
"""


class WaylandPopup:
    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, margin=16, corner="top-right", accent="#89b4fa"):
        self.titulo = titulo
        self.cuerpo = cuerpo
        self.icon_path = icon_path
        self.image_path = image_path
        self.duration = duration
        self.margin = margin
        self.corner = corner
        self.accent = accent
        self._closed = False
        self.window = None
        self.progress = None
        self._start = 0

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
            raise RuntimeError("wlr_layer_shell no soportado por el compositor")

        self.window = Gtk.Window.new(Gtk.WindowType.POPUP)
        self.window.set_title("notify-app")
        self.window.set_name("notify-card")

        GtkLayerShell.init_for_window(self.window)
        if not GtkLayerShell.is_layer_window(self.window):
            raise RuntimeError("gtk-layer-shell init falló")
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.TOP)
        GtkLayerShell.try_force_commit(self.window)

        for edge_name in self._ANCHOR_MAP.get(self.corner, ("top", "right")):
            GtkLayerShell.set_anchor(self.window, self._EDGES[edge_name], True)

        top, right, bottom, left = self._MARGIN_MAP.get(self.corner, (16, 16, 0, 0))
        if top:    GtkLayerShell.set_margin(self.window, self._EDGES["top"], top)
        if right:  GtkLayerShell.set_margin(self.window, self._EDGES["right"], right)
        if bottom: GtkLayerShell.set_margin(self.window, self._EDGES["bottom"], bottom)
        if left:   GtkLayerShell.set_margin(self.window, self._EDGES["left"], left)
        GtkLayerShell.set_exclusive_zone(self.window, -1)

        css = CSS % (self.accent, self.accent)
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        icon = Gtk.Box()
        icon.set_size_request(32, 32)
        icon.set_valign(Gtk.Align.START)
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    self.icon_path, 32, 32, True
                )
                icon.add(Gtk.Image.new_from_pixbuf(pix))
            except Exception:
                pass
        else:
            icon.set_name("notify-icon")
        top_row.pack_start(icon, False, False, 0)

        text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label=self.titulo)
        title.set_name("notify-title")
        title.set_xalign(0)
        title.set_line_wrap(True)
        title.set_lines(1)
        text_vbox.pack_start(title, False, False, 0)

        body = Gtk.Label(label=self.cuerpo)
        body.set_name("notify-body")
        body.set_xalign(0)
        body.set_line_wrap(True)
        body.set_max_width_chars(36)
        text_vbox.pack_start(body, False, False, 0)

        top_row.pack_start(text_vbox, True, True, 0)
        box.pack_start(top_row, False, False, 0)

        if self.image_path and os.path.exists(self.image_path):
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    self.image_path, 260, 140, True
                )
                img = Gtk.Image.new_from_pixbuf(pix)
                img.set_name("notify-image")
                img.set_margin_top(6)
                box.pack_start(img, False, False, 0)
            except Exception:
                pass

        self.progress = Gtk.ProgressBar()
        self.progress.set_fraction(1.0)
        self.window.connect("destroy", lambda *a: Gtk.main_quit())
        box.pack_start(self.progress, False, False, 0)

        self.window.add(box)
        self.window.connect("button-press-event", lambda *a: self._close())
        self.window.connect("key-press-event", lambda *a: self._close())

    def _update_progress(self):
        if self._closed:
            return False
        elapsed = (time.time() - self._start) * 1000
        remaining = max(0, self.duration - elapsed)
        self.progress.set_fraction(remaining / self.duration)
        if remaining <= 0:
            self._close()
            return False
        return True

    def _close(self, *a):
        if self._closed:
            return
        self._closed = True
        if self.window:
            self.window.destroy()
            self.window = None

    def show(self):
        if not os.environ.get("WAYLAND_DISPLAY"):
            print("[wayland] No WAYLAND_DISPLAY", file=sys.stderr)
            return
        self._build_ui()
        self.window.show_all()
        self._start = time.time()
        GLib.timeout_add(50, self._update_progress)
        Gtk.main()
