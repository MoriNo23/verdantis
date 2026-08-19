---
name: gdk3-pixbuf-cursor-input
description: Robust Gdk 3.0 asset loader with memory fallback, native Wayland cursor themes (pointer/default), and pointer event routing.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [gdk3, gdkpixbuf, wayland, cursors, breeze, input-routing]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [gdk-events, cursor-management, pixbuf-scaling, hit-testing]
    triggers:
      - "when loading external images safely without crashing GTK3"
      - "when changing mouse cursors on hover in Wayland"
      - "when enabling pointer motion and click events on DrawingArea"
---

# SKILL: Gdk 3.0 & GdkPixbuf Asset Loading, Cursors & Input Masking

## 1. When to Use / Triggers
Activate this skill whenever:
- Loading image assets into memory with safe in-memory fallback buffers.
- Setting native Wayland cursor shapes (`"pointer"`, `"default"`, `"grab"`) adhering to the user's active KDE Plasma Breeze theme.
- Enabling interactive mouse masks (`motion-notify`, `button-press`, `leave-notify`) on `Gtk.DrawingArea`.

## 2. Quick Reference & Constraints
- **Semantic Cursors:** Use `Gdk.Cursor.new_from_name(display, "pointer")` instead of deprecated enum IDs.
- **Event Masking:** Always register `Gdk.EventMask.POINTER_MOTION_MASK` and `BUTTON_PRESS_MASK`.
- **Safe Pixbuf Loading:** Always catch file I/O exceptions and provide an RGBA memory pixbuf fallback to prevent app crashes.

## 3. Production Asset & Cursor Helpers

```python
from pathlib import Path
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk


def safe_load_pixbuf(
    path: str | Path, target_w: int, target_h: int
) -> GdkPixbuf.Pixbuf:
  try:
    return GdkPixbuf.Pixbuf.new_from_file_at_scale(
        str(path), target_w, target_h, True
    )
  except Exception:
    # Memory fallback (Blue RGBA)
    buf = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, True, 8, target_w, target_h
    )
    buf.fill(0x3B82F6FF)
    return buf


def set_cursor(widget: Gtk.Widget, name: str) -> None:
  gw = widget.get_window()
  if gw:
    disp = widget.get_display() or Gdk.Display.get_default()
    if disp:
      gw.set_cursor(Gdk.Cursor.new_from_name(disp, name))
```

## 4. Common Pitfalls & Edge Cases
- **Pitfall 1:** Missing `widget.add_events()` before realizing the widget.
  *Result:* The widget completely ignores mouse movement and hover animations.
- **Pitfall 2:** Leaving the pointer in `pointer` mode when leaving the button area.
  *Fix:* Reset cursor to `default` in the `leave-notify-event` handler.
