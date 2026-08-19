---
name: pycairo-vector-rendering
description: High-performance 2D vector rendering with Pycairo, subpixel antialiasing alignment, rounded cards, close pills, image clipping, and V-Sync wipe shaders.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pycairo, cairo, 2d-graphics, animations, frameclock, shaders]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [pycairo, vector-drawing, rounded-rectangles, wipe-transitions]
    triggers:
      - "when drawing rounded cards or glassmorphism UI in GTK3"
      - "when implementing close pills or interactive canvas widgets"
      - "when animating wipe transitions synchronized with monitor refresh rate"
      - "when clipping images with rounded corners or circular avatars"
---

# SKILL: Pycairo 2D Vector Rendering Engine

## 1. When to Use / Triggers
Activate this skill whenever:
- Rendering pixel-perfect vector cards, borders, and buttons directly with Cairo.
- Building micro-interactions (hover, pressed states) for custom canvas controls.
- Animating wipe/sweep transitions at 60/120/144Hz without stuttering.
- Masking and clipping `GdkPixbuf` images into rounded shapes.

## 2. Quick Reference & Constraints
- **Subpixel Alignment:** Add `+0.5` to 1px stroke lines to prevent blurry edges.
- **Context Protection:** Wrap every drawing routine in `cr.save()` and `cr.restore()`.
- **V-Sync Animation:** Always use `Gtk.Widget.add_tick_callback()` tied to `Gdk.FrameClock` (never `GLib.timeout_add` for animations).
- **Interpolation:** Use `GdkPixbuf.InterpType.BILINEAR` or `HYPER` when scaling bitmaps.

## 3. Production Drawing Blueprint

### Rounded Rectangle & Glassmorphism Card
```python
import math
import cairo


def draw_rounded_card(
    cr: cairo.Context,
    x: float,
    y: float,
    w: float,
    h: float,
    r: float = 16.0,
    bg_rgba: tuple[float, float, float, float] = (0.09, 0.10, 0.13, 0.94),
    border_rgba: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.12),
) -> None:
  cr.save()
  deg = math.pi / 180.0
  r_clamp = min(r, w / 2.0, h / 2.0)

  cr.new_sub_path()
  cr.arc(x + w - r_clamp, y + r_clamp, r_clamp, -90 * deg, 0 * deg)
  cr.arc(x + w - r_clamp, y + h - r_clamp, r_clamp, 0 * deg, 90 * deg)
  cr.arc(x + r_clamp, y + h - r_clamp, r_clamp, 90 * deg, 180 * deg)
  cr.arc(x + r_clamp, y + r_clamp, r_clamp, 180 * deg, 270 * deg)
  cr.close_path()

  cr.set_source_rgba(*bg_rgba)
  cr.fill_preserve()

  cr.set_source_rgba(*border_rgba)
  cr.set_line_width(1.0)
  cr.stroke()
  cr.restore()
```

### V-Sync Tick Callback Loop
```python
def on_tick_callback(
    self, widget: Gtk.Widget, frame_clock: Gdk.FrameClock
) -> bool:
  now = frame_clock.get_frame_time()
  if self.start_time is None:
    self.start_time = now
  t = min(1.0, (now - self.start_time) / self.duration_us)
  # Cubic ease out
  self.progress = 1.0 - math.pow(1.0 - t, 3)
  self.queue_draw()
  if t >= 1.0:
    return GLib.SOURCE_REMOVE
  return GLib.SOURCE_CONTINUE
```

## 4. Common Pitfalls & Edge Cases
- **Pitfall 1:** Forgetting `cr.restore()` after clipping.
  *Result:* Subsequent text or buttons fail to render (clipped out of view).
- **Pitfall 2:** Drawing at integer coordinates with 1.0 line width.
  *Result:* Fuzzy, anti-aliased 2px gray line instead of crisp 1px white border.
