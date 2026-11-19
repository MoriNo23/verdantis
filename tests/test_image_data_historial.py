"""`image-data` sin path de archivo también se archiva para el replay.

Antes el popup lo mostraba en vivo pero el historial guardaba `avatar_file=None`:
el replay caía al icono de la app. Ahora los bytes se convierten a PNG y se
guardan en el directorio de iconos, con el mismo esquema que `copy_icon`.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import history_store
from test_replay_cli import _manager, datos  # noqa: F401 (fixture)

# RGBA 2x2, rowstride 8
_IMG = (2, 2, 8, True, 8, 4, bytes([0x80, 0xCB, 0xC4, 0xFF] * 4))


def test_write_icon_guarda_los_bytes(datos):
    fname = history_store.write_icon(7, b"\x89PNG\r\nfalso", "avatar")
    assert fname == "n7_avatar.png"
    assert Path(history_store.icon_path(fname)).read_bytes() == b"\x89PNG\r\nfalso"


def test_notify_archiva_image_data_sin_path(datos):
    m = _manager()
    m.notify(app_name="sim", summary="s", body="b",
             hints={"image-data": _IMG}, expire_timeout=6000)
    rec = history_store.read()[0]
    assert rec["avatar_file"], "el replay perdería la imagen del image-data"
    datos_guardados = Path(history_store.icon_path(rec["avatar_file"])).read_bytes()
    assert datos_guardados.startswith(b"\x89PNG")
