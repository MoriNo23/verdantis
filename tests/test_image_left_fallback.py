"""
RED: cadena de la imagen izquierda — sin icono del sender, el slot izquierdo
cae al icono de la app (match EXACTO de .desktop primero, luego tema hicolor)
y, si NADA resuelve, al placeholder con la inicial (el slot nunca desaparece:
spec `toast-imagen-izquierda`, requirement "La imagen izquierda siempre está
presente").

Origen del bug (reportado): los directos de YouTube llegan vía service-worker
SIN image-data (icono del tab) ni image-path; antes el slot izquierdo quedaba
vacío aunque la fila de app sí resolviera el logo (Brave) a 16px.

El cache de .desktop se INYECTA en el módulo (determinista, no depende de qué
apps estén instaladas): el match exacto por Name también cubre PWAs — un
brave-<appid>.desktop tiene Name=YouTube, así que "YouTube" resuelve igual.
"""
import os


# wayland_popup PRIMERO: fija Gdk 3.0 antes de que el import suelto de Gdk
# cargue 4.0 y crashee (pitfall documentado en AGENTS.md).
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import pytest

import wayland_popup as wp
from wayland_popup import NotificationWidget

RED = 0xFF0000FF   # rojo opaco (RGBA nativo de GdkPixbuf)
GREEN = 0x00FF00FF  # verde opaco


def _png(tmp_path, name, pixel):
    """PNG sólido de 64x64 con el color dado (para el Icon inyectado)."""
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 64, 64)
    pb.fill(pixel)
    path = os.path.join(str(tmp_path), name)
    pb.savev(path, "png", [], [])
    return path


def _inject_desktop(app_name, icon_path):
    """Inyecta un .desktop en el cache del módulo con match EXACTO por Name."""
    d = os.path.dirname(icon_path)
    p = os.path.join(d, app_name.lower() + ".desktop")
    with open(p, "w") as f:
        f.write("[Desktop Entry]\nName={}\nIcon={}\nStartupWMClass=\n".format(
            app_name, icon_path))
    wp._desktop_cache = {
        app_name.lower(): [{
            "path": p, "Name": app_name, "Icon": icon_path, "StartupWMClass": "",
        }]
    }


@pytest.fixture(autouse=True)
def _restore_cache():
    yield
    wp._desktop_cache = None  # el próximo acceso re-construye el cache del sistema


def _center_pixel(pb):
    """Color del píxel central de un pixbuf (RGBA por canal)."""
    w, h = pb.get_width(), pb.get_height()
    rowstride = pb.get_rowstride()
    data = pb.get_pixels()
    off = (h // 2) * rowstride + (w // 2) * pb.get_n_channels()
    return (data[off], data[off + 1], data[off + 2], data[off + 3])


def _build(app_name, icon_path=None, image_data_raw=None):
    return NotificationWidget(
        app_name, "", "T", "cuerpo", icon_path, None, "#80cbc4",
        image_data_raw=image_data_raw,
    )


def test_image_left_falls_back_to_desktop_icon(tmp_path):
    """Sin icono del sender, el slot muestra el .desktop exacto (logo de Brave)."""
    _inject_desktop("Brave", _png(tmp_path, "brave.png", RED))
    w = _build("Brave")
    assert w._image_left_pb is not None, (
        "sin image-data ni image-path el slot debe caer al .desktop de la app"
    )
    # La imagen izquierda viene del .desktop (rojo sólido inyectado), no de la nada
    assert _center_pixel(w._image_left_pb) == (255, 0, 0, 255), (
        "el slot no proviene del icono del .desktop inyectado"
    )


def test_image_left_fallback_pwa_youtube(tmp_path):
    """YouTube (PWA): el .desktop brave-<appid> con Name=YouTube resuelve por
    match exacto de Name, igual que el app row a 16px."""
    _inject_desktop("YouTube", _png(tmp_path, "youtube.png", RED))
    w = _build("YouTube")
    assert w._image_left_pb is not None
    assert _center_pixel(w._image_left_pb) == (255, 0, 0, 255)


def test_image_left_fallback_unknown_app_placeholder(tmp_path):
    """App desconocida (sin .desktop ni icono de tema): el slot NO desaparece,
    cae al placeholder de 80 px con la inicial del nombre de la app.

    CONTRATO NUEVO (spec `toast-imagen-izquierda`): antes esta app se quedaba
    sin slot y el layout saltaba a la variante ancha. Este test está ROJO a
    propósito contra el código actual."""
    w = _build("zzz_no_existe_xa")
    assert w._image_left_pb is not None, (
        "nada resuelve -> el slot de imagen izquierda debe caer al placeholder "
        "80x80 con la inicial, nunca desaparecer (spec: La imagen izquierda "
        "siempre está presente)"
    )
    assert (w._image_left_pb.get_width(), w._image_left_pb.get_height()) == (80, 80), (
        "el placeholder del slot es de 80x80, no %sx%s"
        % (w._image_left_pb.get_width(), w._image_left_pb.get_height())
    )
    assert w._eff_text_width() == 240, (
        "con el slot siempre presente la columna de texto es la única del "
        "contrato (240 px), no la variante ancha: %s" % (w._eff_text_width(),)
    )


def test_image_left_sender_icon_beats_fallback(tmp_path):
    """Precedencia intacta: si el sender manda icono real, ese gana — el
    fallback NO pisa al icono del tab."""
    _inject_desktop("Brave", _png(tmp_path, "brave.png", RED))
    sender_icon = _png(tmp_path, "tab.png", GREEN)
    w = _build("Brave", icon_path=sender_icon)
    assert w._image_left_pb is not None
    # El slot viene del icono del sender (verde), no del .desktop (rojo)
    assert _center_pixel(w._image_left_pb) == (0, 255, 0, 255)


def test_image_left_fallback_image_data_beats_desktop(tmp_path):
    """image-data (icono del tab real) también gana sobre el fallback."""
    _inject_desktop("Brave", _png(tmp_path, "brave.png", RED))
    tab_png = _png(tmp_path, "tabdata.png", GREEN)
    pb = GdkPixbuf.Pixbuf.new_from_file(tab_png)
    w, h = pb.get_width(), pb.get_height()
    image_data_raw = (w, h, pb.get_rowstride(), True, 8, 4,
                      bytes(pb.get_pixels()))
    w = _build("Brave", image_data_raw=image_data_raw)
    assert w._image_left_pb is not None
    assert _center_pixel(w._image_left_pb) == (0, 255, 0, 255)