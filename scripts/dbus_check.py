#!/usr/bin/env python3
"""Test de FUNCIONAMIENTO end-to-end del contrato freedesktop 1.2.

Las señales de Verdantis son DIRIGIDAS al sender de Notify (no broadcast),
así que `gdbus monitor` no las ve. Este script usa una sola GDBusConnection:
hace Notify desde ella (su unique-name es el sender) y se suscribe a las
señales del daemon en esa MISMA conexión con signal_subscribe.

Verifica: Notify -> ID, CloseNotification -> NotificationClosed(razón 3),
GetCapabilities y GetServerInformation.
"""
import sys
import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

BUS = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
IFACE = "org.freedesktop.Notifications"

seen = []
loop = GLib.MainLoop()


def on_signal(conn, sender, path, iface, signal, params, *extra):
    seen.append((signal, params))
    print("  señal: %s %s" % (signal, params.unpack()))


def main():
    conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    # Suscribirse a TODAS las señales del daemon en esta conexión (incluye las
    # dirigidas a nuestro unique-name, que es quien hace Notify).
    # sender=None: en D-Bus el sender real de la señal es el unique-name del
    # emisor (:1.x), NO el bus-name org.freedesktop.Notifications.
    sub = conn.signal_subscribe(
        None, IFACE, None, PATH, None,
        Gio.DBusSignalFlags.NONE, on_signal)
    print("==> Suscrito como %s" % conn.get_unique_name())

    def call(method, variant=None):
        return conn.call_sync(BUS, PATH, IFACE, method, variant, None,
                              Gio.DBusCallFlags.NONE, 8000, None)

    # 1. Notify con actions
    v = GLib.Variant("(susssasa{sv}i)",
                     ("verdantis-test", 0, "test", "Prueba", "Cuerpo",
                      ["default", "Abrir", "go", "Ir"], {}, 0))
    r = call("Notify", v)
    nid = r.unpack()[0]
    print("==> Notify -> ID=%s" % nid)

    # 2. CloseNotification desde la MISMA conexión (destino de la señal)
    call("CloseNotification", GLib.Variant("(u)", (nid,)))
    print("==> CloseNotification(%s) enviado" % nid)

    # 3. GetCapabilities / GetServerInformation
    # unpack() de un retorno con UN argumento devuelve una tupla de 1.
    caps = call("GetCapabilities").unpack()[0]
    info = call("GetServerInformation").unpack()
    print("==> Caps:", caps)
    print("==> Server:", info)

    # 4. Cerrar una notificación EN COLA: llega un burst y cerramos al que
    # todavía no se mostró (stagger). El spec exige NotificationClosed/3 igual.
    nids = []
    for i in range(4):
        rr = call("Notify", GLib.Variant("(susssasa{sv}i)",
                  ("verdantis-test", 0, "test", "Burst %d" % i, "cuerpo",
                   [], {}, 0)))
        nids.append(rr.unpack()[0])
    cola_id = nids[-1]           # el último queda en _pending
    call("CloseNotification", GLib.Variant("(u)", (cola_id,)))
    print("==> Burst %s; CloseNotification(%s) en cola" % (nids, cola_id))

    def finish():
        loop.quit()
        return False
    GLib.timeout_add(2000, finish)
    loop.run()
    conn.signal_unsubscribe(sub)

    closed = [s for s in seen if s[0] == "NotificationClosed"]
    if not closed:
        print("FAIL: no se recibió NotificationClosed", file=sys.stderr)
        return 1
    razon = closed[-1][1].unpack()[1]
    print("PASS: NotificationClosed recibida (razón=%s)" % razon)
    if (cola_id, 3) not in [c[1].unpack() for c in closed]:
        print("FAIL: la notificación en cola no emitió razón 3", file=sys.stderr)
        return 1
    print("PASS: la notificación en cola también emitió razón 3")
    if "actions" not in caps:
        print("FAIL: actions no anunciada", file=sys.stderr)
        return 1
    print("PASS: actions anunciada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
