"""El cierre deja de ser una X rosa flotante: botón circular neutro.

Usa los MISMOS tokens que los botones de acción (7 % / 11 % / 4 %) y elimina
el flood rojo del rail. El hit-rect sigue siendo el rail completo de 28 px.
"""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

import toast_core as tm
from test_render_gsk import _widget


def test_reposo_usa_los_tokens_de_los_botones_de_accion():
    fill, glyph, sink = tm.close_style()
    assert fill == tm._VIB_BTN_ALPHA
    assert glyph < 1.0
    assert sink is False


def test_hover_sube_fill_y_glifo():
    f0, g0, _ = tm.close_style()
    f1, g1, _ = tm.close_style(hover=True)
    assert f1 > f0 and g1 > g0
    assert f1 == tm._VIB_BTN_HOVER


def test_pressed_hunde_y_baja_el_fill():
    fh, _, sh = tm.close_style(hover=True)
    fp, _, sp = tm.close_style(pressed=True)
    assert sp is True
    assert fp < fh
    assert fp == tm._VIB_BTN_PRESSED


def test_no_queda_el_tinte_rojo_del_rail():
    """El color (0.86, 0.15, 0.15) del hover viejo NO SHALL aparecer."""
    w = _widget("Hola")
    w._hover_close = True
    snap = Gtk.Snapshot.new()
    w.do_snapshot(snap)
    data = snap.to_node().serialize().get_data().decode("latin1", "replace")
    # GSK serializa la X vieja como rgba(243,139,168,0.95).
    assert "243,139,168" not in data, "sigue dibujándose la X rosa"
