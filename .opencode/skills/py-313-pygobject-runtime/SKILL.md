---
name: py-313-pygobject-runtime
description: Expert Python 3.13 .venv runtime management, GObject Introspection typelib resolution, thread-safety and GLib lifecycle control without memory leaks.
version: 1.0.0
author: Arena AI Research & Senior Linux Systems Team
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [python, python3.13, pygobject, glib, gobject, linux-desktop]
    requires_toolsets: [terminal, filesystem]
    requires_tools: [run_terminal_cmd, read_file, write_file]
  opencode:
    tags: [python3.13, gi-repository, memory-safety, thread-dispatch]
    triggers:
      - "when setting up a Python 3.13 virtual environment with PyGObject"
      - "when importing gi.repository in isolated .venv"
      - "when dispatching background thread tasks to GTK3 / GLib main loop"
      - "when diagnosing GObject circular reference memory leaks"
---

# SKILL: Python 3.13 & PyGObject Lifecycle Management

## 1. When to Use / Triggers
Activate this skill whenever:
- Initializing a Python 3.13 `.venv` for GTK3 / Wayland desktop applications.
- Resolving `gi.require_version` failures or missing system `.typelib` files.
- Executing thread-safe UI updates from background workers to `GLib.MainLoop`.
- Preventing GObject closure memory leaks on widget destruction.

## 2. Quick Reference & Constraints
- **C-API Changes:** Python 3.13 requires `PyGObject >= 3.48.0` / `3.50.0+`.
- **Typelib Path:** System typelibs reside in `/usr/lib/girepository-1.0` or `/usr/lib64/girepository-1.0`. Virtual environments MUST export `GI_TYPELIB_PATH`.
- **Require Ordering:** `gi.require_version()` calls MUST precede any `from gi.repository import ...`.
- **Thread Safety:** Never mutate GTK widgets outside the main GLib thread. Use `GLib.idle_add()`.

## 3. Production Procedure & Patterns

### Step 1: Export Typelib Paths in Python
```python
import os
from pathlib import Path
import sys

SYSTEM_TYPELIB_PATHS = [
    "/usr/lib64/girepository-1.0",
    "/usr/lib/x86_64-linux-gnu/girepository-1.0",
    "/usr/lib/girepository-1.0",
    "/usr/local/lib64/girepository-1.0",
    "/usr/local/lib/girepository-1.0",
]
existing = os.environ.get("GI_TYPELIB_PATH", "")
valid = [p for p in SYSTEM_TYPELIB_PATHS if Path(p).exists()]
if existing:
  valid.append(existing)
os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(valid)
```

### Step 2: Thread-Safe Dispatcher Pattern
```python
from collections.abc import Callable
import threading
from typing import Any
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class MainThreadDispatcher:
  _main_id = threading.get_ident()

  @classmethod
  def dispatch(
      cls,
      fn: Callable[..., None],
      *args: Any,
      priority: int = GLib.PRIORITY_DEFAULT,
  ) -> None:
    if threading.get_ident() == cls._main_id:
      fn(*args)
      return

    def _worker() -> bool:
      fn(*args)
      return False  # GLib.SOURCE_REMOVE

    GLib.idle_add(_worker, priority=priority)
```

## 4. Common Pitfalls & Edge Cases
- **Pitfall 1:** Calling `time.sleep()` in UI callbacks blocks KWin Wayland rendering.
  *Fix:* Use `GLib.timeout_add(interval_ms, callback)`.
- **Pitfall 2:** Connecting methods to GObject signals without disconnection retains objects after `destroy`.
  *Fix:* Disconnect signal handlers in the `destroy` event or use `weakref`.

## 5. Verification Steps
Run in terminal to test the runtime:
```bash
python -c "
import os, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
print('✓ PyGObject runtime verified successfully in Python 3.13')
"
```
