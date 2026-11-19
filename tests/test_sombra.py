"""La sombra necesita superficie propia: hoy se dibuja fuera de la surface
del layer-shell y el compositor la recorta. El fix agranda la surface y corre
los márgenes para que la CARD siga en el mismo sitio.
"""
import toast_core as tm
import wayland_popup as wp


def test_surface_mayor_que_la_card():
    w, h = tm.surface_size(360, 120)
    assert w > 360 and h > 120
    assert w - 360 >= tm._SHADOW_PAD["left"] + tm._SHADOW_PAD["right"]
    assert h - 120 >= tm._SHADOW_PAD["top"] + tm._SHADOW_PAD["bottom"]


def test_margenes_compensan_el_pad():
    """La card sigue a 16 px del borde aunque la surface crezca."""
    top, right, bottom, left = tm.layer_margins("top-right", 16)
    assert top + tm._SHADOW_PAD["top"] == 16
    assert right + tm._SHADOW_PAD["right"] == 16
    assert top >= 0 and right >= 0


def test_el_offset_de_la_pila_no_se_come_el_pad():
    """Apilar no puede mover la card respecto del borde."""
    t0, _, _, _ = tm.layer_margins("top-right", 16, 0)
    t1, _, _, _ = tm.layer_margins("top-right", 16, 50)
    assert t1 - t0 == 50


def test_esquina_inferior_tambien_compensa():
    _, _, bottom, left = tm.layer_margins("bottom-left", 16, 20)
    assert bottom + tm._SHADOW_PAD["bottom"] == 36
    assert left + tm._SHADOW_PAD["left"] == 16


def test_apply_margins_con_pila_no_lanza(monkeypatch):
    """Regresión real: al quitar `offset` local quedó NameError en hover/pila."""
    puestos = {}
    monkeypatch.setattr(wp.Gtk4LayerShell, "set_margin",
                        lambda w, edge, val: puestos.__setitem__(str(edge), val))
    p = wp.WaylandPopup(corner="top-right", margin=16)
    p.window = object()
    p._card = None
    p._stack_margin = 40
    p._apply_margins()
    assert puestos, "no se aplicó ningún margen del layer-shell"
