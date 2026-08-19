"""gtk-layer-shell 0.1 Controller for KDE Plasma 6 (KWin Wayland)."""

from enum import Enum
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GtkLayerShell

class LayerPosition(Enum):
    TOP_RIGHT = 1
    TOP_LEFT = 2
    BOTTOM_RIGHT = 3
    BOTTOM_LEFT = 4
    TOP_CENTER = 5

class LayerShellController:
    """Production helper for zwlr_layer_shell_v1 window setup."""
    
    @classmethod
    def setup_hud_window(
        cls,
        window: Gtk.Window,
        position: LayerPosition = LayerPosition.TOP_RIGHT,
        margin_x: int = 24,
        margin_y: int = 24,
        layer: GtkLayerShell.Layer = GtkLayerShell.Layer.OVERLAY,
        keyboard_mode: GtkLayerShell.KeyboardMode = GtkLayerShell.KeyboardMode.NONE,
        monitor: Gdk.Monitor | None = None
    ) -> None:
        GtkLayerShell.init_for_window(window)
        
        if monitor is not None:
            GtkLayerShell.set_monitor(window, monitor)
        else:
            display = Gdk.Display.get_default()
            if display:
                primary = display.get_primary_monitor() or (display.get_monitor(0) if display.get_n_monitors() > 0 else None)
                if primary:
                    GtkLayerShell.set_monitor(window, primary)

        GtkLayerShell.set_layer(window, layer)
        GtkLayerShell.set_keyboard_mode(window, keyboard_mode)
        GtkLayerShell.set_exclusive_zone(window, 0)

        for edge in [GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT]:
            GtkLayerShell.set_anchor(window, edge, False)

        if position == LayerPosition.TOP_RIGHT:
            GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, margin_y)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.RIGHT, margin_x)
        elif position == LayerPosition.BOTTOM_RIGHT:
            GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.BOTTOM, margin_y)
            GtkLayerShell.set_margin(window, GtkLayerShell.Edge.RIGHT, margin_x)

    @classmethod
    def apply_input_mask(cls, window: Gtk.Window, x: int, y: int, width: int, height: int) -> None:
        gdk_win = window.get_window()
        if gdk_win is not None:
            rect = cairo.RectangleInt(x, y, width, height)
            region = cairo.Region(rect)
            gdk_win.input_shape_combine_region(region, 0, 0)
