"""
RED: historial de notificaciones persistido.

Objetivo (pedido): cada Notify se archiva en un JSONL ligero bajo el XDG
data home (~/.local/share/verdantis/) con los bytes del icono/imagen cuando
el sender los manda — para reproducir "cómo se veía X app tal cual" y
diagnosticar (`avatar_source` dice de dónde salió el slot izquierdo).

EXCEPCIÓN DE TERMINOLOGÍA: `avatar_source` / `avatar_file` son CLAVES DE
PERSISTENCIA (las escribe verdantis_daemon, las lee el dashboard y nombran el
archivo `n<id>_avatar.png` en disco), no vocabulario del layout: el rename de
"imagen izquierda" del change layout-imagen-izquierda no las cubre, así que
este archivo las conserva a propósito.

El directorio se inyecta con set_data_dir (tests nunca tocan ~/.local).
"""
import os

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

import history_store


def _png(tmp_path, name, pixel=0xFF1E1EFF, w=32, h=32):
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, w, h)
    pb.fill(pixel)
    path = os.path.join(str(tmp_path), name)
    pb.savev(path, "png", [], [])
    return path


def test_set_data_dir(tmp_path):
    history_store.set_data_dir(str(tmp_path))
    assert history_store._base_dir() == str(tmp_path)


def test_append_read_roundtrip(tmp_path):
    history_store.set_data_dir(str(tmp_path))
    history_store.append({"nid": 1, "app_name": "Brave", "ts": 1.0})
    recs = history_store.read()
    assert len(recs) == 1
    assert recs[0]["app_name"] == "Brave"
    # append es acumulativo (JSONL)
    history_store.append({"nid": 2, "app_name": "YouTube", "ts": 2.0})
    assert len(history_store.read()) == 2


def test_rotation_keeps_last_n(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "MAX_ENTRIES", 20)
    history_store.set_data_dir(str(tmp_path))
    for i in range(25):
        history_store.append({"nid": i})
    recs = history_store.read()
    assert [r["nid"] for r in recs] == list(range(5, 25))


def test_save_image_data_as_png(tmp_path):
    """El tuple image-data (raw RGBA del sender) se re-encoda a PNG y se
    puede leer de vuelta (replay fiel sin depender de /tmp)."""
    history_store.set_data_dir(str(tmp_path))
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 8, 8)
    pb.fill(0xFFFFFFFF)
    raw = (pb.get_width(), pb.get_height(), pb.get_rowstride(),
           pb.get_has_alpha(), pb.get_bits_per_sample(), pb.get_n_channels(),
           bytes(pb.get_pixels()))
    fname = history_store.save_image_data(7, raw)
    assert fname and fname.endswith(".png")
    saved = history_store.icon_path(fname)
    assert os.path.exists(saved)
    pb2 = GdkPixbuf.Pixbuf.new_from_file(saved)
    assert (pb2.get_width(), pb2.get_height()) == (8, 8)


def test_copy_icon_with_size_cap(tmp_path):
    """Un icono enorme NO se copia (tope MAX_ICON_BYTES, tmpfs efímero)."""
    history_store.set_data_dir(str(tmp_path))
    big = os.path.join(str(tmp_path), "big.png")
    with open(big, "wb") as f:
        f.write(b"\x00" * (history_store.MAX_ICON_BYTES + 1))
    assert history_store.copy_icon(1, big, "image_left") is None
    small = _png(tmp_path, "small.png")
    fname = history_store.copy_icon(1, small, "image_left")
    assert fname and os.path.exists(history_store.icon_path(fname))


def test_daemon_notify_persists_to_store(tmp_path):
    """Hooks del daemon: notify() archiva la noti + bytes del icono y
    avatar_source documenta la proveniencia del slot izquierdo."""
    import verdantis_daemon as vd
    history_store.set_data_dir(str(tmp_path))
    mgr = vd.NotificationManager(scheduler=lambda ms, cb: 0)  # sin timers GLib
    mgr._show_popup = lambda nid, kwargs: None
    thumb = _png(tmp_path, "thumb.png")
    nid = mgr.notify(app_name="YouTube", summary="En vivo ahora",
                     body="directo de prueba", hints={"image-path": thumb,
                                                      "urgency": 1})
    recs = history_store.read()
    assert len(recs) == 1
    r = recs[0]
    assert r["id"] == nid
    assert r["app_name"] == "YouTube"
    assert r["summary"] == "En vivo ahora"
    assert r["avatar_source"] == "image-path"
    assert r["avatar_file"], "debe guardar los bytes del icono del sender"
    assert os.path.exists(history_store.icon_path(r["avatar_file"]))


def test_daemon_notify_without_icon_source(tmp_path):
    """Sin imagen del sender y sin app conocida: avatar_source 'none' — el
    diagnóstico del archivo explica por qué no hubo slot izquierdo."""
    import verdantis_daemon as vd
    history_store.set_data_dir(str(tmp_path))
    mgr = vd.NotificationManager(scheduler=lambda ms, cb: 0)
    mgr._show_popup = lambda nid, kwargs: None
    mgr.notify(app_name="zzz_no_existe_xa", summary="hola", body="mundo",
               hints={})
    r = history_store.read()[0]
    assert r["avatar_source"] == "none"
    assert r["avatar_file"] is None


def test_daemon_notify_transient_not_archived(tmp_path):
    """transient (spec freedesktop): no se archiva (como dunst/mako)."""
    import verdantis_daemon as vd
    history_store.set_data_dir(str(tmp_path))
    mgr = vd.NotificationManager(scheduler=lambda ms, cb: 0)
    mgr._show_popup = lambda nid, kwargs: None
    mgr.notify(app_name="Algo", summary="s", body="b", hints={"transient": True})
    assert history_store.read() == []