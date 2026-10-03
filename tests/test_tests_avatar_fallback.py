"""Metatest de sensibilidad: si el fallback de avatar se rompe (vuelve a la
versión bugueada que NO cae al .desktop), el test principal lo detecta.

Mismo patrón que test_tests_action_zones: se inyecta la versión rota con
try/finally y se verifica que el predicado de test_avatar_fallback
(avatar que proviene del .desktop — píxel rojo inyectado) quedaría en rojo.

NOTA: el fallback encadena .desktop exacto → tema hicolor. Romper SOLO el
lookup de .desktop ya no deja el avatar vacío para app_names con icono de
tema ("Brave" → "brave", ver test_icon_from_theme_reintenta_en_minusculas):
el test principal lo detecta igual por PROCEDENCIA (el avatar debe ser rojo
del .desktop inyectado, no el logo real del tema).
"""

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import wayland_popup as wp
from wayland_popup import NotificationWidget

from test_avatar_fallback import _inject_desktop, _png, RED, _center_pixel


def test_metatest_avatar_test_detects_missing_fallback(tmp_path):
    """Con el fallback roto (None), el avatar queda vacío → el test principal
    de test_avatar_fallback fallaría (sensibilidad verificada)."""
    _inject_desktop("Brave", _png(tmp_path, "brave.png", RED))
    wp._desktop_cache = {"brave": wp._desktop_cache["brave"]}  # conserva inyección

    orig = wp._get_app_icon_from_desktop
    try:
        # Versión bugueada: nunca resuelve el icono de escritorio
        wp._get_app_icon_from_desktop = lambda app, size=80, mode="cover": None
        w = NotificationWidget("Brave", "", "T", "cuerpo", None, None,
                               "#80cbc4")
        # Con el lookup de .desktop roto, el avatar NO puede provenir del
        # desktop inyectado (rojo): o queda vacío (sin icono de tema) o cae
        # al tema hicolor "brave" (no-rojo). El predicado del test principal
        # (avatar = rojo del .desktop) quedaría en rojo: sensibilidad OK.
        assert w._avatar_pb is None \
            or _center_pixel(w._avatar_pb) != (255, 0, 0, 255), (
            "el bug simulado deja el avatar SIN el logo del .desktop inyectado"
            " — si esto no se cumple, el fallback del test principal no está "
            "testeando nada (el avatar no puede seguir siendo el rojo del "
            "desktop con el lookup roto)"
        )
    finally:
        wp._get_app_icon_from_desktop = orig

    # Sanidad: con la versión real, el mismo input SÍ resuelve al .desktop
    w2 = NotificationWidget("Brave", "", "T", "cuerpo", None, None, "#80cbc4")
    assert w2._avatar_pb is not None
    assert _center_pixel(w2._avatar_pb) == (255, 0, 0, 255)