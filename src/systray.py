"""Ícono de bandeja para KDE (StatusNotifierItem + DBusMenu).

Dialoga con `org.kde.StatusNotifierWatcher` del systray de Plasma. Click
izquierdo (`Activate`) abre el centro de notificaciones propio; click derecho
lista el menú DBusMenu ("Abrir historial" / "Limpiar historial").

No usa Qt ni Kirigami: es D-Bus puro sobre `Gio.DBusConnection`, igual que el
resto del daemon. El applet de Plasma no se puede reutilizar (es un
`Plasma/Applet` atado al modelo de SU daemon, GPL-2.0/3.0 vs MIT acá).
"""
import os
import struct

import gi
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gio, Gdk, GdkPixbuf, GLib

import notification_center as nc

_SNI_PATH = "/StatusNotifierItem"
_MENU_PATH = "/MenuBar"

_SNI_XML = """<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <signal name="NewIcon"/>
  </interface>
</node>"""

_MENU_XML = """<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="Status" type="s" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
  </interface>
</node>"""


def _pixmap_verdantis(size=48):
    """El isotipo oficial (assets/verdantis-icon.png) en ARGB32 para SNI.

    Antes se dibujaba a mano una "V" con cairo; hoy la marca es el pulpo
    esmeralda con marco de notificación, campana y pistas de circuito.
    """
    import cairo
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "verdantis-icon.png")
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(ruta, size, size, True)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()
    surf.flush()
    datos = bytes(surf.get_data())
    # KStatusNotifierItem espera ARGB32 nativo (cairo lo entrega en ese orden).
    return [(size, size, list(datos))]

class TrayIcon:
    """Exporta el ítem y el menú; `start()` es idempotente."""

    def __init__(self, conn=None, on_open=None, on_clear=None):
        self._conn = conn
        self._on_open = on_open or (lambda: None)
        self._on_clear = on_clear or (lambda: None)
        self._registrado = False
        self._pixmap = None
        self._nombre = "org.kde.StatusNotifierItem-%d-1" % os.getpid()

    # ── ciclo de vida ────────────────────────────────────────────────────

    def start(self, register_watcher=True):
        if self._registrado:
            return True
        try:
            if self._conn is None:
                self._conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._pixmap = _pixmap_verdantis()
            self._sni_info = Gio.DBusNodeInfo.new_for_xml(_SNI_XML)
            self._menu_info = Gio.DBusNodeInfo.new_for_xml(_MENU_XML)
            self._conn.register_object(
                _SNI_PATH, self._sni_info.interfaces[0],
                self._sni_llamada, self._prop_sni, None)
            self._conn.register_object(
                _MENU_PATH, self._menu_info.interfaces[0],
                self._menu_call, self._prop_menu, None)
            self._registrado = True
            if register_watcher:
                # El nombre propio solo hace falta para registrarse en el
                # watcher del systray; en tests se llama por nombre único y
                # pedir el nombre deja un RequestName pendiente que demora el
                # cierre de la conexión.
                Gio.bus_own_name_on_connection(
                    self._conn, self._nombre, Gio.BusNameOwnerFlags.NONE,
                    None, None)
                self._registrar_en_watcher()
            return True
        except Exception as e:
            print("[verdantis] bandeja no disponible: %s" % e, flush=True)
            return False

    def _registrar_en_watcher(self):
        try:
            self._conn.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self._nombre,)),
                None, Gio.DBusCallFlags.NONE, 2000, None)
        except Exception:
            # Sin systray (o sin watcher) el ítem queda exportado igual: sirve
            # para pruebas y no rompe el daemon.
            pass

    # ── SNI ──────────────────────────────────────────────────────────────

    def _prop_sni(self, _conn, _sender, _path, _iface, prop):
        valores = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "verdantis"),
            "Title": GLib.Variant("s", "Verdantis"),
            "Status": GLib.Variant("s", "Active"),
            "IconName": GLib.Variant("s", "preferences-desktop-notification"),
            "IconPixmap": GLib.Variant("a(iiay)", self._pixmap),
            "Menu": GLib.Variant("o", _MENU_PATH),
            "ItemIsMenu": GLib.Variant("b", False),
            "WindowId": GLib.Variant("i", 0),
        }
        return valores.get(prop)

    def _sni_llamada(self, _conn, _sender, _path, _iface, method, params,
                     invocation):
        try:
            if method in ("Activate", "SecondaryActivate"):
                self._on_open()
            invocation.return_value(None)
        except Exception as e:
            invocation.return_dbus_error("org.verdantis.Error", str(e))

    # ── DBusMenu ─────────────────────────────────────────────────────────

    def _prop_menu(self, _conn, _sender, _path, _iface, prop):
        if prop == "Version":
            return GLib.Variant("u", 3)
        if prop == "Status":
            return GLib.Variant("s", "normal")
        return None

    def _layout(self):
        """(id, props, hijos) raíz + items, en la forma que espera DBusMenu."""
        hijos = []
        for item in nc.menu_items():
            props = {
                "label": GLib.Variant("s", item["label"]),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
            hijos.append(GLib.Variant("(ia{sv}av)", (item["id"], props, [])))
        raiz = (0, {}, hijos)
        return raiz

    def _menu_call(self, _conn, _sender, _path, _iface, method, params,
                   invocation):
        try:
            if method == "GetLayout":
                raiz = self._layout()
                invocation.return_value(
                    GLib.Variant("(u(ia{sv}av))", (1, raiz)))
                return
            if method == "GetGroupProperties":
                ids, _props = params.unpack()
                items = []
                for item in nc.menu_items():
                    if item["id"] in ids:
                        items.append((item["id"], {
                            "label": GLib.Variant("s", item["label"]),
                            "enabled": GLib.Variant("b", True),
                            "visible": GLib.Variant("b", True),
                        }))
                invocation.return_value(GLib.Variant("(a(ia{sv}))", (items,)))
                return
            if method == "Event":
                item_id, evento, _data, _ts = params.unpack()
                if evento == "clicked":
                    self._accion(item_id)
                invocation.return_value(None)
                return
            if method == "AboutToShow":
                invocation.return_value(GLib.Variant("(b)", (False,)))
                return
            invocation.return_value(None)
        except Exception as e:
            invocation.return_dbus_error("org.verdantis.Error", str(e))

    def _accion(self, item_id):
        for item in nc.menu_items():
            if item["id"] != item_id:
                continue
            if item["action"] == "open":
                self._on_open()
            elif item["action"] == "clear":
                self._on_clear()
            return
