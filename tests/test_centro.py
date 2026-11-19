"""Tests del centro de notificaciones (tarjetas del historial) y del modelo
del menú de la bandeja.

La data viene de `history_store.read()`: 1000 registros con app_name, summary,
body, timestamp, url. El centro es la vista que reemplaza al applet de la
bandeja de Plasma (que solo lista el modelo de SU daemon).
"""
import time

import notification_center as nc


def _rec(**kw):
    base = {
        "app_name": "Brave", "summary": "Código de verificación",
        "body": "Tu código de verificación es 482193. No lo compartas.",
        "timestamp": 1_700_000_000, "url": "", "actions": [],
    }
    base.update(kw)
    return base


# ── RED 1: campos de la tarjeta ──────────────────────────────────────────

def test_card_fields_basico():
    campos = nc.card_fields(_rec(), now=1_700_000_000 + 300)
    assert campos["app"] == "Brave"
    assert campos["title"] == "Código de verificación"
    assert campos["body"].startswith("Tu código de verificación")
    assert campos["when"] == "hace 5 min"


def test_card_fields_sin_summary_usa_la_app():
    campos = nc.card_fields(_rec(summary="", app_name="Telegram"),
                            now=1_700_000_000)
    assert campos["title"] == "Telegram"


def test_card_fields_body_sin_urls():
    campos = nc.card_fields(
        _rec(body="Ver en https://xat.com/sala y listo"), now=1_700_000_000)
    assert "https://" not in campos["body"]


def test_card_fields_body_acotado():
    campos = nc.card_fields(_rec(body="x" * 500), now=1_700_000_000)
    assert len(campos["body"]) <= 200


def test_card_fields_hora_relativa():
    ahora = 1_700_000_000
    assert nc.card_fields(_rec(), now=ahora + 30)["when"] == "ahora"
    assert nc.card_fields(_rec(), now=ahora + 7200)["when"] == "hace 2 h"
    assert nc.card_fields(_rec(), now=ahora + 86400 * 2)["when"] == "hace 2 días"
    assert nc.card_fields(_rec(), now=ahora + 86400 * 8)["when"].count("/") == 2


def test_card_fields_timestamp_como_string():
    """Los registros viejos del JSONL pueden traer el timestamp como string."""
    campos = nc.card_fields(_rec(timestamp="1700000000"),
                            now=1_700_000_000 + 60)
    assert campos["when"] == "hace 1 min"


# ── RED 2: el menú de la bandeja ─────────────────────────────────────────

def test_menu_items_tiene_abrir_y_limpiar():
    items = nc.menu_items()
    ids = [i["id"] for i in items]
    labels = [i["label"] for i in items]
    assert ids == list(range(1, len(items) + 1))
    assert "Abrir historial" in labels
    assert "Limpiar historial" in labels


def test_menu_items_ids_estables():
    """Los ids no pueden cambiar entre llamadas: el host cachea el layout."""
    assert nc.menu_items() == nc.menu_items()


def test_menu_de_limpiar_pide_confirmacion_en_el_label():
    limpiar = [i for i in nc.menu_items() if i["action"] == "clear"][0]
    assert "Limpiar" in limpiar["label"]


# ── RED 3: la ventana se arma con la data del historial ──────────────────

def test_ventana_lista_los_registros(monkeypatch):
    """La vista consume `history_store.read()` (no el modelo de Plasma)."""
    import notification_center as nc2
    monkeypatch.setattr(nc2, "_records_recientes",
                        lambda limit: [_rec(summary="Uno"), _rec(summary="Dos")])
    win = nc2.CenterWindow()
    assert win._conteo.get_text() == "2 notificaciones"
    fila = win._lista.get_row_at_index(0)
    assert fila is not None and fila.record["summary"] == "Uno"


def test_ventana_sin_registros_lo_dice(monkeypatch):
    import notification_center as nc2
    monkeypatch.setattr(nc2, "_records_recientes", lambda limit: [])
    assert nc2.CenterWindow()._conteo.get_text() == "sin notificaciones"


def test_ventana_no_expone_replay(monkeypatch):
    """El centro es de solo lectura: no reproduce toasts al click."""
    import notification_center as nc2
    monkeypatch.setattr(nc2, "_records_recientes", lambda limit: [_rec()])
    import inspect
    assert "on_replay" not in inspect.signature(nc2.CenterWindow).parameters
    assert not hasattr(nc2.CenterWindow(), "_on_replay")
