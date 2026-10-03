"""Batching / queueing for notification bursts.

Cuando el sender dispara muchas notificaciones en un burst corto, NO deben
aparecer todas de golpe: el manager las encola y las muestra una por vez cada
STAGGER_MS. Estos tests inyectan un scheduler falso (sin GLib ni display Wayland)
y manejan el drenado de la cola a mano.

ORDEN DE LA COLA: FIFO por LLEGADA, sin importar la `urgency` (spec
`toast-orden-llegada`, requirement "La pila se ordena por llegada"). Antes la
cola se reordenaba por tipo (`_sort_pending`), así que un `critical` tardío
adelantaba a los que ya esperaban y un `low` se iba al final: la pila "separaba
por tipos" en vez de apilar lo que llegaba. La `urgency` sigue decidiendo la
duración y la opacidad de cada toast, pero NUNCA su posición.
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


def _shown(mgr):
    return [nid for nid, _ in mgr._active]


def _popups(mgr):
    return [popup for _, popup in mgr._active]


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
    shown = _shown(mgr)
    # Los nids se asignan en orden creciente => FIFO respeta el orden de llegada.
    assert shown == sorted(shown)


# ── La cola NO se reordena por tipo (spec toast-orden-llegada) ─────────────

def test_burst_de_tipos_mezclados_sale_en_orden_de_llegada():
    """Scenario "Burst de tipos mezclados sale en orden de llegada".

    Rojo hoy: la pila sale en orden de `urgency` (B critical, A normal,
    D normal, C low), no de llegada."""
    mgr, scheduled = _make_manager()
    llegadas = []
    for summary, urg in (("A normal", 1), ("B critical", 2),
                         ("C low", 0), ("D normal", 1)):
        llegadas.append(mgr.notify(summary=summary, app_name="app",
                                   hints={"urgency": urg}))
    while mgr._pending:
        _run_one_pump(scheduled)

    assert _shown(mgr) == llegadas, (
        "spec toast-orden-llegada / 'La pila se ordena por llegada': un burst "
        "de tipos mezclados tiene que mostrarse en el orden en que llegó "
        "(%s); la pila salió en %s — el orden lo está decidiendo la `urgency` "
        "y no la llegada" % (llegadas, _shown(mgr))
    )


def test_un_critical_tardio_no_adelanta_a_la_cola():
    """Scenario "Un critical tardío no adelanta a la cola".

    Rojo hoy: el critical muestra primero aunque haya llegado último."""
    mgr, scheduled = _make_manager()
    primero = mgr.notify(summary="a", app_name="app", hints={"urgency": 1})
    segundo = mgr.notify(summary="b", app_name="app", hints={"urgency": 1})
    critico = mgr.notify(summary="c", app_name="app", hints={"urgency": 2})

    _run_one_pump(scheduled)
    assert _shown(mgr) == [primero], (
        "spec toast-orden-llegada / 'Un critical tardío no adelanta a la cola': "
        "el primero en llegar se muestra primero; se mostró %s (el critical es "
        "%s)" % (_shown(mgr), critico)
    )
    while mgr._pending:
        _run_one_pump(scheduled)
    assert _shown(mgr) == [primero, segundo, critico]


def test_un_low_no_se_rezaqa_al_final():
    """Scenario "Un low no se rezaqa al final": llega en medio y se queda ahí.

    Rojo hoy: el `low` baja al fondo de la cola aunque haya llegado segundo."""
    mgr, scheduled = _make_manager()
    critico = mgr.notify(summary="a", app_name="app", hints={"urgency": 2})
    bajo = mgr.notify(summary="b", app_name="app", hints={"urgency": 0})
    normal = mgr.notify(summary="c", app_name="app", hints={"urgency": 1})

    while mgr._pending:
        _run_one_pump(scheduled)

    assert _shown(mgr) == [critico, bajo, normal], (
        "spec toast-orden-llegada / 'Un low no se rezaqa al final': el `low` "
        "llegó segundo y tiene que quedar segundo; la pila quedó %s (se "
        "ordenó por `urgency`)" % (_shown(mgr),)
    )


def test_cerrar_una_activa_drena_por_llegada():
    """Scenario "Cerrar una activa no reordena el resto": al liberarse un hueco
    entra la siguiente **por orden de llegada**, aunque sea de otro tipo.

    Rojo hoy: el drenado de `_close_id` vuelve a llamar `_sort_pending`."""
    mgr, scheduled = _make_manager()
    llegadas = []
    tipos = [1, 0, 2, 0, 1, 2, 1]
    for i, urg in enumerate(tipos):
        llegadas.append(mgr.notify(summary="n{}".format(i), app_name="app",
                                   hints={"urgency": urg}))
    for _ in range(vd.NotificationManager.MAX_VISIBLE):
        _run_one_pump(scheduled)
    assert len(mgr._active) == vd.NotificationManager.MAX_VISIBLE
    assert len(mgr._pending) == len(tipos) - vd.NotificationManager.MAX_VISIBLE

    mgr._close_id(mgr._active[0][0])

    assert len(mgr._active) == vd.NotificationManager.MAX_VISIBLE, (
        "cerrar una activa tiene que dejar entrar la siguiente de la cola"
    )
    assert _shown(mgr)[-1] == llegadas[vd.NotificationManager.MAX_VISIBLE], (
        "spec toast-orden-llegada / 'Cerrar una activa no reordena el resto': "
        "entra la siguiente por orden de llegada (%s), no la de mayor `urgency`; "
        "la pila quedó %s" % (llegadas[vd.NotificationManager.MAX_VISIBLE],
                             _shown(mgr))
    )


def test_la_urgencia_sigue_definiendo_la_vida_del_toast():
    """Requirement "La urgencia no reordena, solo define la vida del toast":
    el FIFO no le saca a la `urgency` su significado propio — duración y
    opacidad por toast, sólo no la posición.

    Se asserta POR TOAST (buscando cada `urgency`), no por posición: así el test
    es verde hoy y después del fix, y sigue detectando que la `urgency` no
    quedó sin efecto. Es la contraparte que impide que "se apilen por llegada"
    termine en "la urgencia no significa nada"."""
    mgr, scheduled = _make_manager()
    for summary, urg in (("low", 0), ("normal", 1), ("crit", 2)):
        mgr.notify(summary=summary, app_name="app", hints={"urgency": urg},
                   expire_timeout=6000)
    while mgr._pending:
        _run_one_pump(scheduled)

    popups = _popups(mgr)
    assert len(popups) == 3
    por_urgencia = {p.urgency: p for p in popups}
    assert por_urgencia[0]._bg_alpha == 0.55, (
        "el `low` debe seguir siendo el más tenue del card: alpha %s"
        % (por_urgencia[0]._bg_alpha,)
    )
    assert por_urgencia[1]._bg_alpha == 0.85, (
        "el `normal` debe conservar su opacidad base: alpha %s"
        % (por_urgencia[1]._bg_alpha,)
    )
    assert por_urgencia[2]._bg_alpha == 1.0, (
        "el `critical` debe seguir siendo opaco: alpha %s"
        % (por_urgencia[2]._bg_alpha,)
    )
    assert (por_urgencia[0].duration < por_urgencia[1].duration
            < por_urgencia[2].duration), (
        "la `urgency` debe seguir mandando en la duración (low 0.7x, normal 1x, "
        "critical 1.5x, más el holdback por posición): %s"
        % ([p.duration for p in popups],)
    )