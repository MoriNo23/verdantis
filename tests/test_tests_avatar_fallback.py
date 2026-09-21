"""Metatest de sensibilidad: si el fallback de avatar se rompe (vuelve a la
versión bugueada que NO cae al .desktop), el test principal lo detecta.

Mismo patrón que test_tests_action_zones: se inyecta la versión rota con
try/finally y se verifica que el predicado de test_avatar_fallback
(avatar no-None con .desktop disponible) quedaría en rojo.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import wayland_popup as wp
from wayland_popup import NotificationWidget

from test_avatar_fallback import _inject_desktop, _png, RED


def test_metatest_avatar_test_detects_missing_fallback(tmp_path):
    """Con el fallback roto (None), el avatar queda vacío → el test principal
    de test_avatar_fallback fallaría (sensibilidad verificada)."""
    _inject_desktop("Brave", _png(tmp_path, "brave.png", RED))
    wp._desktop_cache = {"brave": wp._desktop_cache["brave"]}  # conserva inyección

    orig = wp._get_app_icon_from_desktop
    try:
        # Versión bugueada: nunca resuelve el icono de escritorio
        wp._get_app_icon_from_desktop = lambda app, size: None
        w = NotificationWidget("Brave", "", "T", "cuerpo", None, None,
                               "#80cbc4")
        assert w._avatar_pb is None, (
            "el bug simulado deja el avatar vacío — si esto no se cumple, el "
            "fallback del test principal no está testeando nada"
        )
    finally:
        wp._get_app_icon_from_desktop = orig

    # Sanidad: con la versión real, el mismo input SÍ resuelve
    w2 = NotificationWidget("Brave", "", "T", "cuerpo", None, None, "#80cbc4")
    assert w2._avatar_pb is not None