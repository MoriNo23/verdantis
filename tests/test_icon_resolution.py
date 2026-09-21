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


def test_resample_scala_con_hyper(monkeypatch):
    """Reporte: los iconos (avatar 80px y logo de app 16px) se veían blandos
    en pequeño porque los rescale usaban BILINEAR. Contrato: todo rescale de
    iconos pasa por _resample con HYPER (nítido al reducir, más limpio al
    agrandar favicons chicos al slot del avatar)."""
    calls = []
    orig = GdkPixbuf.Pixbuf.scale_simple

    def spy(self, w, h, interp):
        calls.append(interp)
        return orig(self, w, h, interp)

    monkeypatch.setattr(GdkPixbuf.Pixbuf, "scale_simple", spy)
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 32, 32)
    pb.fill(0x1E1E2EFF)
    out = wp._resample(pb, 80)
    assert out.get_width() == 80
    assert calls and all(c is GdkPixbuf.InterpType.HYPER for c in calls), (
        "el rescale de iconos debe usar HYPER; si vuelve BILINEAR los "
        "avatares/logos se ven mal en pequeño (reporte usuario)"
    )


def test_no_rescale_bilinear_en_iconos():
    """Contrato de fuente: en wayland_popup NO queda ningún `InterpType.BILINEAR`
    y `scale_simple` solo existe DENTRO de _resample. Cualquier nuevo rescale
    de iconos (avatar/logo) debe pasar por el helper HYPER; el banner (foto)
    mantiene su propio path y no aplica."""
    src = open(wp.__file__, encoding="utf-8").read()
    assert "InterpType.BILINEAR" not in src, (
        "rescale de iconos con BILINEAR reintroducido → calidad blanda"
    )
    assert src.count("scale_simple(") == 1, (
        "el único scale_simple debe vivir en _resample (HYPER)"
    )


def test_icon_from_theme_reintenta_en_minusculas(monkeypatch):
    """
    RED del reporte: el lookup de IconTheme es case-sensitive y los senders
    mandan app_name capitalizado ("Brave", "YouTube") mientras los iconos del
    tema son minúsculas ("brave"). Con "Brave" el lookup da None → _icon_from_theme
    debe reintentar en minúsculas o el slot izquierdo queda vacío.
    """
    seen = []

    class _Info:
        def load_icon(self):
            return GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)

    class _Theme:
        def lookup_icon(self, name, size, flags):
            seen.append(name)
            return _Info() if name == "brave" else None

    fake = _Theme()
    monkeypatch.setattr(Gtk.IconTheme, "get_for_screen",
                        staticmethod(lambda screen: fake))
    monkeypatch.setattr(Gtk.IconTheme, "new", staticmethod(lambda: fake))

    pb = wp._icon_from_theme("Brave", 16)
    assert pb is not None, \
        "app_name capitalizado debe resolver al icono del tema en minúsculas"
    assert seen == ["Brave", "brave"], \
        "sin el reintento en minúsculas el lookup capitalizado da None"


def test_icon_from_theme_fallback_to_new_when_no_screen(monkeypatch):
    """
    Si Gdk.Screen.get_default() es None (caso headless/Wayland sin screen),
    _icon_from_theme debe usar Gtk.IconTheme.new() y no crashear.
    """
    monkeypatch.setattr(Gdk.Screen, "get_default", staticmethod(lambda: None))
    # No debe lanzar excepción; puede devolver None si el tema no resuelve
    pb = wp._icon_from_theme("firefox-nightly", 16)
    assert pb is None or isinstance(pb, GdkPixbuf.Pixbuf)


def test_notificationwidget_avatar_falls_back_without_sender_image(tmpdir):
    """
    Contrato nuevo (fallback): sin imagen del sender (image-path/image-data),
    el avatar cae al icono de la app — match EXACTO del .desktop (logo de
    Brave / icono de la PWA de YouTube). Con .desktop resolvible → slot 80px.
    """
    png_path = os.path.join(tmpdir, "navegador.png")
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 32, 32)
    pix.fill(0x1E1E2EFF)
    pix.savev(png_path, "png", [], [])
    _make_desktop(tmpdir, "NavegadorZ", "navegadorz", png_path)
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
        "sin imagen del sender el avatar debe caer al icono de la app (.desktop exacto)"
    )
    # El slot izquierdo se reserva: texto con columna reducida
    assert widget._eff_text_width() <= 240


def test_notificationwidget_no_slot_when_nothing_resolves(tmpdir):
    """
    Sin imagen del sender Y sin icono de la app resolvible (desktop con icono
    inexistente + app_name sin icono de tema) → _avatar_pb None → el layout no
    reserva el slot (texto a ancho completo).
    """
    _make_desktop(tmpdir, "NavegadorZ", "navegadorz", "no_existe_icono_xyz_1234")
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
    assert widget._avatar_pb is None, (
        "sin imagen y sin icono de app no debe haber slot de avatar fantasma"
    )
    assert widget._eff_text_width() > 240


def test_imagedata_becomes_avatar_tab_icon():
    """image-data (lo que manda el navegador: icono del tab) → avatar 80px,
    NO al banner grande (antes el favicon se estiraba a 260x140)."""
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 8, 8)
    pb.fill(0xFFFFFFFF)
    raw = (
        pb.get_width(), pb.get_height(), pb.get_rowstride(),
        pb.get_has_alpha(), pb.get_bits_per_sample(), pb.get_n_channels(),
        pb.get_pixels(),
    )
    widget = wp.NotificationWidget(
        app_name="Brave", app_icon="", titulo="t", cuerpo="c",
        icon_path="", image_path="", accent="#80cbc4",
        image_data_raw=raw,
    )
    assert widget._avatar_pb is not None, "image-data debe poblar el avatar (icono del tab)"
    assert widget._image_pb is None, "image-data NO debe ir al banner grande"
    assert widget._eff_text_width() == 240  # con avatar: columna de texto normal
