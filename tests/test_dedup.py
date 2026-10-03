"""
Tests de la lógica de deduplicación de notificaciones por contenido.

Problema resuelto: apps que spamean la MISMA notificación N veces seguidas
sin usar replaces_id (pestañas web, PWAs, scripts) -> N toasts idénticos
encimados. La dedup detecta el contenido duplicado dentro de DEDUP_WINDOW
y lo REEMPLAZA (libera el anterior) en vez de dejar dos iguales.

Arquitectura actual: TODA notificación entra a `_pending` (batching con
stagger via `_pump`). Por eso la dedup se mide sobre el TOTAL de entradas
activas+pendientes que cargan UN contenido: dos notis idénticas -> 1 sola
entrada para ese contenido (la segunda reemplazó a la primera, que se
descarta de `_pending` vía `_close_id`).

Reglas:
- Mismo (app_name + summary + body) dentro de DEDUP_WINDOW -> 1 entrada
  para ese contenido; la 2da reemplaza a la 1ra.
- Fuera de DEDUP_WINDOW -> eventos legítimos (2 entradas).
- Normalización: mayúsculas y espacios/tabs colapsados no rompen la igualdad.
- Contenido distinto -> 2 entradas.
"""


from verdantis_daemon import NotificationManager, _dedup_key


class FakeBus:
    def emit_signal(self, *a):
        pass


def _notify(m, summary="t", body="b", app_name="app", **kw):
    return m.notify(
        app_name=app_name, app_icon="", summary=summary, body=body,
        actions=[], hints={}, expire_timeout=6000, **kw
    )


def _count_entries(m):
    """Total de entradas (activas + pendientes) que cargan cada contenido."""
    total = len([e for e in m._pending]) + len([e for e in m._active])
    return total


def _content_ids(m, key):
    """ids (active o pending) cuyo contenido es `key`, en orden de aparición."""
    ids = []
    ids += [e[0] for e in m._active if _dedup_key_for_popup(e) == key]
    ids += [e[0] for e in m._pending if e[1].get("_dedup_key") == key]
    return ids


def _dedup_key_for_popup(e):
    # los popups activos no guardan la clave; la recalculamos desde los kwargs
    k = e[1]
    return _dedup_key(k.get("app_name", ""), k.get("titulo", ""),
                      k.get("cuerpo", ""), "")


# --- _dedup_key (lógica pura) ---

def test_key_ignores_case():
    assert _dedup_key("WhatsApp", "Nuevo Msg", "hola") == \
        _dedup_key("whatsapp", "nuevo msg", "hola")


def test_key_collapses_whitespace():
    assert _dedup_key("app", "a  b", "c\nd") == _dedup_key("app", "a b", "c d")


def test_key_differs_on_content():
    assert _dedup_key("app", "titulo", "a") != _dedup_key("app", "titulo", "b")
    assert _dedup_key("app", "a", "body") != _dedup_key("otra", "a", "body")


def test_key_ignores_sender():
    assert _dedup_key("app", "t", "b", sender=":1.2") == \
        _dedup_key("app", "t", "b", sender=":1.999")


# --- Comportamiento dedup en NotificationManager ---

def test_duplicate_within_window_replaces_old_entry():
    m = NotificationManager()
    m.set_dbus(FakeBus())
    key = _dedup_key("app", "t", "b")
    nid1 = _notify(m)
    nid2 = _notify(m)  # mismo contenido, dentro de la ventana
    # nid1 fue liberado (ya no está activo ni pendiente)
    assert nid1 not in [e[0] for e in m._active]
    assert nid1 not in [e[0] for e in m._pending]
    # La dedup apunta al reemplazo
    assert m._dedup[key][0] == nid2
    # No quedan 2 toasts para el mismo contenido
    assert len([e for e in m._pending if e[0] == nid2]) == 1
    assert len(m._active) == 0  # ambos aún pendientes (batching)


def test_dedup_prevents_duplicate_toast_visible_after_pump():
    m = NotificationManager()
    m.set_dbus(FakeBus())
    _notify(m, summary="x")
    _notify(m, summary="x")  # duplicado
    # drenamos la cola manualmente
    while m._pending:
        m._pump()
    # solo UN toast visible para el contenido duplicado
    assert len(m._active) == 1


def test_distinct_content_does_not_dedup():
    m = NotificationManager()
    m.set_dbus(FakeBus())
    _notify(m, summary="uno")
    _notify(m, summary="otro")
    while m._pending:
        m._pump()
    assert len(m._active) == 2


def test_duplicate_outside_window_is_not_deduped():
    m = NotificationManager()
    m.set_dbus(FakeBus())
    key = _dedup_key("app", "t", "b")
    nid1 = _notify(m)
    # Expulsamos la primera de la ventana de dedup
    m._dedup[key] = (nid1, m._dedup[key][1] - (m.DEDUP_WINDOW + 1))
    nid2 = _notify(m)
    assert nid2 != nid1
    while m._pending:
        m._pump()
    assert len(m._active) == 2


def test_close_cleans_dedup_entry():
    m = NotificationManager()
    m.set_dbus(FakeBus())
    key = _dedup_key("app", "t", "b")
    nid1 = _notify(m)
    assert key in m._dedup
    m._close_id(nid1)
    assert key not in m._dedup


def test_replace_burst_keeps_single_toast():
    """Un flood de 5 notis idénticas -> exactamente 1 toast para ese contenido."""
    m = NotificationManager()
    m.set_dbus(FakeBus())
    for _ in range(5):
        _notify(m, summary="spam")
    while m._pending:
        m._pump()
    assert len(m._active) == 1
    # la dedup apunta a la última del flood
    assert len(m._dedup) == 1


def test_duplicate_active_is_replaced_not_stacked():
    """Duplicado que llega cuando la 1ra YA está activa (visible): la dedup
    cierra la activa y encola la nueva — nunca quedan dos iguales apiladas.

    (Portado de test_notify_dedup.py en la fusión de suites: era el único
    caso que ejercitaba el reemplazo sobre una toast VISIBLE, no pendiente.)"""
    m = NotificationManager()
    m.set_dbus(FakeBus())
    nid1 = _notify(m)
    while m._pending:
        m._pump()          # nid1 ya visible (activa)
    assert len(m._active) == 1
    nid2 = _notify(m)      # mismo contenido, mientras nid1 sigue activa
    while m._pending:
        m._pump()
    shown = [nid for nid, _ in m._active]
    assert shown == [nid2], (
        "la toast activa debe ser reemplazada por la nueva, no apilada"
    )
    assert len(m._active) == 1


def test_duplicate_suppressed_within_window_then_allowed_after():
    """Secuencia completa en el mismo manager: dentro de la ventana el dup
    reemplaza (queda 1 pendiente); con la ventana vencida un 3er aviso igual
    vuelve a ser legítimo (2 pendientes, id nuevo).

    (Portado de test_notify_dedup.py en la fusión de suites: cubría la
    transición suprimida->permitida con estado compartido.)"""
    m = NotificationManager()
    m.set_dbus(FakeBus())
    nid1 = _notify(m)
    nid2 = _notify(m)               # dentro de la ventana: reemplaza a nid1
    assert len(m._pending) == 1
    m.DEDUP_WINDOW = -1.0           # ventana vencida: avisos separados son legítimos
    nid3 = _notify(m)
    assert len(m._pending) == 2
    assert nid3 not in (nid1, nid2)