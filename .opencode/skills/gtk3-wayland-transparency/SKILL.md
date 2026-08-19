---
name: gtk3-wayland-transparency
description: Master GTK 3.0 RGBA visual pipeline and alpha compositing on Wayland / KDE Plasma 6 KWin without black boxes or theme artifacts.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [gtk3, wayland, kwin, kde-plasma-6, transparency, cairo]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [gtk3-transparency, alpha-compositing, wayland-visual, app-paintable]
    triggers:
      - "when creating transparent GTK3 windows on Wayland"
      - "when fixing black background artifacts in KWin 6 overlays"
      - "when configuring custom Cairo draw pipelines for Gtk.Window"
---

# SKILL: GTK 3.0 Wayland Transparency Pipeline

## 1. When to Use / Triggers
Activate this skill whenever:
- Creating floating, transparent or glassmorphism windows in GTK 3.0 on Wayland.
- Overlays render solid black backgrounds instead of transparent alpha channels in KDE Plasma 6.
- GTK theme default styles override custom transparent Cairo drawings.

## 2. Quick Reference & Constraints
- **Visual Assignment:** Always query `screen.get_rgba_visual()` and apply `window.set_visual(visual)`.
- **App Paintable:** Must call `window.set_app_paintable(True)` and `window.set_decorated(False)`.
- **Cairo Clear:** Use `cairo.OPERATOR_CLEAR` followed by `cr.paint()` at the root window's `draw` signal.
- **Return Value:** Root draw handler must return `False` so child widgets render on top of the cleared canvas.

## 3. Production Pattern: `transparent_window.py`

```python
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk


class TransparentTopLevelWindow(Gtk.Window):

  def __init__(self, title: str = "LayerOverlay") -> None:
    super().__init__(type=Gtk.WindowType.TOPLEVEL)
    self.set_title(title)
    self.set_decorated(False)
    self.set_resizable(False)

    # 1. Enable RGBA Visual
    screen = self.get_screen()
    if screen and screen.is_composited():
      visual = screen.get_rgba_visual()
      if visual:
        self.set_visual(visual)

    # 2. Enable manual painting
    self.set_app_paintable(True)
    self.connect("draw", self._on_window_draw)

  def _on_window_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
    cr.save()
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.restore()
    return False  # Allow children to paint
```

## 4. Common Pitfalls & Edge Cases
- **Pitfall 1:** Using `window.set_opacity(0.8)` instead of RGBA.
  *Result:* All text, icons, and buttons become faded/transparent, ruining legibility.
  *Fix:* Keep window opacity at 1.0 and paint background with RGBA alpha channels via Cairo.
- **Pitfall 2:** Calling `set_visual()` after `show()` or `realize()`.
  *Result:* Gdk-CRITICAL error; visual remains 24-bit RGB (black background).

## 5. Verification
Verify alpha support using:
```bash
python -c "
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk
screen = Gdk.Screen.get_default()
print('RGBA Visual supported:', screen.get_rgba_visual() is not None and screen.is_composited())
"
```
