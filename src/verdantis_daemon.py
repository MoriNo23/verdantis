import json
import os
import subprocess
import time
os.environ['GDK_BACKEND'] = 'wayland'

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, GtkLayerShell, GLib, Gio

from wayland_popup import WaylandPopup, _find_desktop_file, _extract_markup_url

NOTIFICATIONS_XML = '''
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg type="s" name="app_name" direction="in"/>
      <arg type="u" name="replaces_id" direction="in"/>
      <arg type="s" name="app_icon" direction="in"/>
      <arg type="s" name="summary" direction="in"/>
      <arg type="s" name="body" direction="in"/>
      <arg type="as" name="actions" direction="in"/>
      <arg type="a{sv}" name="hints" direction="in"/>
      <arg type="i" name="expire_timeout" direction="in"/>
      <arg type="u" name="id" direction="out"/>
    </method>
    <method name="CloseNotification">
      <arg type="u" name="id" direction="in"/>
    </method>
    <method name="GetCapabilities">
      <arg type="as" name="caps" direction="out"/>
    </method>
    <method name="GetServerInformation">
      <arg type="s" name="name" direction="out"/>
      <arg type="s" name="vendor" direction="out"/>
      <arg type="s" name="version" direction="out"/>
      <arg type="s" name="spec_version" direction="out"/>
    </method>
    <signal name="NotificationClosed">
      <arg type="u" name="id"/>
      <arg type="u" name="reason"/>
    </signal>
    <signal name="ActionInvoked">
      <arg type="u" name="id"/>
      <arg type="s" name="action_key"/>
    </signal>
  </interface>
</node>
'''


class NotificationManager:
    MAX_VISIBLE = 5
    STACK_GAP = 8

    def __init__(self, corner="top-right"):
        self.corner = corner
        self._active = []
        self._queue = []
        self._next_id = 1
        self._corner = corner
        self._dbus_bus = None
        self._notifications = {}

    def set_dbus(self, bus):
        self._dbus_bus = bus

    def _extract_url(self, hints):
        url = None
        try:
            kde_urls = hints.get("x-kde-urls")
            if kde_urls and len(kde_urls) > 0:
                url = kde_urls[0]
        except Exception:
            pass
        if not url:
            try:
                url = hints.get("url", "")
            except Exception:
                pass
        if not url:
            try:
                data = hints.get("data")
                if data:
                    if isinstance(data, bytes):
                        data = json.loads(data.decode("utf-8", errors="replace"))
                    if isinstance(data, dict):
                        url = data.get("url", "")
                    elif isinstance(data, str):
                        try:
                            url = json.loads(data).get("url", "")
                        except Exception:
                            url = data
            except Exception:
                pass
        if url and not url.startswith(("http://", "https://", "mailto:", "tel:")):
            url = ""
        return url

    def notify(self, app_name="", app_icon="", summary="", body="",
               actions=None, hints=None, expire_timeout=-1, replaces_id=0):
        if hints is None:
            hints = {}
        if actions is None:
            actions = []

        if replaces_id > 0:
            self._close_id(replaces_id)

        nid = self._next_id
        self._next_id += 1

        url = self._extract_url(hints)
        # URL de hyperlink en el body (body-hyperlinks): <a href="...">
        markup_url = _extract_markup_url(body)
        if not url and markup_url:
            url = markup_url
        desktop_entry = hints.get("desktop-entry", "") or app_name
        # Urgency: BYTE 0=low, 1=normal, 2=critical (spec freedesktop 1.2)
        urgency = hints.get("urgency", 1)
        try:
            urgency = int(urgency)
        except (TypeError, ValueError):
            urgency = 1
        if urgency not in (0, 1, 2):
            urgency = 1
        self._notifications[nid] = {
            "actions": actions,
            "hints": hints,
            "url": url,
            "app_name": app_name,
            "desktop_entry": desktop_entry,
            "urgency": urgency,
        }

        avatar_path = hints.get("image-path", "")
        if not avatar_path or not os.path.exists(avatar_path):
            avatar_path = app_icon if app_icon and os.path.exists(app_icon) else ""

        app_icon_file = app_icon if app_icon and os.path.exists(app_icon) else ""

        image_data = hints.get("image-data", None)
        image_path = hints.get("image-path", "")
        banner_path = ""
        if image_path and os.path.exists(image_path) and image_path != avatar_path:
            banner_path = image_path

        kwargs = {
            "titulo": summary,
            "cuerpo": body,
            "icon_path": avatar_path if avatar_path else None,
            "image_path": banner_path if banner_path else None,
            "image_data_raw": image_data,
            "duration": expire_timeout if expire_timeout > 0 else 6000,
            "corner": self._corner,
            "accent": hints.get("accent", "#80cbc4"),
            "urgency": urgency,
            "app_name": app_name,
            "app_icon": app_icon_file,
            "on_close": lambda nid=nid: self._on_closed(nid),
            "on_click": lambda nid=nid: self._on_action_invoked(nid),
        }

        if len(self._active) < self.MAX_VISIBLE:
            self._show_popup(nid, kwargs)
        else:
            self._queue.append((nid, kwargs))

        return nid

    def _show_popup(self, nid, kwargs):
        popup = WaylandPopup(**kwargs)
        idx = len(self._active)
        popup.prepare()
        popup.set_stack_margin(idx)
        self._active.append((nid, popup))

    def _close_id(self, nid):
        for i, (aid, popup) in enumerate(self._active):
            if aid == nid:
                popup._close()
                break
        self._queue = [(qid, qk) for qid, qk in self._queue if qid != nid]

    def _focus_or_activate_app(self, desktop_entry, app_name):
        target = desktop_entry or app_name
        if not target:
            return
        desktop_path = _find_desktop_file(target)
        desktop_id = ""
        if desktop_path and os.path.exists(desktop_path):
            desktop_id = os.path.splitext(os.path.basename(desktop_path))[0]
            try:
                app_info = Gio.DesktopAppInfo.new_from_filename(desktop_path)
                if app_info:
                    app_info.launch([], None)
                    return
            except Exception:
                pass
        # Fallback: gtk-launch con el desktop-id o el nombre de la app
        launch_id = desktop_id or target
        try:
            subprocess.Popen(
                ["gtk-launch", launch_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _on_action_invoked(self, nid):
        info = self._notifications.get(nid, {})
        actions = info.get("actions", [])
        url = info.get("url", "")
        app_name = info.get("app_name", "")
        desktop_entry = info.get("desktop_entry", "")

        default_action = "default"
        for i in range(0, len(actions), 2):
            if actions[i] == "default":
                default_action = actions[i]
                break

        if self._dbus_bus:
            try:
                self._dbus_bus.emit_signal(
                    None, "/org/freedesktop/Notifications",
                    "org.freedesktop.Notifications", "ActionInvoked",
                    GLib.Variant("(us)", (nid, default_action)),
                )
            except Exception:
                pass

        if url:
            try:
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            self._focus_or_activate_app(desktop_entry, app_name)

        # Cierre inmediato del popup visual (su callback dispara _on_closed)
        for aid, popup in list(self._active):
            if aid == nid:
                popup._close()
                break

    def _on_closed(self, nid):
        self._active = [(aid, p) for aid, p in self._active if aid != nid]
        self._notifications.pop(nid, None)

        for i, (_, p) in enumerate(self._active):
            p.set_stack_margin(i)

        if self._queue and len(self._active) < self.MAX_VISIBLE:
            qid, qk = self._queue.pop(0)
            self._show_popup(qid, qk)

        if self._dbus_bus:
            self._dbus_bus.emit_signal(
                None, "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", "NotificationClosed",
                GLib.Variant("(uu)", (nid, 2)),
            )

    def close_all(self):
        for _, popup in self._active:
            popup._close()
        self._active = []
        self._queue = []
        self._notifications = {}


class NotificationDaemon:
    def __init__(self, corner="top-right"):
        self._corner = corner
        self._manager = NotificationManager(corner)
        self._bus = None
        self._loop = None
        self._owned = False

    def _on_bus_acquired(self, conn, name):
        node = Gio.DBusNodeInfo.new_for_xml(NOTIFICATIONS_XML)
        conn.register_object(
            "/org/freedesktop/Notifications",
            node.interfaces[0],
            self._handle_method_call,
            self._handle_get_property,
            None,
        )
        self._bus = conn
        self._manager.set_dbus(conn)

    def _handle_method_call(self, conn, sender, obj_path, iface_name, method_name, params, invocation):
        if method_name == "Notify":
            app_name, replaces_id, app_icon, summary, body, actions, hints, timeout = params
            nid = self._manager.notify(
                app_name=app_name, app_icon=app_icon,
                summary=summary, body=body,
                actions=actions, hints=hints,
                expire_timeout=timeout, replaces_id=replaces_id,
            )
            invocation.return_value(GLib.Variant("(u)", (nid,)))
        elif method_name == "CloseNotification":
            nid = params[0]
            self._manager._close_id(nid)
            invocation.return_value(None)
        elif method_name == "GetCapabilities":
            caps = ["actions", "body", "body-markup", "body-hyperlinks",
                    "icon-static", "persistence"]
            invocation.return_value(GLib.Variant("(as)", (caps,)))
        elif method_name == "GetServerInformation":
            invocation.return_value(GLib.Variant("(ssss)", (
                "Verdantis", "Verdantis", "0.1.0", "1.2",
            )))

    def _handle_get_property(self, conn, sender, obj_path, iface_name, prop_name):
        raise GLib.GError(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND, "no props")

    def _on_name_acquired(self, conn, name):
        self._owned = True

    def _on_name_lost(self, conn, name):
        self._owned = False

    def run(self):
        Gio.bus_own_name(
            Gio.BusType.SESSION,
            "org.freedesktop.Notifications",
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )
        self._loop = GLib.MainLoop()
        self._loop.run()

    def stop(self):
        if self._loop:
            self._loop.quit()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Daemon de notificaciones Wayland (DBus)")
    parser.add_argument("--corner", default="top-right",
                        choices=["top-right", "top-left", "bottom-right", "bottom-left"])
    args = parser.parse_args()

    daemon = NotificationDaemon(corner=args.corner)
    try:
        daemon.run()
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    main()
