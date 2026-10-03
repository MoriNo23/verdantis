"""
Gaps menores del spec freedesktop 1.2 que verdantis NO manejaba:
  - urgency  : hint tipo BYTE (y) en DBus, no int suelto.
  - resident : si True, el toast NO se auto-cierra (como expire_timeout=0).
  - transient: no guardar en historial (verdantis no tiene historial, se
    guarda en metadata para future-proofing).
  - category : string de agrupacion ("im", "email", "presence"...).
  - suppress-sound / sound-name : control de sonido (no implementado, guardado).

Confirmado contra mako/dunst/KDE (notification.cpp:407-438):
  KDE lee urgency como .toInt() aceptando byte; resident y transient como bool;
  category como string. mako lee urgency con sd_bus_read "y" (byte).
"""


from verdantis_daemon import NotificationManager


def _daemon():
    return NotificationManager(corner="top-right")


# urgency: reading a byte tones DBus arrival.
def test_urgency_byte_variant():
    d = _daemon()
    # glbl reads it as regular int, but the code must handle it even if it
    # arrives as bytes (Python int works as-is, this documents the contract).
    nid = d.notify(app_name="Test", hints={"urgency": 2}, expire_timeout=0)
    assert d._notifications[nid]["urgency"] == 2  # critical


def test_urgency_out_of_range_clamps_to_normal():
    d = _daemon()
    nid = d.notify(app_name="Test", hints={"urgency": 99}, expire_timeout=0)
    assert d._notifications[nid]["urgency"] == 1  # normal (fallback)


def test_urgency_missing_defaults_normal():
    d = _daemon()
    nid = d.notify(app_name="Test", expire_timeout=0)
    assert d._notifications[nid]["urgency"] == 1


# resident: NO auto-cerrar
def test_resident_hint_makes_toast_sticky():
    d = _daemon()
    nid = d.notify(app_name="Test", hints={"resident": True},
                   expire_timeout=5000)
    info = d._notifications.get(nid, {})
    assert info.get("is_resident") is True


def test_resident_missing_is_false():
    d = _daemon()
    nid = d.notify(app_name="Test", expire_timeout=0)
    assert d._notifications[nid].get("is_resident") is False


# transient: metadata guardada
def test_transient_hint_recorded():
    d = _daemon()
    nid = d.notify(app_name="Test", hints={"transient": True}, expire_timeout=0)
    assert d._notifications[nid]["is_transient"] is True


def test_transient_missing_is_false():
    d = _daemon()
    nid = d.notify(app_name="Test", expire_timeout=0)
    assert d._notifications[nid]["is_transient"] is False


# category
def test_category_recorded():
    d = _daemon()
    nid = d.notify(app_name="Test", hints={"category": "im.received"},
                   expire_timeout=0)
    assert d._notifications[nid]["category"] == "im.received"


def test_category_missing_empty():
    d = _daemon()
    nid = d.notify(app_name="Test", expire_timeout=0)
    assert d._notifications[nid]["category"] == ""


# suppress-sound / sound-name
def test_suppress_sound_recorded():
    d = _daemon()
    nid = d.notify(app_name="Test", hints={"suppress-sound": True},
                   expire_timeout=0)
    assert d._notifications[nid]["suppress_sound"] is True


def test_sound_name_recorded():
    d = _daemon()
    nid = d.notify(app_name="Test", hints={"sound-name": "message-new-instant"},
                   expire_timeout=0)
    assert d._notifications[nid]["sound_name"] == "message-new-instant"
