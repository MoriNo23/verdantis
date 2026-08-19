---
name: gtk-layer-shell-plasma6
description: Production integration of gtk-layer-shell 0.1 over Wayland zwlr_layer_shell_v1 protocol in KDE Plasma 6 KWin, with anchoring, non-blocking exclusive zones, and input masking.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [wayland, gtk-layer-shell, kde-plasma-6, kwin, desktop-overlay]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [layer-shell, kwin-wayland, exclusive-zone, input-masking]
    triggers:
      - "when creating Wayland desktop widgets, panels, or HUDs"
      - "when fixing gtk_layer_init_for_window crashing after realize"
      - "when configuring click-through transparent regions on Wayland"
---

# SKILL: `gtk-layer-shell` 0.1 on Wayland (KDE Plasma 6 / KWin)

## 1. When to Use / Triggers
Activate this skill whenever:
- Displaying GTK3 windows as persistent desktop overlays, status bars, HUDs, or notifications on Wayland.
- Interacting with KDE Plasma 6 (KWin 6) using the `zwlr_layer_shell_v1` protocol.
- Configuring mouse click-through for transparent padding using input shape masks.

## 2. Quick Reference & Constraints
- **CRITICAL ORDER:** `GtkLayerShell.init_for_window(window)` MUST be called **BEFORE** `window.show()`, `window.show_all()` or `window.realize()`.
- **Layers:**
  - `Layer.BACKGROUND` / `Layer.BOTTOM`: Wallpapers and desktop gadgets.
  - `Layer.TOP`: Panels and taskbars.
  - `Layer.OVERLAY`: Floating HUDs, toasts, and OSDs.
- **Keyboard Interactivity:** Use `KeyboardMode.NONE` for non-modal HUDs. `EXCLUSIVE` blocks Plasma global shortcuts.
- **Exclusive Zone:** Set to `0` or `-1` to avoid pushing Plasma panels.

## 3. Production Architecture Pattern

```python
from enum import Enum
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, Gtk, GtkLayerShell


class LayerPosition(Enum):
  TOP_RIGHT = 1
  BOTTOM_RIGHT = 2
  TOP_LEFT = 3
  BOTTOM_LEFT = 4


def setup_layer_shell(
    window: Gtk.Window,
    pos: LayerPosition = LayerPosition.TOP_RIGHT,
    margin_x: int = 24,
    margin_y: int = 24,
) -> None:
  # 1. Init before window realization
  GtkLayerShell.init_for_window(window)
  GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
  GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.NONE)
  GtkLayerShell.set_exclusive_zone(window, 0)

  # 2. Reset anchors
  for edge in [
      GtkLayerShell.Edge.TOP,
      GtkLayerShell.Edge.BOTTOM,
      GtkLayerShell.Edge.LEFT,
      GtkLayerShell.Edge.RIGHT,
  ]:
    GtkLayerShell.set_anchor(window, edge, False)

  # 3. Apply position
  if pos == LayerPosition.TOP_RIGHT:
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, True)
    GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.RIGHT, True)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, margin_y)
    GtkLayerShell.set_margin(window, GtkLayerShell.Edge.RIGHT, margin_x)
```

## 4. Click-Through Input Masking
```python
def apply_click_through_mask(
    window: Gtk.Window, x: int, y: int, width: int, height: int
) -> None:
  """Ensures clicks outside the exact card area pass through to underlying windows."""
  gdk_win = window.get_window()
  if gdk_win:
    rect = cairo.RectangleInt(x, y, width, height)
    region = cairo.Region(rect)
    gdk_win.input_shape_combine_region(region, 0, 0)
```

## 5. Common Pitfalls & Edge Cases
- **Pitfall 1:** Initializing layer shell after `show_all()`.
  *Error:* `Gtk-ERROR: gtk_layer_init_for_window() called on realized window`.
  *Fix:* Execute in `Window.__init__()` before mapping.
- **Pitfall 2:** Window steals all keyboard input.
  *Fix:* Do not use `KeyboardMode.EXCLUSIVE`; use `KeyboardMode.NONE`.
