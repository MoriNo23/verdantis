"""Pango & PangoCairo Dynamic Typography Engine with Bundled Font Loader."""

import sys
import os
import ctypes
import ctypes.util
from pathlib import Path
import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

class BundledFontManager:
    _loaded_fonts: set[str] = set()

    @classmethod
    def register_font(cls, font_file_path: str | Path) -> bool:
        resolved = str(Path(font_file_path).resolve())
        if resolved in cls._loaded_fonts:
            return True
        if not os.path.exists(resolved):
            return False

        try:
            fc_name = ctypes.util.find_library("fontconfig") or "libfontconfig.so.1"
            fc = ctypes.cdll.LoadLibrary(fc_name)
            fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            fc.FcConfigAppFontAddFile.restype = ctypes.c_bool
            
            ok = fc.FcConfigAppFontAddFile(None, resolved.encode("utf-8"))
            if ok:
                cls._loaded_fonts.add(resolved)
                return True
            return False
        except Exception as err:
            sys.stderr.write(f"ERR: Failed loading fontconfig ctypes: {err}\n")
            return False

class PangoTextRenderer:
    @staticmethod
    def render_text(
        cr: cairo.Context,
        text: str,
        x: float,
        y: float,
        max_width: float,
        font_desc_str: str = "Manrope Medium 13",
        color_rgba: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.95),
        ellipsize: bool = True
    ) -> tuple[int, int]:
        cr.save()
        layout: Pango.Layout = PangoCairo.create_layout(cr)
        layout.set_text(text, -1)
        layout.set_font_description(Pango.FontDescription.from_string(font_desc_str))
        
        if max_width > 0:
            layout.set_width(int(max_width * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        
        if ellipsize:
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            
        cr.set_source_rgba(*color_rgba)
        cr.move_to(x, y)
        PangoCairo.update_layout(cr, layout)
        PangoCairo.show_layout(cr, layout)
        w, h = layout.get_pixel_size()
        cr.restore()
        return (w, h)
