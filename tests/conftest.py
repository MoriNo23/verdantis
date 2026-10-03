import os
import sys

# conftest corre ANTES que cualquier módulo de test: es el dueño único del
# path hacia src/ y del GDK_BACKEND. Los archivos de test no repiten este
# preámbulo (antes lo copiaban los 31); el orden "wayland_popup primero entre
# los imports gi" se sigue respetando dentro de cada módulo (pitfall Gdk 3.0).
# Excepción deliberada: test_version_constant.py conserva su propio sys.path
# porque declara que debe poder correr aislado (fuera de pytest).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# Si hay un display Wayland real (WAYLAND_DISPLAY seteado, sesión de Mori),
# usamos 'wayland' para que GtkLayerShell.is_supported() sea True y los tests
# de layer-shell (test_dbus_contract, test_click_pwa) funcionen. Si no hay
# display (headless puro / mutmut), forzamos 'offscreen' para que gi no crashee.
if os.environ.get("WAYLAND_DISPLAY"):
    os.environ["GDK_BACKEND"] = "wayland"
else:
    os.environ["GDK_BACKEND"] = "offscreen"
