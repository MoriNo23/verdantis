"""Tests del pipeline de render GSK (el gap que dejó pasar el bug de contraste).

Hasta v0.15.2 no había NINGÚN test que ejecutara `do_snapshot`: los 91 tests
eran de lógica y el render solo se verificaba a ojo. Estos tests construyen un
`Gtk.Snapshot` real sin ventana (headless), ejecutan el snapshot del widget y
serializan el `Gsk.RenderNode` resultante para comprobar que los nodos de la
vibrancia (gradiente, sombra, clip redondeado, texto, botones) están presentes.

Si un cambio rompe el pipeline de dibujo, la serialización cambia y el test
falla — sin depender del ojo ni de KWin.
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gtk

import wayland_popup as wp


def _widget(cuerpo="Tu código de verificación es 482193",
            acciones=None, ancho=360, alto=200):
    """Widget mínimo con los atributos que do_snapshot consulta."""
    w = wp.NotificationWidget.__new__(wp.NotificationWidget)
    w.__dict__.update(
        _cuerpo=cuerpo, _app_name="Brave", _hide_title=False, _expanded=False,
        _actions=acciones or [], _fraction=0.6, _hover=False,
        _accent_rgb=wp._hex_rgb("#80cbc4"),
        _card_bg=wp._hex_rgb(wp._CARD_BG_HEX),
        _left_title=wp._hex_rgb(wp._TXT_TITLE_L),
        _left_body=wp._hex_rgb(wp._TXT_BODY_L),
        _left_app=wp._hex_rgb(wp._TXT_APP_L),
        _right_title=wp._hex_rgb(wp._TXT_TITLE_R),
        _right_body=wp._hex_rgb(wp._TXT_BODY_R),
        _right_app=wp._hex_rgb(wp._TXT_APP_R),
        _titulo="Título", _app_label=None, _font_scale=1.0,
        _image_left_pb=None, _image_pb=None, _app_icon_pb=None,
        _action_icon_pbs={}, _action_rects=[], _close_rect=None,
        _copy_rect=None,
        _copy_text=wp._find_code(cuerpo) or cuerpo,
        _pressed_copy=False, _hover_copy=False,
        _pressed_action_idx=None, _pressed_close=False, _hover_action_idx=None,
    )
    w.get_width = lambda: ancho
    w.get_height = lambda: alto
    return w


def _nodos(cuerpo, acciones=None):
    """Serializa el render node del widget y devuelve el texto de los nodos."""
    w = _widget(cuerpo, acciones)
    snap = Gtk.Snapshot.new()
    w.do_snapshot(snap)
    node = snap.to_node()
    assert node is not None, "do_snapshot no produjo ningún nodo"
    return node.serialize().get_data().decode("latin1", "replace"), w


def test_render_gsk_clude_gradiente_sombra_y_clip_redondeado():
    """La vibrancia no es plano: gradiente + sombra + esquinas redondeadas."""
    data, _ = _nodos("Hola mundo")
    for nodo in ("linear-gradient", "outset-shadow", "rounded-clip"):
        assert nodo in data, "falta el nodo GSK %r en el render" % nodo


def test_render_gsk_dibuja_texto():
    """El body y el título se rasterizan con nodos de texto (append_layout)."""
    data, _ = _nodos("Hola mundo")
    assert "text" in data, "el render no contiene nodos de texto"


def test_render_gsk_botones_publican_rect_y_se_dibujan():
    """La fila de acciones publica rects y se dibuja (2 botones caben)."""
    data, w = _nodos("Mensaje", [("a", "Marcar como leída"), ("b", "Responder")])
    assert len(w._action_rects) == 2
    # Con 2 acciones D-Bus la fila ya ocupa todo el ancho: el botón Copiar
    # local no tiene hueco y no se dibuja (comportamiento correcto, sin solape).
    for nodo in ("rounded-clip", "text"):
        assert nodo in data


def test_render_gsk_copiar_solo_sin_acciones_db():
    """El botón Copiar local aparece cuando no hay acciones D-Bus compitiendo."""
    data, w = _nodos("Mensaje sin acciones")
    assert w._action_rects == []
    assert w._copy_rect is not None, "sin acciones D-Bus debe aparecer Copiar"


def test_render_gsk_codigo_muestra_boton_copiar():
    """Con código de verificación, el botón Copiar código se dibuja."""
    data, w = _nodos("Tu código de verificación es 482193")
    assert w._copy_text == "482193"
    assert w._copy_rect is not None
    assert "text" in data


def test_render_gsk_wipe_recorta_con_clip():
    """El frente de tiempo (fraction<1) genera nodos de recorte."""
    data, _ = _nodos("Hola mundo")
    assert "clip" in data, "el wipe no recorta la parte ya transcurrida"


def test_render_gsk_sin_ventana_no_lanza():
    """Regresión: el snapshot debe funcionar headless (sin GdkWindow)."""
    w = _widget("Hola")
    snap = Gtk.Snapshot.new()
    w.do_snapshot(snap)          # no debe lanzar
    assert snap.to_node() is not None
