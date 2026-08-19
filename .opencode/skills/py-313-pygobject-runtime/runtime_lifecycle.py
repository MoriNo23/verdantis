"""Runtime Lifecycle & Memory-Safe Dispatcher for Python 3.13 + PyGObject."""

import os
import sys
import threading
import weakref
from pathlib import Path
from typing import Callable, Any, TypeVar

# 1. Automatic Typelib Resolution
SYSTEM_TYPELIB_PATHS = [
    "/usr/lib64/girepository-1.0",
    "/usr/lib/x86_64-linux-gnu/girepository-1.0",
    "/usr/lib/girepository-1.0",
    "/usr/local/lib64/girepository-1.0",
    "/usr/local/lib/girepository-1.0"
]
existing_path = os.environ.get("GI_TYPELIB_PATH", "")
valid_paths = [p for p in SYSTEM_TYPELIB_PATHS if Path(p).exists()]
if existing_path:
    valid_paths.append(existing_path)
os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(valid_paths)

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

try:
    gi.require_version("GtkLayerShell", "0.1")
except ValueError as err:
    sys.stderr.write(f"CRITICAL: GtkLayerShell-0.1 typelib missing: {err}\n")

from gi.repository import GLib, GObject

T = TypeVar("T")

class ThreadSafeDispatcher:
    """Thread-safe UI dispatcher targeting the GTK/GLib MainLoop."""
    _main_thread_id = threading.get_ident()

    @classmethod
    def run_on_main_thread(
        cls,
        func: Callable[..., T],
        *args: Any,
        priority: int = GLib.PRIORITY_DEFAULT,
        **kwargs: Any
    ) -> None:
        if threading.get_ident() == cls._main_thread_id:
            func(*args, **kwargs)
            return

        def _wrapper() -> bool:
            func(*args, **kwargs)
            return False  # GLib.SOURCE_REMOVE

        GLib.idle_add(_wrapper, priority=priority)

class SafeSignalRegistry:
    """Weakref-backed signal manager to prevent memory leaks upon widget destruction."""
    def __init__(self, target_instance: object) -> None:
        self._weak_target = weakref.ref(target_instance)
        self._handlers: list[tuple[GObject.Object, int]] = []

    def connect(self, emitter: GObject.Object, signal_name: str, method_name: str) -> int:
        def _invoker(*args: Any) -> Any:
            instance = self._weak_target()
            if instance is not None:
                fn = getattr(instance, method_name, None)
                if callable(fn):
                    return fn(*args)
            return None

        handler_id = emitter.connect(signal_name, _invoker)
        self._handlers.append((emitter, handler_id))
        return handler_id

    def disconnect_all(self) -> None:
        for emitter, handler_id in self._handlers:
            if GObject.signal_handler_is_connected(emitter, handler_id):
                emitter.disconnect(handler_id)
        self._handlers.clear()
