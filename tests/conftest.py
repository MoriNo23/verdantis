import os

# Si hay un display Wayland real (WAYLAND_DISPLAY seteado, sesión de Mori),
# usamos 'wayland' para que GtkLayerShell.is_supported() sea True y los tests
# de layer-shell (test_dbus_contract, test_click_pwa) funcionen. Si no hay
# display (headless puro / mutmut), forzamos 'offscreen' para que gi no crashee.
if os.environ.get("WAYLAND_DISPLAY"):
    os.environ["GDK_BACKEND"] = "wayland"
else:
    os.environ["GDK_BACKEND"] = "offscreen"
