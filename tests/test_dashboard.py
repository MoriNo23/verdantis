"""
Tests del DASHBOARD (`src/dashboard.py`) — historial + replay.

El módulo estaba al 0% de cobertura (tabla de crapper) y tiene lógica real,
no solo rutas que devuelven HTML:

- `_history_records` tiene un fallback con criterio: disco (persistido, con
  `avatar_file`/`banner_file` guardados) y, si no hay archivo, la memoria del
  manager (daemon recién arrancado).
- `/api/replay/<id>` reproduce "tal cual": reinyecta el avatar persistido como
  `image-path` SOLO si el archivo sigue en disco, y reformatea los hints que
  se serializaron a strings.
- `/api/stats` agrupa por app con el nombre vacío plegado a "(unknown)".

Se prueba con el TEST CLIENT de Flask: sin puerto, sin thread, sin arrancar
el servidor real (`start_dashboard` queda fuera: spawnea un thread con app.run
y eso en la suite es un servidor zombi esperando a molestar).

Caracterización de comportamiento existente: pasan desde el primer run; su
valor es la red de regresión sobre el replay (que es lo único que ESCRIBE en
el sistema al re-emitir una notificación).
"""

import json
import os

import pytest

import dashboard
import history_store
from app_info import APP_NAME


class _ManagerFake:
    """El NotificationManager de mentira: registra los notify()."""

    def __init__(self, history=None):
        self.history = history or []
        self._active = {}
        self._pending = []
        self.notificados = []

    def notify(self, **kwargs):
        self.notificados.append(kwargs)
        return len(self.notificados)


class _DaemonFake:
    """El daemon de mentira: solo lo que el dashboard toca."""

    def __init__(self, manager):
        self._manager = manager


@pytest.fixture(autouse=True)
def _daemon_limpio(monkeypatch, tmp_path):
    """Aísla el global `_daemon` y el directorio de datos de cada test.

    `set_data_dir(tmp_path)` es la vía oficial del history_store para que los
    tests nunca toquen `~/.local` — sin esto, el replay leería el historial
    REAL de la máquina del que corre la suite."""
    monkeypatch.setattr(dashboard, "_daemon", None)
    monkeypatch.setattr(history_store, "_DATA_DIR", str(tmp_path))
    yield


@pytest.fixture
def cliente():
    return dashboard.app.test_client()


def _registro(nid=1, app_name="Brave", body="hola", avatar_file=None):
    return {
        "id": nid, "app_name": app_name, "app_icon": "", "summary": "Título",
        "body": body, "actions": [], "hints": {"urgency": "2"},
        "expire_timeout": 5000, "avatar_file": avatar_file,
    }


def test_index_sirve_html_con_el_nombre_de_la_app(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert r.content_type.startswith("text/html")
    html = r.get_data(as_text=True)
    assert APP_NAME in html, "el dashboard lleva el nombre de la app"


def test_api_history_nuevos_primero_desde_disco(cliente):
    """El disco se lee más viejo primero y la API los devuelve newest-first."""
    history_store.append(_registro(1, body="primero"))
    history_store.append(_registro(2, body="segundo"))
    r = cliente.get("/api/history")
    assert r.status_code == 200
    cuerpos = [h["body"] for h in r.get_json()]
    assert cuerpos == ["segundo", "primero"], (
        "la API devuelve newest-first (reversed del orden de llegada)"
    )


def test_api_history_cae_a_memoria_si_no_hay_disco(cliente):
    """Daemon recién arrancado: sin archivo, la lista sale del manager."""
    mgr = _ManagerFake(history=[_registro(7, body="en-memoria")])
    dashboard._daemon = _DaemonFake(mgr)
    r = cliente.get("/api/history")
    assert r.get_json() == [_registro(7, body="en-memoria")]


def test_api_history_vacia_sin_daemon_ni_disco(cliente):
    assert cliente.get("/api/history").get_json() == []


def test_replay_sin_daemon_es_500(cliente):
    r = cliente.post("/api/replay/1")
    assert r.status_code == 500
    assert "error" in r.get_json()


def test_replay_de_id_inexistente_es_404(cliente):
    history_store.append(_registro(1))
    dashboard._daemon = _DaemonFake(_ManagerFake())
    r = cliente.post("/api/replay/999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "id not found"


def test_replay_emite_el_registro_tal_cual(cliente):
    """Replay re-emite los campos guardados con sender propio y replace=0."""
    history_store.append(_registro(5, app_name="Brave", body="el cuerpo"))
    mgr = _ManagerFake()
    dashboard._daemon = _DaemonFake(mgr)
    r = cliente.post("/api/replay/5")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "replayed": 5}
    assert len(mgr.notificados) == 1
    n = mgr.notificados[0]
    assert n["app_name"] == "Brave"
    assert n["summary"] == "Título"
    assert n["body"] == "el cuerpo"
    assert n["sender"] == "dashboard-replay", "el replay firma su origen"
    assert n["replaces_id"] == 0, "el replay no reemplaza: es una nueva"
    assert n["expire_timeout"] == 5000


def test_replay_reinyecta_el_avatar_persistido(cliente, tmp_path):
    """El avatar se guardó como PNG en el directorio propio (los favicons de
    /tmp son efímeros): el replay lo reinyecta como image-path SOLO si el
    archivo sigue ahí."""
    from gi.repository import GdkPixbuf
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 8, 8)
    pix.fill(0x2A2A3AFF)
    src = os.path.join(str(tmp_path), "orig.png")
    pix.savev(src, "png", [], [])
    fname = history_store.copy_icon(5, src, "avatar")
    assert fname, "copy_icon tiene que devolver el nombre guardado"
    history_store.append(_registro(5, body="con avatar", avatar_file=fname))

    mgr = _ManagerFake()
    dashboard._daemon = _DaemonFake(mgr)
    r = cliente.post("/api/replay/5")
    assert r.status_code == 200
    hint_path = mgr.notificados[0]["hints"].get("image-path")
    assert hint_path and os.path.exists(hint_path), (
        "el avatar persistido se reinyecta como image-path y el archivo existe"
    )
    assert hint_path == history_store.icon_path(fname)


def test_replay_sin_avatar_no_inventa_image_path(cliente):
    """Sin imagen del sender, la reproducción vuelve a resolver el fallback
    (desktop/tema) igual que la original: NO se inyecta un image-path falso."""
    history_store.append(_registro(5, body="sin avatar", avatar_file=None))
    mgr = _ManagerFake()
    dashboard._daemon = _DaemonFake(mgr)
    r = cliente.post("/api/replay/5")
    assert r.status_code == 200
    assert "image-path" not in mgr.notificados[0]["hints"], (
        "sin avatar persistido no se inyecta image-path: el fallback resuelve"
    )


def test_stats_agrupa_por_app(cliente):
    history_store.append(_registro(1, app_name="Brave"))
    history_store.append(_registro(2, app_name="Brave"))
    history_store.append(_registro(3, app_name=""))
    mgr = _ManagerFake()
    mgr._active = {"a": 1, "b": 2}       # 2 activas
    mgr._pending = ["x"] * 3             # 3 en cola
    dashboard._daemon = _DaemonFake(mgr)
    r = cliente.get("/api/stats")
    assert r.status_code == 200
    s = r.get_json()
    assert s["total"] == 3
    assert s["active"] == 2
    assert s["queued"] == 3
    assert s["by_app"] == {"Brave": 2, "(unknown)": 1}, (
        "el app_name vacío se agrupa como (unknown)"
    )


def test_stats_sin_daemon_avisa(cliente):
    r = cliente.get("/api/stats")
    assert r.status_code == 200
    assert r.get_json()["error"] == "daemon not wired"


def test_deserialise_hints_reformatea_los_scalares():
    """Los hints se guardaron como str (image-data es RGB crudo): el replay solo
    necesita los escalares, con urgency a int y "True"/"False" a bool."""
    h = dashboard._deserialise_hints({
        "urgency": "2",
        "resident": "True",
        "silent": "False",
        "desktop-entry": "brave-browser",
        "image-data": {"w": 1},      # dict: RGB crudo, no es hint escalar
        "otro": None,                # None tampoco
    })
    assert h == {
        "urgency": 2,                      # str numérico → int
        "resident": True,                  # "True" → bool
        "silent": False,                   # "False" → bool
        "desktop-entry": "brave-browser",  # str común pasa igual
    }


def test_deserialise_hints_descarta_urgency_invalida():
    """`urgency` que no parsea a int se descarta: no viaja corrompida."""
    h = dashboard._deserialise_hints({"urgency": "alta"})
    assert h == {}, "urgency no-numérica se descarta, no se pasa como string"