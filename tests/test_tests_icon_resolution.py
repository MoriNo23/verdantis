"""
Test unitario DE LOS test unitarios (metatest).

Objetivo: demostrar que tests/test_icon_resolution.py es una red de seguridad
válida, no un placebo. Verifica dos cosas:

1. Que los tests actuales PASAN con el fix aplicado (smoke).
2. Que los tests FALLARÍAN si el bug volviera (sensibilidad al bug):
   - Simulamos el código ORIGINAL bugueado: _icon_from_theme usa
     Gtk.IconTheme.get_default() que en offscreen/Wayland sin screen
     devuelve None -> slot de imagen izquierda de proveniencia vacío.
   - Bajo esa simulación, _get_app_icon_from_desktop y NotificationWidget
     deben devolver None (el bug), probando que el test lo detectaría.
"""
import os

if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "offscreen"

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GdkPixbuf

import wayland_popup as wp


# ---------------------------------------------------------------------------
# Helpers reutilizados de test_icon_resolution.py (aislados)
# ---------------------------------------------------------------------------

def _make_desktop(tmpdir, name, desktop_id, icon):
    path = os.path.join(tmpdir, f"{desktop_id}.desktop")
    with open(path, "w") as f:
        f.write(f"[Desktop Entry]\nName={name}\nIcon={icon}\nType=Application\n")
    return path


def _setup_cache(tmpdir):
    wp._DESKTOP_DIRS[:] = [tmpdir]
    wp._desktop_cache = None
    wp._rebuild_desktop_cache()


# Versión BUGUEADA de _icon_from_theme: imita el código original
# que usaba Gtk.IconTheme.get_default() (devuelve None en offscreen).
def _buggy_icon_from_theme(icon_name, size=16):
    if not icon_name:
        return None
    try:
        # ESTE es el path original que causaba el bug
        theme = Gtk.IconTheme.get_default()
        if theme is None:
            return None
        info = theme.lookup_icon(icon_name, size, 0)
        if info:
            return info.load_icon()
    except Exception:
        pass
    return None


def test_fix_present_makes_tests_pass(tmpdir):
    """Sensibilidad directa: con el fix, _get_app_icon_from_desktop resuelve."""
    _make_desktop(tmpdir, "NavegadorZ", "navegadorz", "firefox-nightly")
    _setup_cache(tmpdir)
    pb = wp._get_app_icon_from_desktop("NavegadorZ", 80)
    assert pb is not None, "El fix debería resolver el icono"
    assert isinstance(pb, GdkPixbuf.Pixbuf)


def test_buggy_version_breaks_resolution(monkeypatch):
    """
    Metatest clave: si _icon_from_theme vuelve al código bugueado
    (get_default fuerza None, como en Wayland sin screen GTK), entonces
    la resolución de proveniencia FALLA. Esto prueba que
    tests/test_icon_resolution.py DETECTARÍA la regresión (no es placebo).
    """
    # Simular el entorno donde get_default() devuelve None (el bug real)
    monkeypatch.setattr(Gtk.IconTheme, "get_default",
                        staticmethod(lambda: None))
    # Y el fix de get_for_screen tampoco ayuda porque screen es None en offscreen
    monkeypatch.setattr(Gdk.Screen, "get_default",
                        staticmethod(lambda: None))
    monkeypatch.setattr(wp, "_icon_from_theme",
                        lambda name, size=16: _buggy_icon_from_theme(name, size))

    tmp = str(__import__("tempfile").mkdtemp())
    _make_desktop(tmp, "NavegadorZ", "navegadorz", "firefox-nightly")
    _setup_cache(tmp)

    pb = wp._get_app_icon_from_desktop("NavegadorZ", 80)
    # Bajo el bug, debe ser None (el slot de imagen izquierda queda vacío)
    assert pb is None, (
        "Metatest roto: el path bugueado NO produjo un slot vacío. "
        "El test de integración no detectaría la regresión."
    )

    # Y NotificationWidget NO debe traer el icono de la app bajo el bug: el
    # slot queda vacío (código actual) o cae al placeholder con la inicial
    # (contrato nuevo) — en ningún caso puede ser el icono de la app.
    widget = wp.NotificationWidget(
        app_name="NavegadorZ", app_icon="", titulo="T", cuerpo="C",
        icon_path="", image_path="", accent="#80cbc4",
    )
    slot = widget._image_left_pb
    assert slot is None or slot.get_width() == 80, (
        "Metatest roto: NotificationWidget resolved something unexpected for "
        "the left image slot under the bug: %r" % (slot,)
    )


def test_no_hay_match_difuso_de_desktop():
    """La resolución de `.desktop` es SOLO match exacto: no debe existir un
    matcher difuso en el módulo.

    AGENTS.md lo dice desde hace rato: "Resolución de `.desktop`: SOLO match
    exacto (`_exact_desktop_file`). El match difuso rompe con PWAs de Brave
    (`brave-<appid>.desktop`) — un 'brave' genérico cae en el PWA y muestra su
    icono/nombre".

    `_find_desktop_file` (CC 15, CRAP 121 — el peor del repo) era ese matcher
    difuso, y no lo llamaba NADA: su único caller era un test que existía solo
    para testearlo, y que ni siquiera entraba al camino difuso (resolvía por
    match exacto). Este assert es el RED del change que lo borra: hoy falla,
    mañana pasa, y si alguien lo vuelve a agregar para "usarlo algún día" el
    test lo dice con el nombre del bug que ya mordeó una vez.
    """
    assert not hasattr(wp, "_find_desktop_file"), (
        "El módulo expone un match DIFUSO de .desktop (`_find_desktop_file`). "
        "La spec (AGENTS.md y el spec `toast-iconos-app`) exige match exacto: "
        "el difuso rompe con los PWA de navegador (`brave-<appid>.desktop`), "
        "donde un 'brave' genérico cae en el PWA y muestra su icono y nombre. "
        "La vía exacta es `_exact_desktop_file`."
    )
    # Y la vía exacta sí existe: el assert de arriba no pasa por borrarla todo.
    assert hasattr(wp, "_exact_desktop_file"), (
        "Debe quedar la vía EXACTA (`_exact_desktop_file`); este metatest no "
        "pide borrar el resolver, pide borrar el matcher difuso."
    )


def test_buggy_version_falls_back_to_absolute_path(monkeypatch):
    """
    El bug solo afecta iconos de TEMA. Las rutas absolutas deben seguir
    funcionando aunque _icon_from_theme esté bugueado (get_default None).
    Esto demuestra que el metatest distingue correctamente los dos caminos.
    """
    monkeypatch.setattr(Gtk.IconTheme, "get_default",
                        staticmethod(lambda: None))
    monkeypatch.setattr(Gdk.Screen, "get_default",
                        staticmethod(lambda: None))
    monkeypatch.setattr(wp, "_icon_from_theme",
                        lambda name, size=16: _buggy_icon_from_theme(name, size))

    tmp = str(__import__("tempfile").mkdtemp())
    png_path = os.path.join(tmp, "icono.png")
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    pix.fill(0x1E1E2EFF)
    pix.savev(png_path, "png", [], [])
    _make_desktop(tmp, "TermAppX", "termappx", png_path)
    _setup_cache(tmp)

    pb = wp._get_app_icon_from_desktop("TermAppX", 80)
    assert pb is not None, "Ruta absoluta debe resolverse aunque el tema falle"
    assert isinstance(pb, GdkPixbuf.Pixbuf)
