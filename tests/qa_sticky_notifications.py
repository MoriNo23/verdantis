#!/usr/bin/env python3
"""QA helper: send persistent (sticky) notifications via DBus so they stay
on screen until YOU kill them. Useful for visual inspection / screenshots.

Uses Gio.DBusConnection (same stack as verdantis itself) -- no extra deps.
Sends the raw org.freedesktop.Notifications.Notify method with expire_timeout=0
(the freedesktop "persistent" value, confirmed in
  - plasma-workspace libnotificationmanager/server_p.cpp:331
      "// -1 = server default, 0 would be persistent"
  - mako criteria.c:482  expiring = (requested_timeout != 0)
  - dunst: timeout==0 -> "sticky", never expires).

Usage:
    .venv/bin/python tests/qa_sticky_notifications.py            # send all
    .venv/bin/python tests/qa_sticky_notifications.py pinterest  # send one
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib

BUS_NAME = "org.freedesktop.Notifications"
OBJ = "/org/freedesktop/Notifications"
IFACE = "org.freedesktop.Notifications"


def _notify(app_name, summary, body, actions=None, hints=None,
            expire_timeout=0, replaces_id=0):
    conn = Gio.bus_get_sync(Gio.BusType.SESSION)
    actions = actions or []
    hints = hints or {}
    # signature: s us ssasa{sv}i  -> app,replaces,icon,summary,body,actions,hints,timeout
    val = GLib.Variant(
        "(susssasa{sv}i)",
        (app_name, replaces_id, "", summary, body, actions, hints, expire_timeout),
    )
    nid = conn.call_sync(
        BUS_NAME, OBJ, IFACE, "Notify",
        val, GLib.VariantType.new("(u)"),
        Gio.DBusCallFlags.NONE, -1, None,
    )[0]
    print("sent id={} app={!r} summary={!r} actions={} expire={}".format(
        nid, app_name, summary, actions, expire_timeout))
    return nid


SCENARIOS = {
    # Pinterest-style: browser tab, requireInteraction -> expire_timeout=0,
    # actions=["default", ...] so the browser handles its own activation.
    "pinterest": lambda: _notify(
        "Brave", "Pinterest", "Nueva idea para ti: Mesa de madera reciclada",
        actions=["default", "Open"],
        hints={"desktop-entry": GLib.Variant("s", "brave-browser"),
               "x-kde-urls": GLib.Variant("as", ["https://pinterest.com/pin/123"])},
        expire_timeout=0),
    "slack": lambda: _notify(
        "Chrome", "Slack", "Juan: ¿viste el repo de verdantis?",
        actions=["default", "Reply"],
        hints={"desktop-entry": GLib.Variant("s", "google-chrome")},
        expire_timeout=0),
    # Native app with URL but NO actions (dunst: open URL when no actions).
    "native-url": lambda: _notify(
        "DownloadManager", "Download Manager", "Descarga completa: reporte.pdf",
        actions=[],
        hints={"x-kde-urls": GLib.Variant("as", ["https://example.com/reporte.pdf"])},
        expire_timeout=0),
    "critical": lambda: _notify(
        "System", "Backup", "El respaldo falló (disco lleno)",
        actions=[],
        hints={"urgency": GLib.Variant("y", 2)},
        expire_timeout=0),
    "transient": lambda: _notify(
        "System", "Volume", "Volumen al 50%",
        actions=[], expire_timeout=6000),
}


def main():
    import sys
    keys = sys.argv[1:] or list(SCENARIOS)
    for k in keys:
        if k not in SCENARIOS:
            print("unknown scenario:", k)
            continue
        SCENARIOS[k]()
    print("\nSticky notifications sent with expire_timeout=0 -- they will NOT "
          "auto-close. Close them manually (or restart verdantis) to clear.")


if __name__ == "__main__":
    main()
