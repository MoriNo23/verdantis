"""
Tests unitarios para la resolución de iconos de proveniencia.

Bug reportado: cuando una notificación NO trae imagen (image_path vacío),
debe mostrar el icono de la app de origen (terminal, navegador, etc.) usando
el .desktop de la app. Si esto falla, el avatar queda vacío.

Estos tests validan el fix en wayland_popup.py:
- _icon_from_theme usa Gtk.IconTheme.get_for_screen() (no get_default())
"""
import os
import sys
import base64

os.environ.setdefault("GDK_BACKEND", "wayland")

if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "offscreen"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GdkPixbuf

import wayland_popup as wp


def _make_desktop(tmpdir, name, desktop_id, icon):
    path = os.path.join(tmpdir, f"{desktop_id}.desktop")
    with open(path, "w") as f:
        f.write(f"[Desktop Entry]\nName={name}\nIcon={icon}\nType=Application\n")
    return path


def _setup_cache(tmpdir):
    # Limpiar cache y usar SOLO nuestro tmpdir (aislar del sistema)
    wp._DESKTOP_DIRS[:] = [tmpdir]
    wp._desktop_cache = None  # forzar re-interpretación del cache
    # NOTA: los .desktop deben crearse ANTES de llamar a _setup_cache,
    # porque _rebuild_desktop_cache() lee el directorio en ese momento.
    wp._rebuild_desktop_cache()


def test_find_desktop_file_by_app_name(tmpdir):
    _make_desktop(tmpdir, "ZuluBrowser", "zulubrowser", "firefox-nightly")
    _setup_cache(tmpdir)
    found = wp._find_desktop_file("ZuluBrowser")
    assert found is not None
    assert found.endswith("zulubrowser.desktop")


def test_get_app_icon_from_desktop_with_theme_icon(tmpdir):
    """
    App con Icon=nombre-de-tema. Debe resolver via _icon_from_theme y
    devolver un GdkPixbuf no-None (icono de proveniencia).
    Usamos 'firefox-nightly' que resuelve con Gtk.IconTheme.new() (el fix).
    """
    _make_desktop(tmpdir, "ZuluBrowser", "zulubrowser", "firefox-nightly")
    _setup_cache(tmpdir)
    pb = wp._get_app_icon_from_desktop("ZuluBrowser", 80)
    assert pb is not None, "El icono de proveniencia NO se resolvió (bug)"
    assert isinstance(pb, GdkPixbuf.Pixbuf)


def test_get_app_icon_from_desktop_with_absolute_path(tmpdir):
    """Icono con ruta absoluta debe cargarse directo desde archivo."""
    png_path = os.path.join(tmpdir, "icono.png")
    # Crear un PNG válido en memoria y guardarlo
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    pix.fill(0x1E1E2EFF)  # color sólido válido
    pix.savev(png_path, "png", [], [])
    _make_desktop(tmpdir, "TermAppX", "termappx", png_path)
    _setup_cache(tmpdir)
    pb = wp._get_app_icon_from_desktop("TermAppX", 80)
    assert pb is not None
    assert isinstance(pb, GdkPixbuf.Pixbuf)


def test_icon_from_theme_returns_pixbuf():
    """_icon_from_theme debe devolver pixbuf para un icono existente."""
    pb = wp._icon_from_theme("firefox-nightly", 16)
    assert pb is not None, "_icon_from_theme('firefox-nightly') devolvió None"
    assert isinstance(pb, GdkPixbuf.Pixbuf)


def test_icon_from_theme_fallback_to_new_when_no_screen(monkeypatch):
    """
    Si Gdk.Screen.get_default() es None (caso headless/Wayland sin screen),
    _icon_from_theme debe usar Gtk.IconTheme.new() y no crashear.
    """
    monkeypatch.setattr(Gdk.Screen, "get_default", staticmethod(lambda: None))
    # No debe lanzar excepción; puede devolver None si el tema no resuelve
    pb = wp._icon_from_theme("firefox-nightly", 16)
    assert pb is None or isinstance(pb, GdkPixbuf.Pixbuf)


def test_notificationwidget_sets_avatar_without_image(tmpdir):
    """
    INTEGRACIÓN: NotificationWidget sin image_path ni icon_path debe
    terminar con _avatar_pb no-None (icono de proveniencia de la app).
    """
    _make_desktop(tmpdir, "NavegadorZ", "navegadorz", "firefox-nightly")
    _setup_cache(tmpdir)
    widget = wp.NotificationWidget(
        app_name="NavegadorZ",
        app_icon="",
        titulo="Título",
        cuerpo="Cuerpo",
        icon_path="",
        image_path="",
        accent="#80cbc4",
    )
    assert widget._avatar_pb is not None, (
        "NotificationWidget no colocó el avatar de proveniencia sin imagen"
    )
    assert isinstance(widget._avatar_pb, GdkPixbuf.Pixbuf)
