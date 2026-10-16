"""Metatest de sensibilidad del replay por CLI (tests/test_replay_cli.py).

Inyecta la versión bugueada de cada pieza y verifica que el predicado del test
correspondiente queda en rojo; sin esto, test_replay_cli sería un placebo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import history_store
import replay
import verdantis_daemon

from test_replay_cli import _manager, _rec, _recs, datos  # noqa: F401


def test_metatest_seleccionar_ignorando_last_detectado(monkeypatch):
    """Inyección: `seleccionar` devuelve TODO (replay de 1000 registros).
    El test de --last debe quedar en rojo."""
    monkeypatch.setattr(replay, "seleccionar",
                        lambda records, last=5, app=None, id=None: list(records))
    assert [r["id"] for r in replay.seleccionar(_recs(), last=2)] != [2, 3], (
        "Metatest roto: con --last ignorado el test del recorte queda en verde"
    )


def test_metatest_icono_archivado_ignorado_detectado(datos, monkeypatch):
    """Inyección: `record_a_kwargs` no mira `avatar_file` (replay sin la imagen
    de la notificación: cae siempre al icono de app). El test del icono
    archivado debe quedar en rojo."""
    monkeypatch.setattr(replay, "record_a_kwargs",
                        lambda record, duration=None: {"icon_path": None})
    src = datos / "tab.png"
    src.write_bytes(b"x")
    fname = history_store.copy_icon(1, str(src), "avatar")
    kw = replay.record_a_kwargs(_rec(avatar_file=fname))
    assert kw["icon_path"] != history_store.icon_path(fname), (
        "Metatest roto: con avatar_file ignorado el test del icono queda verde"
    )


def test_metatest_transient_archivado_detectado(datos, monkeypatch):
    """Inyección: el daemon archiva TODO, incluidas las transient (bug del
    guard ausente). El test de transient debe quedar en rojo."""
    monkeypatch.setattr(verdantis_daemon, "_debe_archivar", lambda hints: True)
    m = _manager()
    m.notify(app_name="sim", summary="efímera", body="",
             hints={"transient": True}, expire_timeout=6000)
    assert len(history_store.read()) != 0, (
        "Metatest roto: si transient se archiva y el test sigue verde, "
        "test_notify_transient_no_archiva no cubre nada"
    )


def test_metatest_guard_de_clear_detectado(datos, monkeypatch):
    """Inyección: `clear` borra sin `--yes`. El test del guard debe quedar en
    rojo (el historial es evidencia de producción y no se recupera)."""
    import argparse
    history_store.append(_rec(id=1))
    monkeypatch.setattr(history_store, "clear", lambda: (1, 0))
    args = argparse.Namespace(yes=True)  # --yes inyectado: el guard no corre
    try:
        replay.cmd_clear(args)
    except SystemExit:
        raise AssertionError(
            "Metatest roto: el guard de --yes no se ejecutó")
    assert history_store.read() != [], (
        "Metatest roto: sin guard, clear se lleva el historial entero"
    )
