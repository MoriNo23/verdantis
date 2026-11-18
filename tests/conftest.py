import os
import sys

# conftest corre ANTES que cualquier módulo de test: es el dueño único del
# path hacia src/ y del GDK_BACKEND. Los archivos de test no repiten este
# preámbulo. wayland_popup carga libgtk4-layer-shell con RTLD_GLOBAL antes de
# gi (pitfall del orden de linking con libwayland en GTK4).
# Excepción deliberada: test_version_constant.py conserva su propio sys.path
# porque declara que debe poder correr aislado (fuera de pytest).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# Si hay un display Wayland real (WAYLAND_DISPLAY seteado, sesión de Mori),
# usamos 'wayland' para que Gtk4LayerShell.is_supported() sea True y los tests
# de layer-shell (test_dbus_contract, test_click_pwa) funcionen. Si no hay
# display (headless puro / mutmut), forzamos 'offscreen' para que gi no crashee.
if os.environ.get("WAYLAND_DISPLAY"):
    os.environ["GDK_BACKEND"] = "wayland"
else:
    # GTK4 no tiene backend 'offscreen' (era GTK3): el headless real es
    # 'broadway'. Sin display los tests de Snapshot igual pasan, pero con
    # 'offscreen' Gdk emitía "No such backend" en cada corrida de CI.
    os.environ["GDK_BACKEND"] = "broadway"
