"""Stagger/offset de los timeouts de auto-cierre en bursts.

Bug: multiples notificaciones que llegan juntas (ej: reconectar red, bajar
VPN) tenian todas el MISMO duration (6000ms) y desaparecian a la vez. El
STAGGER_MS de la cola solo escalona la *aparicion* (via _pump), no el timer
de auto-cierre de cada popup (WaylandPopup.duration arranca en time.time(),
asi que el cierre caia en una ventana de ~1.2s que se leia como sincronizado).

Fix (verdantis_daemon.py:_show_popup): al mostrar el popup en la posicion idx
del stack, se suma idx * CLOSE_STAGGER_MS a su duration (la posicion 0 queda
en el default del server; los persistentes duration=0 no aplican). Asi el
cierre queda escalonado como la aparicion.

Estos tests inyectan un scheduler falso (sin GLib ni display) y drenan la
cola a mano, leyendo el duration real de cada WaylandPopup construido.
"""

import verdantis_daemon as vd


def _make_manager():
    scheduled = []  # lista de (ms, callback) entregada al scheduler

    def fake_scheduler(ms, cb):
        scheduled.append((ms, cb))
        return len(scheduled)

    mgr = vd.NotificationManager(corner="top-right", scheduler=fake_scheduler)
    # NO sobreescribimos _show_popup: dejamos correr el REAL (que aplica el
    # stagger por posicion). El real llama a popup.prepare(), que sin
    # WAYLAND_DISPLAY es no-op (retorna temprano) y no levanta display, asi
    # que es seguro headless y ademas ejercita el fix.
    return mgr, scheduled


def _drain_until_active(mgr, scheduled, n):
    """Corre pumps hasta tener n popups activos (o se vacie _pending)."""
    guard = 0
    while True:
        if len(mgr._active) >= n or (not mgr._pending and len(mgr._active) == n):
            break
        if not scheduled:
            break
        ms, cb = scheduled[-1]
        assert ms == vd.NotificationManager.STAGGER_MS
        cb()
        guard += 1
        if guard > 100:
            break
    return [p.duration for _, p in mgr._active]


def test_burst_close_timeouts_not_identical():
    """Las notificaciones de un burst que quedan VISIBLES no vencen todas
    juntas: el holdback por POSICIÓN en la pila las separa (el cierre quedaba
    en una ventana de ~1.2s que se leía como sincronizado).

    Las posiciones simultáneas son 0..MAX_VISIBLE-1 (el resto espera en la cola),
    así que el burst se notifica con una de más y se drena hasta llenar la pila:
    el test vale para cualquier capacidad."""
    mgr, scheduled = _make_manager()
    for i in range(vd.NotificationManager.MAX_VISIBLE + 1):
        # expire_timeout=-1 -> duration base 6000ms (default del server)
        mgr.notify(summary="n{}".format(i), app_name="app", expire_timeout=-1)

    durations = _drain_until_active(mgr, scheduled,
                                    vd.NotificationManager.MAX_VISIBLE)
    assert len(durations) == vd.NotificationManager.MAX_VISIBLE
    # Ninguna es igual a la anterior: el stagger por posicion las separa.
    assert durations[0] == 6000            # posicion 0: default sin holdback
    for anterior, actual in zip(durations, durations[1:]):
        assert actual > anterior, (
            "el holdback crece con la posicion: %s" % (durations,)
        )
    # Todas distintas entre si.
    assert len(set(durations)) == len(durations)


def test_close_stagger_increments_by_position():
    """El holdback crece linealmente con idx * CLOSE_STAGGER_MS, donde idx es la
    posición en la pila (0..MAX_VISIBLE-1)."""
    mgr, scheduled = _make_manager()
    for i in range(vd.NotificationManager.MAX_VISIBLE + 1):
        mgr.notify(summary="n{}".format(i), app_name="app", expire_timeout=-1)

    durations = _drain_until_active(mgr, scheduled,
                                    vd.NotificationManager.MAX_VISIBLE)
    base = 6000
    step = vd.NotificationManager.CLOSE_STAGGER_MS
    assert durations == [base + i * step
                         for i in range(vd.NotificationManager.MAX_VISIBLE)]

    # La que entra a un hueco libre entra en posición 1 (ya hay otra visible),
    # así que NO vuelve al default: conserva el holdback.
    mgr._close_id(mgr._active[0][0])
    assert mgr._active[-1][1].duration == base + step, (
        "la noti que entra a un hueco libre va a la posición 1 y mantiene el "
        "holdback; tuvo %s" % (mgr._active[-1][1].duration,)
    )


def test_close_stagger_preserves_position_zero_default():
    """Una notificacion aislada (idx 0) NO debe alterar su duration base."""
    mgr, scheduled = _make_manager()
    mgr.notify(summary="solo", app_name="app", expire_timeout=-1)
    _drain_until_active(mgr, scheduled, 1)
    # idx 0 -> sin holdback, mantiene el default del server.
    assert mgr._active[0][1].duration == 6000


def test_persistent_notification_ignores_stagger():
    """duration=0 (persistente / requireInteraction) no recibe holdback."""
    mgr, scheduled = _make_manager()
    mgr.notify(summary="sticky", app_name="Brave", expire_timeout=0)
    # Segunda noti para forzar idx>0 en la segunda... pero la primera es idx 0.
    mgr.notify(summary="sticky2", app_name="Brave", expire_timeout=0)
    durations = _drain_until_active(mgr, scheduled, 2)
    # Ambas persistentes: duration=0 sin holdback, incluso en idx>0.
    assert durations == [0, 0]


def test_explicit_positive_timeout_keeps_value_plus_stagger():
    """expire_timeout > 0 conserva su valor y suma el holdback por posicion."""
    mgr, scheduled = _make_manager()
    mgr.notify(summary="a", app_name="x", expire_timeout=3000)
    mgr.notify(summary="b", app_name="x", expire_timeout=3000)
    durations = _drain_until_active(mgr, scheduled, 2)
    step = vd.NotificationManager.CLOSE_STAGGER_MS
    assert durations == [3000, 3000 + step]
