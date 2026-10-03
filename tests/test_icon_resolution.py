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


def test_widget_resuelve_logo_por_nombre_de_tema():
    """app_icon como NOMBRE DE TEMA pelado (sin archivo asociado): la fila de
    app debe mostrar el logo resuelto por ese nombre.

    El 43.5% de las notificaciones reales manda justo eso
    ("network-wireless-disconnected", "dialog-warning", ...). Antes el daemon
    las normalizaba a "" y esta vía del widget era código muerto."""
    widget = wp.NotificationWidget(
        app_name="ZuluBrowser",
        app_icon="firefox-nightly",
        titulo="Título", cuerpo="Cuerpo",
        icon_path="", image_path="", accent="#80cbc4",
    )
    assert widget._app_icon_pb is not None, (
        "un app_icon con nombre de tema debe resolver el logo de la fila"
    )
    # El tamaño exacto del slot (16×16, sin recortes) lo fijan los tests de
    # `_resample(mode="contain")`: el tema puede devolver 32×32 y antes esa
    # vía del widget ni siquiera pasaba por _resample.


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


# ── Modo contain: los iconos no cuadrados no se cortan ────────────────────
#
# `_resample` hacía center-crop del cuadrado central: un logo panorámico
# (32×16) perdía los extremos laterales al entrar en el slot 16×16. El logo de
# la fila de app se escala con `mode="contain"` (letterbox, preserva el aspect
# ratio); el avatar 80px sigue en cover porque su clip circular es por diseño.


def _pixbuf(w, h, extremos=False):
    """Pixbuf w×x×h construido desde bytes crudos (GdkPixbuf no expone set_pixel).

    `extremos=False`: cuerpo totalmente opaco (para medir el letterbox).
    `extremos=True`: bandas opacas en los 4 primeros/últimos píxeles (roja y
    verde) y el resto transparente — así se distingue con nitidez un
    center-crop (que se come los extremos) de un contain (que los preserva).
    Las bandas son de 4 px porque al reducir 32→16 una línea de 1 px se
    promedia con su vecino transparente y no sobrevive al reescalado."""
    from gi.repository import GLib
    banda = 4
    data = bytearray()
    for _y in range(h):
        for x in range(w):
            if not extremos:
                data += bytes((0, 0, 0xFF, 0xFF))       # azul opaco
            elif x < banda:
                data += bytes((0xFF, 0x00, 0x00, 0xFF))  # rojo
            elif x >= w - banda:
                data += bytes((0x00, 0xFF, 0x00, 0xFF))  # verde
            else:
                data += bytes((0, 0, 0, 0))             # transparente
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(data)), GdkPixbuf.Colorspace.RGB,
        True, 8, w, h, w * 4)


def _opaco_en(pb, x, y):
    """Alpha del píxel (x, y). Este binding de GdkPixbuf no expone get_pixel;
    se lee del buffer crudo igual que render_helpers.pixbuf_pixels."""
    raw = pb.get_pixels()
    n = pb.get_n_channels()
    off = y * pb.get_rowstride() + x * n
    return raw[off + 3] > 128 if n == 4 else True


def test_resample_contain_no_recorta_extremos():
    """32×16 → slot 16×16 con letterbox: el icono entra COMPLETO. Los dos
    extremos (columnas 0 y 31 del original) sobreviven en el slot.

    Con el center-crop viejo (cover) el slot sale VACÍO: los extremos son
    justamente lo que el recorte se come."""
    out = wp._resample(_pixbuf(32, 16, extremos=True), 16, mode="contain")
    assert (out.get_width(), out.get_height()) == (16, 16), (
        "el slot sigue siendo cuadrado (16×16), con bandas transparentes"
    )
    assert _opaco_en(out, 0, 8), (
        "el extremo izquierdo del icono desapareció: contain está haciendo "
        "center-crop (el modo viejo)"
    )
    assert _opaco_en(out, 15, 8), (
        "el extremo derecho del icono desapareció: contain está haciendo "
        "center-crop (el modo viejo)"
    )


def test_resample_contain_preserva_aspect_con_bandas():
    """Un 32×16 opaco escalado con contain ocupa la franja central completa y
    deja bandas transparentes arriba/abajo (no se deforma a cuadrado)."""
    out = wp._resample(_pixbuf(32, 16), 16, mode="contain")
    for y in (0, 1, 2, 3, 12, 13, 14, 15):
        assert not _opaco_en(out, 8, y), (
            "con letterbox la fila %d debe quedar transparente (el 32x16 ocupa "
            "las 8 filas centrales)" % y
        )
    for y in (4, 5, 6, 7, 8, 9, 10, 11):
        assert _opaco_en(out, 8, y), (
            "la franja central (fila %d, el icono) debe quedar opaca" % y
        )


def test_resample_contain_cuadrado_llena_el_slot():
    """Un icono ya cuadrado (16×16) con contain ocupa el slot completo: sin
    bandas ni cambios respecto a cover."""
    out = wp._resample(_pixbuf(16, 16), 16, mode="contain")
    assert (out.get_width(), out.get_height()) == (16, 16)
    for x, y in ((0, 0), (15, 15), (8, 8)):
        assert _opaco_en(out, x, y), (
            "un icono cuadrado debe llenar el slot en contain (vacío en %d,%d)"
            % (x, y)
        )


def test_resample_cover_sigue_centrando_para_el_avatar():
    """cover (default)=center-crop: es lo del avatar 80px, cuyo clip circular
    es por diseño. Sobre un 32×16 se come los dos extremos — el comportamiento
    que el logo de 16px ya NO quiere."""
    src = _pixbuf(32, 16, extremos=True)
    cover = wp._resample(src, 16)
    contain = wp._resample(src, 16, mode="contain")
    assert (cover.get_width(), cover.get_height()) == (16, 16)
    assert not _opaco_en(cover, 0, 8) and not _opaco_en(cover, 15, 8), (
        "cover debe=center-crop: con un 32x16 los extremos no sobreviven "
        "(el recorte se queda con las 16 columnas centrales, vacías)"
    )
    assert _opaco_en(contain, 0, 8) and _opaco_en(contain, 15, 8), (
        "contain es el que preserva los extremos: si no, los dos modos son "
        "indistinguibles y el test de contain no probaría nada"
    )
    # Y el avatar circular no pide contain:
    import inspect
    src_make = inspect.getsource(wp._make_circular)
    assert "contain" not in src_make, (
        "el avatar 80px debe seguir en cover (clip circular por diseño)"
    )


def test_logo_de_app_usa_contain():
    """La cadena del logo de 16 px pasa por contain: un tema que devuelve 32×32
    (p. ej. 'spectacle') o un archivo panorámico no se recorta en el slot."""
    import inspect
    src_init = inspect.getsource(wp.NotificationWidget.__init__)
    assert 'mode="contain"' in src_init, (
        "el logo de 16px debe escalar con contain (sin recortes)"
    )


def test_no_rescale_bilinear_en_iconos():
    """Contrato de fuente: en wayland_popup NO queda ningún `InterpType.BILINEAR`
    y TODO `scale_simple` vive DENTRO de `_resample` (los dos modos, cover y
    contain, escalan por el mismo helper). Cualquier nuevo rescale de iconos
    (avatar/logo) debe pasar por ahí; el banner (foto) mantiene su propio path
    y no aplica."""
    import inspect
    src = open(wp.__file__, encoding="utf-8").read()
    assert "InterpType.BILINEAR" not in src, (
        "rescale de iconos con BILINEAR reintroducido → calidad blanda"
    )
    n_total = src.count("scale_simple(")
    n_helper = inspect.getsource(wp._resample).count("scale_simple(")
    assert n_total == n_helper, (
        f"los {n_total} scale_simple del módulo deben estar en _resample "
        f"(hay {n_helper} allí): un rescale fuera del helper se libra de HYPER"
    )
    assert n_helper == 2, (
        "los dos modos de _resample (cover y contain) escalan con scale_simple"
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
