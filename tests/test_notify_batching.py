"""Batching / queueing for notification bursts.

Cuando el sender dispara muchas notificaciones en un burst corto, NO deben
aparecer todas de golpe: el manager las encola y las muestra una por vez cada
STAGGER_MS, respetando prioridad (urgency). Estos tests inyectan un scheduler
falso (sin GLib ni display Wayland) y manejan el drenado de la cola a mano.
"""

import verdantis_daemon as vd


def _make_manager():
    scheduled = []  # lista de (ms, callback) entregada al scheduler

    def fake_scheduler(ms, cb):
        scheduled.append((ms, cb))
        return len(scheduled)

    mgr = vd.NotificationManager(corner="top-right", scheduler=fake_scheduler)

    # _show_popup real construye un WaylandPopup y lo mete en _active; acá
    # replicamos eso sin levantar UI (no hay display en el test).
    def fake_show(nid, kwargs):
        popup = vd.WaylandPopup(**kwargs)
        mgr._active.append((nid, popup))

    mgr._show_popup = fake_show
    return mgr, scheduled


def _run_one_pump(scheduled):
    """Ejecuta el ultimo callback de pump agendado y devuelve cuantos hay."""
    ms, cb = scheduled[-1]
    assert ms == vd.NotificationManager.STAGGER_MS
    cb()
    return len(scheduled)


def test_burst_not_shown_all_at_once():
    mgr, scheduled = _make_manager()
    for i in range(4):
        mgr.notify(summary="n{}".format(i), app_name="app")
    # Nada se muestra hasta que el pump corre (la cola esta llena, no activas)
    assert len(mgr._active) == 0
    assert len(mgr._pending) == 4
    # Un solo pump fue agendado (STAGGER_MS), no se dispararon las 4 de una.
    assert len(scheduled) == 1
    assert scheduled[0][0] == vd.NotificationManager.STAGGER_MS

    # Cada corrida del pump muestra EXACTAMENTE una notificacion.
    _run_one_pump(scheduled)
    assert len(mgr._active) == 1
    assert len(mgr._pending) == 3
    _run_one_pump(scheduled)
    assert len(mgr._active) == 2
    # Drena el resto.
    for _ in range(5):
        if mgr._pending or len(mgr._active) < 4:
            _run_one_pump(scheduled)
    assert len(mgr._active) == 4
    assert len(mgr._pending) == 0


def test_burst_order_preserves_fifo_for_same_urgency():
    mgr, scheduled = _make_manager()
    for i in range(3):
        mgr.notify(summary="n{}".format(i), app_name="app",
                   hints={"urgency": 1})
    # FIFO: el primero en encolar es el primero en mostrarse.
    while mgr._pending or len(mgr._active) < 3:
        _run_one_pump(scheduled)
    shown = [nid for nid, _ in mgr._active]
    # Los nids se asignan en orden creciente => FIFO respeta el orden de llegada.
    assert shown == sorted(shown)


def test_critical_priority_shown_before_low():
    mgr, scheduled = _make_manager()
    # Llegan en orden: low, normal, critical; pero el critical debe salir 1o.
    low = mgr.notify(summary="low", app_name="a", hints={"urgency": 0})
    norm = mgr.notify(summary="norm", app_name="a", hints={"urgency": 1})
    crit = mgr.notify(summary="crit", app_name="a", hints={"urgency": 2})

    # Primer pump: debe mostrar el critical (mayor urgencia).
    _run_one_pump(scheduled)
    assert [nid for nid, _ in mgr._active] == [crit]
    _run_one_pump(scheduled)
    assert [nid for nid, _ in mgr._active] == [crit, norm]
    _run_one_pump(scheduled)
    assert [nid for nid, _ in mgr._active] == [crit, norm, low]


def test_closing_frees_slot_and_drains_queue():
    mgr, scheduled = _make_manager()
    # Llenamos el limite MAX_VISIBLE y agregamos un par mas en la cola.
    for i in range(vd.NotificationManager.MAX_VISIBLE + 2):
        mgr.notify(summary="n{}".format(i), app_name="a")
    # Drenamos hasta que todas las visibles esten activas.
    for _ in range(vd.NotificationManager.MAX_VISIBLE):
        _run_one_pump(scheduled)
    assert len(mgr._active) == vd.NotificationManager.MAX_VISIBLE
    assert len(mgr._pending) == 2
    # Cerramos una activa -> debe mostrar la siguiente de la cola de inmediato.
    closed_nid = mgr._active[0][0]
    mgr._close_id(closed_nid)
    assert len(mgr._active) == vd.NotificationManager.MAX_VISIBLE  # entro 1 de la cola
    assert len(mgr._pending) == 1


def test_close_all_clears_pending_and_pump():
    mgr, scheduled = _make_manager()
    for i in range(3):
        mgr.notify(summary="n{}".format(i), app_name="a")
    mgr.close_all()
    assert mgr._pending == []
    assert mgr._active == []
    assert mgr._pump_scheduled is False
