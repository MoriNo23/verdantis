"""Deduplication tests for NotificationManager.notify().

Apps that spam the same content without replaces_id (web tabs, PWAs, scripts)
must NOT produce N stacked identical toasts. notify() keeps a per-content
dedup key (app + summary + body, normalized) and, within DEDUP_WINDOW, closes
the previous emission before the new one is shown. This test injects a fake
scheduler + fake popup (no GLib/display) and drives the queue by hand.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import verdantis_daemon as vd


def _make_manager():
    scheduled = []  # lista de (ms, callback) entregada al scheduler

    def fake_scheduler(ms, cb):
        scheduled.append((ms, cb))
        return len(scheduled)

    mgr = vd.NotificationManager(corner="top-right", scheduler=fake_scheduler)

    # _show_popup real construye un WaylandPopup y lo mete en _active; aca
    # replicamos eso sin levantar UI (no hay display en el test).
    def fake_show(nid, kwargs):
        popup = vd.WaylandPopup(**kwargs)
        mgr._active.append((nid, popup))

    mgr._show_popup = fake_show
    return mgr, scheduled


def _drain(mgr, scheduled):
    """Ejecuta pumps hasta vaciar _pending y llenar _active al maximo."""
    for _ in range(50):
        if not mgr._pending:
            break
        ms, cb = scheduled[-1]
        assert ms == vd.NotificationManager.STAGGER_MS
        cb()
    return len(mgr._active)


# --- Tests de la clave de dedup (unidad) -------------------------------------

def test_dedup_key_normalizes_case_and_whitespace():
    a = vd._dedup_key("WhatsApp Web", "Nuevo mensaje", "Hola")
    b = vd._dedup_key("whatsapp   web", "  NUEVO   mensaje ", "\thola\t")
    assert a == b  # misma app/contenido, forma distinta => misma clave


def test_dedup_key_distinguishes_sender_independent_content():
    # El sender NO entra en la clave: dos emisores con el mismo contenido
    # deben colapsar (es la misma pestaña compartiendo el bus).
    a = vd._dedup_key("app", "x", "y", sender=":1.1")
    b = vd._dedup_key("app", "x", "y", sender=":1.2")
    assert a == b


def test_dedup_key_differs_on_different_content():
    a = vd._dedup_key("app", "mismo", "cuerpo")
    b = vd._dedup_key("app", "otro", "cuerpo")
    assert a != b


# --- Tests de comportamiento en notify() -------------------------------------

def test_duplicate_in_window_is_suppressed_before_show():
    mgr, scheduled = _make_manager()
    n1 = mgr.notify(summary="dup", app_name="app")
    n2 = mgr.notify(summary="dup", app_name="app")  # mismo contenido, ms despues
    # Ambas cayeron en _pending (pump no corre solo). El dup #1 fue cerrado
    # por dedup => solo queda el #2 en la cola.
    assert len(mgr._pending) == 1
    pending_ids = [qid for qid, _, _ in mgr._pending]
    assert pending_ids == [n2]
    assert n1 != n2
    # Al drenar, aparece UNA sola toast (no dos identicas).
    _drain(mgr, scheduled)
    assert len(mgr._active) == 1


def test_duplicate_active_is_replaced_not_stacked():
    mgr, scheduled = _make_manager()
    n1 = mgr.notify(summary="dup", app_name="app")
    _drain(mgr, scheduled)  # n1 ya visible (activa)
    assert len(mgr._active) == 1
    n2 = mgr.notify(summary="dup", app_name="app")  # dup mientras n1 sigue activa
    # dedup cierra n1 de _active y encola n2; al drenar solo queda n2.
    _drain(mgr, scheduled)
    shown = [nid for nid, _ in mgr._active]
    assert shown == [n2]
    assert len(mgr._active) == 1


def test_distinct_content_both_shown():
    mgr, scheduled = _make_manager()
    mgr.notify(summary="uno", app_name="app")
    mgr.notify(summary="dos", app_name="app")
    _drain(mgr, scheduled)
    assert len(mgr._active) == 2


def test_same_content_after_window_allowed():
    # Fuerza la ventana a -1s: cualquier separacion temporal falla el chequeo,
    # por lo que dos emisiones iguales separadas son eventos legitimos.
    mgr, scheduled = _make_manager()
    mgr.DEDUP_WINDOW = -1.0
    mgr.notify(summary="repeat", app_name="app")
    mgr.notify(summary="repeat", app_name="app")
    assert len(mgr._pending) == 2  # ninguna se suprimio
    _drain(mgr, scheduled)
    assert len(mgr._active) == 2


def test_duplicate_suppressed_within_window_then_allowed_after():
    mgr, scheduled = _make_manager()
    n1 = mgr.notify(summary="evt", app_name="app")
    n2 = mgr.notify(summary="evt", app_name="app")
    assert len(mgr._pending) == 1  # n2 reemplaza a n1
    # Ahora agrandamos la ventana a negativo de modo que un 3er evento igual,
    # conceptualmente "separado", vuelva a ser valido (legitimo segundo aviso).
    mgr.DEDUP_WINDOW = -1.0
    n3 = mgr.notify(summary="evt", app_name="app")
    assert len(mgr._pending) == 2  # n2 y n3 en cola (n1 ya fuera)
    assert n3 not in (n1, n2)
