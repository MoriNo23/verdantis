"""Tests del replay por CLI (historial en disco + comandos list/replay/clear).

Cubre las tres capas con lógica propia:
- `history_store`: JSONL append/read, rotación con limpieza de iconos, `clear`.
- `replay`: selección (`--last`/`--app`/`--id`) y mapeo registro→kwargs del
  toast (icono archivado, urgencia de los hints, navegador plegado).
- wiring de los subcomandos por subprocess (headless: `list` y `clear` no
  tocan display).

El render del replay no se testea acá: lo verifica el usuario (spec
`verificacion-visual`).
"""
import argparse
import os
import subprocess
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import history_store
import replay

_RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _rec(**kw):
    """Registro con el esquema del JSONL en disco (ids int, como los reales)."""
    base = {
        "id": 1, "timestamp": 100.0, "app_name": "sim", "app_icon": "",
        "summary": "s", "body": "b", "actions": [], "hints": {},
        "expire_timeout": -1, "sender": "", "url": "", "duration": 6000,
        "avatar_file": None, "banner_file": None,
    }
    base.update(kw)
    return base


def json_lines(*recs):
    """Contenido de un history.jsonl con esos registros."""
    import json
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)


@pytest.fixture
def datos(tmp_path, monkeypatch):
    """Aísla el store en tmp_path: los tests nunca tocan ~/.local."""
    monkeypatch.setattr(history_store, "_DATA_DIR", str(tmp_path))
    return tmp_path


# --- Store: JSONL ---

def test_append_y_read_roundtrip(datos):
    history_store.append(_rec(id=7, summary="hola"))
    recs = history_store.read()
    assert [r["id"] for r in recs] == [7]
    assert recs[0]["summary"] == "hola"


def test_read_sin_archivo_devuelve_vacio(datos):
    assert history_store.read() == []


def test_read_salta_linea_corrupta(datos):
    history_store.append(_rec(id=1))
    with open(history_store._history_path(), "a", encoding="utf-8") as f:
        f.write("{no es json}\n")
    history_store.append(_rec(id=2))
    assert [r["id"] for r in history_store.read()] == [1, 2]


def test_rotate_descarta_viejos_y_sus_iconos(datos, monkeypatch):
    monkeypatch.setattr(history_store, "MAX_ENTRIES", 3)
    src = datos / "origen.png"
    src.write_bytes(b"png")
    for i in range(4):
        fname = history_store.copy_icon(i, str(src), "avatar")
        history_store.append(_rec(id=i, avatar_file=fname))
    assert [r["id"] for r in history_store.read()] == [1, 2, 3], (
        "el tope mantiene los ÚLTIMOS registros (más viejo primero)"
    )
    assert not os.path.exists(history_store.icon_path("n0_avatar.png")), (
        "el icono del registro descartado queda huérfano en disco"
    )
    assert os.path.exists(history_store.icon_path("n3_avatar.png"))


# --- Store: iconos ---

def test_copy_icon_copia_bytes(datos):
    src = datos / "tab.png"
    src.write_bytes(b"contenido")
    fname = history_store.copy_icon(5, str(src), "avatar")
    assert fname == "n5_avatar.png"
    with open(history_store.icon_path(fname), "rb") as f:
        assert f.read() == b"contenido"


def test_copy_icon_ignora_archivo_grande_y_ausente(datos, monkeypatch):
    monkeypatch.setattr(history_store, "MAX_ICON_BYTES", 4)
    grande = datos / "grande.png"
    grande.write_bytes(b"12345")
    assert history_store.copy_icon(1, str(grande), "avatar") is None
    assert history_store.copy_icon(2, str(datos / "no_existe.png"), "avatar") is None


# --- Store: clear ---

def test_clear_borra_jsonl_e_iconos(datos):
    src = datos / "tab.png"
    src.write_bytes(b"x")
    history_store.append(_rec(id=1, avatar_file=history_store.copy_icon(
        1, str(src), "avatar")))
    history_store.clear()
    assert history_store.read() == []
    assert os.listdir(history_store._icon_dir()) == []


# --- Selección de registros ---

def _recs():
    return [
        _rec(id=1, app_name="Brave", summary="uno"),
        _rec(id=2, app_name="sim", summary="dos"),
        _rec(id=3, app_name="Brave", summary="tres"),
    ]


def test_seleccionar_last_devuelve_los_ultimos_en_orden_de_llegada():
    assert [r["id"] for r in replay.seleccionar(_recs(), last=2)] == [2, 3]


def test_seleccionar_default_es_last_5():
    recs = [_rec(id=i) for i in range(1, 9)]
    assert [r["id"] for r in replay.seleccionar(recs)] == [4, 5, 6, 7, 8]


def test_seleccionar_por_app_ignora_mayusculas():
    assert [r["id"] for r in replay.seleccionar(_recs(), app="brave")] == [1, 3]


def test_seleccionar_por_id_gana_sobre_last():
    assert [r["id"] for r in replay.seleccionar(_recs(), last=1, id=1)] == [1]


def test_seleccionar_por_id_toma_el_ultimo_match():
    """Los ids se REPITEN: cada reinicio del daemon resetea `_next_id` y el
    JSONL acumula 1000 registros, así que `--id 5` son decenas de matches.
    `--id` es "el más reciente con ese id" (un toast, no una traca)."""
    recs = [_rec(id=1, summary="viejo"), _rec(id=2), _rec(id=1, summary="nuevo")]
    assert [r["summary"] for r in replay.seleccionar(recs, id=1)] == ["nuevo"]


def test_seleccionar_sin_registros_no_explota():
    assert replay.seleccionar([], last=3) == []


# --- Registro → kwargs del toast ---

def test_record_a_kwargs_usa_el_icono_archivado(datos):
    src = datos / "tab.png"
    src.write_bytes(b"x")
    fname = history_store.copy_icon(1, str(src), "avatar")
    kw = replay.record_a_kwargs(_rec(
        summary="hola", body="cuerpo", app_name="sim", app_icon="dialog-warning",
        hints={"urgency": 2}, actions=["default", "Activar"], avatar_file=fname,
        duration=6000,
    ))
    assert (kw["titulo"], kw["cuerpo"]) == ("hola", "cuerpo")
    assert kw["icon_path"] == history_store.icon_path(fname)
    assert kw["urgency"] == 2
    assert kw["duration"] == 6000
    assert kw["actions"] == ["default", "Activar"]
    assert kw["app_icon"] == "dialog-warning"
    assert kw["on_close"] is None and kw["on_click"] is None, (
        "el replay no tiene bus: click/cierre no emiten señales"
    )


def test_record_a_kwargs_sin_icono_archivado_cae_al_fallback(datos):
    kw = replay.record_a_kwargs(_rec(avatar_file=None))
    assert kw["icon_path"] is None, (
        "sin PNG archivado el popup resuelve icono de app / placeholder"
    )


def test_record_a_kwargs_icono_borrado_no_rompe(datos):
    kw = replay.record_a_kwargs(_rec(avatar_file="n99_avatar.png"))
    assert kw["icon_path"] is None


def test_record_a_kwargs_duration_override(datos):
    assert replay.record_a_kwargs(_rec(duration=6000), duration=1000)["duration"] == 1000


def test_record_a_kwargs_navegador_pliega_el_titulo(datos):
    kw = replay.record_a_kwargs(_rec(
        app_name="Brave", summary="Respuesta lista",
        hints={"desktop-entry": "brave-browser-nightly"},
    ))
    assert kw["app_label"] == "Brave - Respuesta lista"
    assert kw["hide_title"] is True


def test_record_a_kwargs_respeta_persistente(datos):
    """duration 0 = persistente (spec 1.2): el replay no puede volverlo 6000."""
    assert replay.record_a_kwargs(_rec(duration=0))["duration"] == 0


def test_record_a_kwargs_con_url_arma_click_que_abre_y_pide_cierre(datos, monkeypatch):
    """Spec `replay`: el click del toast reproducido abre la URL archivada
    con xdg-open y pide el cierre retornando True (no hay daemon que cierre)."""
    popen = Mock()
    monkeypatch.setattr(replay.subprocess, "Popen", popen)
    kw = replay.record_a_kwargs(_rec(url="https://ejemplo.com/x"))
    assert callable(kw["on_click"]), "con URL archivada debe haber click"
    assert kw["on_click"]() is True
    popen.assert_called_once_with(
        ["xdg-open", "https://ejemplo.com/x"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def test_record_a_kwargs_sin_url_no_hay_click(datos):
    """Sin URL el click no tiene efecto: no hay affordance que mienta."""
    kw = replay.record_a_kwargs(_rec(url=""))
    assert kw["on_click"] is None


def test_record_a_kwargs_url_local_se_ignora(datos):
    """La misma última línea de defensa del daemon: una URL local/de red
    privada jamás es destino de click (aunque esté archivada)."""
    kw = replay.record_a_kwargs(_rec(url="http://127.0.0.1:8766/x"))
    assert kw["on_click"] is None


def test_record_a_kwargs_botones_sin_accion_replay(datos):
    """Los botones reproducidos renderizan por fidelidad pero no ejecutan:
    no hay sender. `buttons_actionable=False` se los niega al popup."""
    kw = replay.record_a_kwargs(_rec(actions=["default", "Abrir"]))
    assert kw["buttons_actionable"] is False


def test_record_a_kwargs_solo_parametros_que_el_popup_acepta(datos):
    """Guardarraíl contra divergencia: el shape del daemon y el del popup son
    el mismo contrato; una clave de más revienta en el render."""
    import inspect
    from wayland_popup import WaylandPopup
    kw = replay.record_a_kwargs(_rec(
        hints={"urgency": 2, "desktop-entry": "brave-browser"},
        actions=["default", "Activar"]))
    assert set(kw) <= set(inspect.signature(WaylandPopup.__init__).parameters)


def test_para_x11_solo_pasa_parametros_del_fallback(datos):
    """El __init__ del fallback X11 es un subconjunto: urgency, actions y
    callbacks no existen ahí (TypeError si el filtro no corre)."""
    import inspect
    from x11_popup import NotificacionX11
    kw = replay._para_x11(replay.record_a_kwargs(_rec(
        hints={"urgency": 2}, actions=["default", "Activar"])))
    assert set(kw) <= set(inspect.signature(NotificacionX11.__init__).parameters)
    assert "actions" not in kw and "urgency" not in kw
def test_record_a_kwargs_registro_viejo_minimo(datos):
    """Los 1000 registros en disco traen el esquema completo, pero el replay no
    puede depender de claves opcionales (`duration`, `hints`, `actions`)."""
    kw = replay.record_a_kwargs(
        {"id": 1, "summary": "s", "body": "b", "app_name": "sim"})
    assert kw["titulo"] == "s"
    assert kw["duration"] == 6000


# --- Loop de replay ---

def test_cmd_replay_muestra_cada_registro_elegido(datos, monkeypatch, tmp_path):
    for r in _recs():
        history_store.append(r)
    vistos = []
    monkeypatch.setattr(replay, "mostrar_toast", lambda kw, **k: vistos.append(kw))
    replay.cmd_replay(argparse.Namespace(last=2, app=None, id=None,
                                         duration=None, force_fallback=False))
    assert [k["titulo"] for k in vistos] == ["dos", "tres"]


def test_cmd_replay_sin_historial_no_abre_ventana(datos, monkeypatch, capsys):
    monkeypatch.setattr(replay, "mostrar_toast", lambda kw, **k: pytest.fail(
        "no hay nada que reproducir y se abrió una ventana"))
    replay.cmd_replay(argparse.Namespace(last=2, app=None, id=None,
                                         duration=None, force_fallback=False))
    assert "no hay" in capsys.readouterr().err.lower()


# --- Wiring de los subcomandos (subprocess: `list` y `clear` sin display) ---

def _correr(args, tmp_path):
    env = dict(os.environ, XDG_DATA_HOME=str(tmp_path))
    return subprocess.run(
        [sys.executable, os.path.join(_RAIZ, "src", "verdantis.py")] + args,
        env=env, capture_output=True, text=True,
    )


def test_cli_list_imprime_historial(tmp_path):
    hist = tmp_path / "verdantis" / "icons"
    hist.mkdir(parents=True)
    (tmp_path / "verdantis" / "history.jsonl").write_text(
        json_lines(_rec(id=1, app_name="sim", summary="Noti 5")), encoding="utf-8")
    r = _correr(["list"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Noti 5" in r.stdout and "sim" in r.stdout


def test_cli_clear_sin_yes_no_borra(tmp_path):
    d = tmp_path / "verdantis"
    d.mkdir()
    (d / "history.jsonl").write_text(json_lines(_rec(id=1)), encoding="utf-8")
    r = _correr(["clear"], tmp_path)
    assert r.returncode != 0
    assert (d / "history.jsonl").exists(), "sin --yes no se borra nada"


def test_cli_clear_con_yes_borra(tmp_path):
    d = tmp_path / "verdantis" / "icons"
    d.mkdir(parents=True)
    (d / "n1_avatar.png").write_bytes(b"x")
    (tmp_path / "verdantis" / "history.jsonl").write_text(
        json_lines(_rec(id=1)), encoding="utf-8")
    r = _correr(["clear", "--yes"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "verdantis" / "history.jsonl").exists()
    assert os.listdir(str(d)) == []


# --- El daemon archiva lo que el replay reproduce ---

def _manager():
    """Manager con show stubbeado (sin ventanas) y bus falso: el manager real."""
    from test_auditoria_fixes import _manager_stub_show
    return _manager_stub_show()


def test_notify_archiva_en_historial(datos):
    m = _manager()
    m.notify(app_name="sim", summary="hola", body="cuerpo", hints={},
             expire_timeout=6000)
    recs = history_store.read()
    assert len(recs) == 1
    assert (recs[0]["summary"], recs[0]["app_name"]) == ("hola", "sim")
    assert recs[0]["duration"] == 6000


def test_notify_transient_no_archiva(datos):
    m = _manager()
    m.notify(app_name="sim", summary="efímera", body="", hints={"transient": True},
             expire_timeout=6000)
    assert history_store.read() == []


def test_notify_archiva_copiando_el_icono(datos, tmp_path):
    """El favicon del tab vive en /tmp (efímero): se copia para que el replay
    no dependa de un archivo que ya no existe."""
    src = tmp_path / "tab.png"
    src.write_bytes(b"png")
    m = _manager()
    m.notify(app_name="Brave", summary="s", body="b",
             hints={"image-path": str(src)}, expire_timeout=6000)
    rec = history_store.read()[0]
    assert rec["avatar_file"], "sin copia del icono el replay pierde la imagen"
    assert os.path.exists(history_store.icon_path(rec["avatar_file"]))


def test_un_fallo_de_disco_no_rompe_notify(datos, monkeypatch):
    """Best-effort: si el historial explota, la notificación sale igual."""
    def boom(_):
        raise OSError("disco lleno")

    monkeypatch.setattr(history_store, "append", boom)
    m = _manager()
    nid = m.notify(app_name="sim", summary="s", body="b", hints={},
                   expire_timeout=6000)
    assert nid > 0
