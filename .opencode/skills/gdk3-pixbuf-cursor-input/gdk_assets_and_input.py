"""Gdk 3.0 & GdkPixbuf Asset Loader and Wayland Cursor Controller."""

import sys
from pathlib import Path
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

class GdkAssetManager:
    @staticmethod
    def load_pixbuf_safe(
        path: str | Path,
        target_w: int = 64,
        target_h: int = 64
    ) -> GdkPixbuf.Pixbuf:
        resolved = str(Path(path).resolve())
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                resolved,
                target_w,
                target_h,
                preserve_aspect_ratio=True
            )
        except Exception as e:
            sys.stderr.write(f"WARN: Fallback pixbuf used for {resolved}: {e}\n")
            fb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, target_w, target_h)
            fb.fill(0x3B82F6FF)
            return fb

class GdkCursorManager:
    @staticmethod
    def set_cursor(widget: Gtk.Widget, cursor_name: str = "default") -> None:
        win = widget.get_window()
        if win is not None:
            disp = widget.get_display() or Gdk.Display.get_default()
            if disp:
                cursor = Gdk.Cursor.new_from_name(disp, cursor_name)
                win.set_cursor(cursor)
