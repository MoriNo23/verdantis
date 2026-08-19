"""Transparent TopLevel Window Implementation for GTK3 on Wayland."""

import sys
import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

class TransparentTopLevelWindow(Gtk.Window):
    """Base window class configured for pure alpha transparency on KDE Plasma 6."""
    def __init__(self, title: str = "LayerShellOverlay") -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title(title)
        self.set_decorated(False)
        self.set_resizable(False)

        self._setup_rgba_visual()
        self.set_app_paintable(True)
        self.connect("draw", self._on_window_draw)

    def _setup_rgba_visual(self) -> None:
        screen: Gdk.Screen | None = self.get_screen()
        if screen is not None:
            visual: Gdk.Visual | None = screen.get_rgba_visual()
            if visual is not None and screen.is_composited():
                self.set_visual(visual)
            else:
                sys.stderr.write("WARN: RGBA visual not available; check compositor.\n")

    def _on_window_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.restore()
        return False
