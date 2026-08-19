---
name: pangocairo-bundled-typography
description: Pango and PangoCairo typography engine with dynamic FontConfig C-API bundled font registration (Manrope), multi-line wrapping, and precision ellipsis.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pango, pangocairo, fontconfig, typography, manrope, cairo]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [pango-layout, bundled-fonts, fontconfig-ctypes, text-ellipsis]
    triggers:
      - "when loading bundled TTF/OTF fonts in Python without root installation"
      - "when rendering formatted text with Pango and Cairo"
      - "when calculating dynamic text wrap and ellipsis widths"
---

# SKILL: Pango & PangoCairo Bundled Typography (Manrope)

## 1. When to Use / Triggers
Activate this skill whenever:
- Embedding custom fonts (like **Manrope**, Inter, JetBrains Mono) directly inside an application bundle without requiring system installation.
- Rendering high-DPI text with subpixel hinting using PangoCairo.
- Formatting UI titles, badges, and subtitles with multi-line auto-wrap and end ellipsis.

## 2. Quick Reference & Constraints
- **Runtime Font Registration:** Use `ctypes` calling `FcConfigAppFontAddFile(None, font_path)` in `libfontconfig.so.1`.
- **Pango.SCALE Multiplication:** Pango uses fixed-point values. Always multiply pixel dimensions by `Pango.SCALE` ($1024$) and cast to `int`.
- **Ellipsis Mode:** Set `layout.set_ellipsize(Pango.EllipsizeMode.END)` to handle string truncation cleanly.

## 3. Production Font Loader & Text Renderer Pattern

```python
import ctypes
import ctypes.util
from pathlib import Path
import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo


def load_app_font(font_path: str | Path) -> bool:
  p = str(Path(font_path).resolve())
  fc_lib = ctypes.cdll.LoadLibrary(
      ctypes.util.find_library("fontconfig") or "libfontconfig.so.1"
  )
  fc_lib.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
  fc_lib.FcConfigAppFontAddFile.restype = ctypes.c_bool
  return fc_lib.FcConfigAppFontAddFile(None, p.encode("utf-8"))


def render_pango_text(
    cr: cairo.Context,
    text: str,
    x: float,
    y: float,
    max_w: float,
    font_desc: str = "Manrope SemiBold 13",
    color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.95),
) -> tuple[int, int]:
  cr.save()
  layout = PangoCairo.create_layout(cr)
  layout.set_text(text, -1)
  layout.set_font_description(Pango.FontDescription.from_string(font_desc))
  if max_w > 0:
    layout.set_width(int(max_w * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    layout.set_ellipsize(Pango.EllipsizeMode.END)
  cr.set_source_rgba(*color)
  cr.move_to(x, y)
  PangoCairo.update_layout(cr, layout)
  PangoCairo.show_layout(cr, layout)
  size = layout.get_pixel_size()
  cr.restore()
  return size
```

## 4. Common Pitfalls & Edge Cases
- **Pitfall 1:** Passing raw pixel integers to `layout.set_width()`.
  *Result:* Text collapses into 1-pixel column because $100\text{px}$ is interpreted as $\approx 0.09\text{px}$.
  *Fix:* Pass `int(width * Pango.SCALE)`.
- **Pitfall 2:** Registering fonts after creating layouts.
  *Result:* Pango falls back to generic Serif/Sans instead of bundled Manrope.
