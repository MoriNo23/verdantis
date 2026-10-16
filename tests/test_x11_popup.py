"""Tests del fallback X11 (`src/x11_popup.py`).

Dos cosas sin display: el cálculo de posición puro (esquina + workarea +
margen → x,y, los 4 corners del one-shot) y la superficie de parámetros de
`NotificacionX11` — tiene que ser la MISMA que tenía el fallback Qt para que
la rejija del one-shot sea un cambio de módulo (spec `entrada-fallback`).
La ventana real no se construye acá (necesita display; los tests de la
decisión viven en `test_entrada.py` con fakes).
"""

import inspect
import sys

import x11_popup


# Workarea de un monitor 1600x900 con paneles que la corren a (100, 50):
# el origen distinto de (0,0) es lo que prueba el escenario "esquina con
# paneles" — la esquina se ancla al workarea, no al borde físico.
WORKAREA = (100, 50, 1600, 900)
MARGEN = 16
TAMANIO = (360, 240)  # _CARD_WIDTH x alto de la card


def test_esquina_top_left():
    assert x11_popup.posicion_esquina(
        "top-left", WORKAREA, MARGEN, TAMANIO) == (116, 66)


def test_esquina_top_right():
    # x = 100 + 1600 - 360 - 16; y = 50 + 16
    assert x11_popup.posicion_esquina(
        "top-right", WORKAREA, MARGEN, TAMANIO) == (1324, 66)


def test_esquina_bottom_left():
    # y = 50 + 900 - 240 - 16
    assert x11_popup.posicion_esquina(
        "bottom-left", WORKAREA, MARGEN, TAMANIO) == (116, 694)


def test_esquina_bottom_right():
    assert x11_popup.posicion_esquina(
        "bottom-right", WORKAREA, MARGEN, TAMANIO) == (1324, 694)


def test_margen_cero_ancla_al_borde_del_workarea():
    assert x11_popup.posicion_esquina(
        "bottom-right", WORKAREA, 0, TAMANIO) == (1340, 710)


def test_superficie_igual_a_la_vieja_qt():
    """La rejija del one-shot no puede recibir kwargs nuevos: mismos 8."""
    params = inspect.signature(x11_popup.NotificacionX11.__init__).parameters
    assert set(params) - {"self"} == {
        "titulo", "cuerpo", "icon_path", "image_path",
        "duration", "margin", "corner", "accent",
    }, "la superficie de NotificacionX11 debe ser la de NotificacionPersonalizada"


def test_construccion_sin_display_guarda_parametros():
    n = x11_popup.NotificacionX11(
        titulo="T", cuerpo="B", icon_path="/i.png", image_path=None,
        duration=1234, margin=8, corner="bottom-left", accent="#fff")
    assert (n.titulo, n.cuerpo, n.icon_path, n.image_path) == (
        "T", "B", "/i.png", None)
    assert (n.duration, n.margin, n.corner, n.accent) == (
        1234, 8, "bottom-left", "#fff")
    assert n.window is None, "sin display la ventana se construye en show()"


def test_import_del_fallback_no_carga_qt():
    """Spec `entrada-fallback`: ningún path carga PyQt6 ni el módulo Qt."""
    assert not any(m.startswith("PyQt6") for m in sys.modules), (
        "importar x11_popup cargó PyQt6: el fallback es GTK como todo el proyecto"
    )
