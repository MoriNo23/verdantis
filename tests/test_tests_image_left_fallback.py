"""Metatest de sensibilidad: si el fallback de la imagen izquierda se rompe
(vuelve a la versión bugueada que NO cae al .desktop), el test principal lo
detecta.

Mismo patrón que test_tests_action_zones: se inyecta la versión rota con
try/finally y se verifica que el predicado de test_image_left_fallback
(slot que proviene del .desktop — píxel rojo inyectado) quedaría en rojo.

NOTA: el fallback encadena .desktop exacto → tema hicolor → placeholder. Romper
SOLO el lookup de .desktop ya no deja el slot vacío para app_names con icono
de tema ("Brave" → "brave", ver test_icon_from_theme_reintenta_en_minusculas),
y con el contrato nuevo (placeholder) tampoco: el test principal lo detecta
igual por PROCEDENCIA (el slot debe ser el rojo del .desktop inyectado, no el
logo real del tema ni el placeholder con la inicial).
"""

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import wayland_popup as wp
from wayland_popup import NotificationWidget

from test_image_left_fallback import _inject_desktop, _png, RED, _center_pixel


def test_metatest_image_left_test_detects_missing_fallback(tmp_path):
    """Con el lookup de .desktop roto, el slot NO puede provenir del desktop
    inyectado (rojo) → el test principal de test_image_left_fallback fallaría
    (sensibilidad verificada)."""
    _inject_desktop("Brave", _png(tmp_path, "brave.png", RED))
    wp._desktop_cache = {"brave": wp._desktop_cache["brave"]}  # conserva inyección

    orig = wp._get_app_icon_from_desktop
    try:
        # Versión bugueada: nunca resuelve el icono de escritorio
        wp._get_app_icon_from_desktop = lambda app, size=80, mode="cover": None
        w = NotificationWidget("Brave", "", "T", "cuerpo", None, None,
                               "#80cbc4")
        # Con el lookup de .desktop roto, el slot NO puede provenir del desktop
        # inyectado (rojo): queda vacío, cae al tema hicolor "brave" (no-rojo) o
        # al placeholder con la inicial. El predicado del test principal
        # (slot = rojo del .desktop) quedaría en rojo: sensibilidad OK.
        assert w._image_left_pb is None \
            or _center_pixel(w._image_left_pb) != (255, 0, 0, 255), (
            "el bug simulado deja el slot SIN el logo del .desktop inyectado"
            " — si esto no se cumple, el fallback del test principal no está "
            "testeando nada (el slot no puede seguir siendo el rojo del "
            "desktop con el lookup roto)"
        )
    finally:
        wp._get_app_icon_from_desktop = orig

    # Sanidad: con la versión real, el mismo input SÍ resuelve al .desktop
    w2 = NotificationWidget("Brave", "", "T", "cuerpo", None, None, "#80cbc4")
    assert w2._image_left_pb is not None
    assert _center_pixel(w2._image_left_pb) == (255, 0, 0, 255)