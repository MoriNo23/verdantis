"""Batching / queueing for notification bursts.

Cuando el sender dispara muchas notificaciones en un burst corto, NO deben
aparecer todas de golpe: el manager las encola y las muestra una por vez cada
STAGGER_MS. Estos tests inyectan un scheduler falso (sin GLib ni display Wayland)
y manejan el drenado de la cola a mano.

CAPACIDAD: la pila muestra a lo sumo `MAX_VISIBLE` toasts (spec `toast-stack`);
el resto ESPERA en la cola hasta que se libere un hueco, y al liberarse entra la
primera de la cola. Por eso los tests que necesitan ver entrar más de
`MAX_VISIBLE` notificaciones cierran una para hacer lugar (`_drenar`), y el orden
se lee de `_creados` (todas las que entraron alguna vez).

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
    # `_creados` guarda TODAS las que entraron a la pila —incluidas las que se
    # cerraron para liberar un hueco—, así los tests de ORDEN no dependen de
    # cuántas caben a la vez (MAX_VISIBLE).
    mgr._creados = []

    def fake_show(nid, kwargs):
        popup = vd.WaylandPopup(**kwargs)
        mgr._creados.append((nid, popup))
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


def _entrada(mgr):
    """nids de TODAS las notificaciones que entraron a la pila, en ese orden."""
    return [nid for nid, _ in mgr._creados]


def _drenar(mgr, scheduled, total):
    """Deja entrar `total` notificaciones respetando la capacidad de la pila.

    La pila muestra a lo sumo MAX_VISIBLE toasts: cuando se llena, se cierra la
    más vieja para liberar el hueco antes del siguiente tick (cerrar ya deja
    entrar a la primera de la cola). El orden de ENTRADA es lo que estos tests
    verifican (FIFO por llegada), así que se lee de `_creados` y no de `_active`:
    las que se cerraron para hacer lugar también cuentan.
    """
    while len(mgr._creados) < total:
        if mgr._pending and len(mgr._active) < vd.NotificationManager.MAX_VISIBLE:
            _run_one_pump(scheduled)
        elif mgr._active:
            mgr._close_id(mgr._active[0][0])
        else:
            break
    return [p for _, p in mgr._creados]


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
    assert len(mgr._pending) == 2
    # La pila se llenó: el resto espera. Cerrar una libera el hueco y deja
    # entrar a la siguiente (spec `toast-stack`).
    mgr._close_id(mgr._active[0][0])
    assert len(mgr._active) == 2
    assert len(mgr._pending) == 1
    # El mismo drenado vacía la cola entera.
    _drenar(mgr, scheduled, 4)
    assert len(mgr._pending) == 0
    assert len(mgr._creados) == 4


def test_burst_order_preserves_fifo_for_same_urgency():
    mgr, scheduled = _make_manager()
    for i in range(3):
        mgr.notify(summary="n{}".format(i), app_name="app",
                   hints={"urgency": 1})
    # FIFO: el primero en encolar es el primero en mostrarse.
    _drenar(mgr, scheduled, 3)
    entrada = _entrada(mgr)
    # Los nids se asignan en orden creciente => FIFO respeta el orden de llegada.
    assert entrada == sorted(entrada)


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
    _drenar(mgr, scheduled, 4)
    assert _entrada(mgr) == llegadas, (
        "spec toast-orden-llegada / 'La pila se ordena por llegada': un burst "
        "de tipos mezclados tiene que mostrarse en el orden en que llegó "
        "(%s); la pila salió en %s — el orden lo está decidiendo la `urgency` "
        "y no la llegada" % (llegadas, _entrada(mgr))
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
    _drenar(mgr, scheduled, 3)
    assert _entrada(mgr) == [primero, segundo, critico]


def test_un_low_no_se_rezaqa_al_final():
    """Scenario "Un low no se rezaqa al final": llega en medio y se queda ahí.

    Rojo hoy: el `low` baja al fondo de la cola aunque haya llegado segundo."""
    mgr, scheduled = _make_manager()
    critico = mgr.notify(summary="a", app_name="app", hints={"urgency": 2})
    bajo = mgr.notify(summary="b", app_name="app", hints={"urgency": 0})
    normal = mgr.notify(summary="c", app_name="app", hints={"urgency": 1})

    _drenar(mgr, scheduled, 3)
    assert _entrada(mgr) == [critico, bajo, normal], (
        "spec toast-orden-llegada / 'Un low no se rezaqa al final': el `low` "
        "llegó segundo y tiene que quedar segundo; la pila quedó %s (se "
        "ordenó por `urgency`)" % (_entrada(mgr),)
    )


def test_vencer_un_toast_deja_entrar_a_la_siguiente_de_la_cola():
    """Scenario "Se libera un hueco" (spec `toast-stack`): un toast que se VENCE
    por timer —no un cierre explícito— también libera el hueco y deja entrar a la
    primera de la cola.

    Rojo hoy: el popup vencido avisa por `on_close` → `_on_closed`, que solo
    limpia `_active`; el reflow y el drenado de la cola viven en `_close_id`, y
    el vencimiento por timer no pasa por ahí. Con la pila llena (2), las
    pendientes se quedan esperando para siempre."""
    mgr, scheduled = _make_manager()
    for i in range(3):
        mgr.notify(summary="n{}".format(i), app_name="app")
    for _ in range(vd.NotificationManager.MAX_VISIBLE):
        _run_one_pump(scheduled)
    assert len(mgr._active) == 2
    assert len(mgr._pending) == 1

    # Vence el primero (timer del popup → on_close → _on_closed).
    mgr._active[0][1]._close()

    assert len(mgr._active) == 2, (
        "al vencer un toast tiene que entrar la primera de la cola; quedaron "
        "%s activos y %s pendientes" % (len(mgr._active), len(mgr._pending))
    )
    assert len(mgr._pending) == 0, (
        "la cola tiene que quedar vacía; quedaron %s esperando"
        % (len(mgr._pending),)
    )


def test_la_toast_no_se_crea_hasta_que_haya_espacio_visual():
    """Regla del usuario (textual): "la toast no se crea si no hasta que haya
    espacio visual, si solo se puede mostrar 2 toast a la vez".

    Llegan 10 de golpe → se CREAN (y se muestran) solo las 2 primeras; las otras 8
    esperan en la cola como DATOS: sin popup, sin ventana y sin timer. Cada vez que
    se libera un hueco —vence el timeout o el usuario cierra— se crea la siguiente,
    en orden de llegada, y nunca hay una tercera creada.

    La mezcla de urgencias (1, 2, 0) cubre el scenario "La capacidad no depende del
    tipo": ningún tipo gana un hueco extra. `_creados` es la lista de popups
    CONSTRUIDOS: contar ahí es contar toasts creados (lo que la regla prohíbe de más).
    """
    mgr, scheduled = _make_manager()
    nids = [
        mgr.notify(summary="n{}".format(i), app_name="app",
                   hints={"urgency": (1, 2, 0)[i % 3]})
        for i in range(10)
    ]
    tope = vd.NotificationManager.MAX_VISIBLE

    for _ in range(tope):
        _run_one_pump(scheduled)
    assert _entrada(mgr) == nids[:tope], (
        "solo se crean las %s primeras; se crearon %s" % (tope, _entrada(mgr))
    )
    assert len(mgr._pending) == 10 - tope, (
        "el resto espera SIN estar creado; quedaron %s" % (len(mgr._pending),)
    )
    assert len(scheduled) == tope, (
        "con la pila llena el pump no se vuelve a agendar (no se crea una tercera "
        "sin cerrar un hueco); agendó %s veces" % (len(scheduled),)
    )

    # Cada hueco liberado crea EXACTAMENTE la siguiente de la fila. Se alternan
    # los DOS caminos de liberación: vencimiento del timer (`popup._close()` →
    # `on_close` → `_on_closed`, el mismo camino que corre el timeout real) y
    # cierre explícito (`_close_id`, el del click).
    for i in range(10 - tope):
        if i % 2 == 0:
            mgr._active[0][1]._close()          # se vence el de arriba
        else:
            mgr._close_id(mgr._active[0][0])    # el usuario cierra el de arriba
        assert len(mgr._creados) == tope + i + 1, (
            "al liberar un hueco se crea UNA y solo una toast; van %s creadas"
            % (len(mgr._creados),)
        )
        assert len(mgr._active) == tope, (
            "nunca hay más de %s creadas/mostradas a la vez; hay %s"
            % (tope, len(mgr._active))
        )
    assert _entrada(mgr) == nids, (
        "el orden de entrada es el de llegada (FIFO); entraron %s" % (_entrada(mgr),)
    )
    assert len(mgr._pending) == 0, "la cola quedó vacía"


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
    popups = _drenar(mgr, scheduled, 3)
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