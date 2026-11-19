"""Tests del ícono de bandeja (org.kde.StatusNotifierItem + DBusMenu).

Corren sobre un bus PRIVADO (`Gio.TestDBus`), no el bus de la sesión: exportan
el objeto, lo consultan con Properties.Get/GetAll y disparan Activate y los
clicks del menú. Así se verifica el contrato que consume el systray de KDE sin
depender de una sesión gráfica.
"""
import subprocess

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

import pytest

import tray


@pytest.fixture
def par():
    """(servicio, cliente) en un dbus-daemon privado.

    Se lanza un `dbus-daemon` aparte en vez de `Gio.TestDBus`: cuando otro test
    ya inicializó GDK, `tb.down()` espera hasta 30 s a que cierren conexiones
    que no son nuestras. Con el proceso propio, el teardown es inmediato.

    Dos conexiones a propósito: una llamada SÍNCRONA a la misma conexión que
    sirve el objeto se queda esperando su propia respuesta (deadlock sin bucle
    principal). El systray real es siempre otro proceso.
    """
    proc = subprocess.Popen(
        ["dbus-daemon", "--session", "--nofork", "--print-address=1"],
        stdout=subprocess.PIPE, text=True)
    addr = proc.stdout.readline().strip()
    assert addr, "dbus-daemon no arrojó una dirección"

    def nueva():
        return Gio.DBusConnection.new_for_address_sync(
            addr,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
    a, b = nueva(), nueva()
    try:
        yield a, b
    finally:
        for c in (a, b):
            try:
                c.close_sync(None)
            except Exception:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc.stdout.close()


@pytest.fixture
def conn(par):
    return par[0]


def _cliente(par):
    return par[1]


def _llamar(conn, destino, path, iface, method, args, rtype):
    """Llamada async + bucle anidado: el objeto servido vive en la MISMA
    conexión de test y necesita que el contexto principal corra para responder.
    `call_sync` bloquearía ese contexto y la llamada muere por timeout.
    """
    loop = GLib.MainLoop()
    salida = {}

    def cb(c, res):
        try:
            salida["r"] = c.call_finish(res)
        except Exception as e:
            salida["e"] = e
        loop.quit()

    conn.call(destino, path, iface, method, args, GLib.VariantType(rtype),
              Gio.DBusCallFlags.NONE, 2000, None, cb)
    loop.run()
    if "e" in salida:
        raise salida["e"]
    return salida["r"]


def _get(conn, iface, prop, destino=None):
    return _llamar(conn, destino or conn.get_unique_name(),
                   "/StatusNotifierItem", "org.freedesktop.DBus.Properties",
                   "Get", GLib.Variant("(ss)", (iface, prop)), "(v)")


def _call(conn, path, iface, method, args, rtype="()", destino=None):
    return _llamar(conn, destino or conn.get_unique_name(), path, iface,
                   method, args, rtype)


def _tray(conn, abierto=None, limpiado=None):
    t = tray.TrayIcon(
        conn=conn,
        on_open=lambda: abierto.append(1),
        on_clear=lambda: limpiado.append(1),
    )
    t.start(register_watcher=False)
    return t


# ── RED 1: el ítem se expone con las propiedades que lee el systray ──────

def test_sni_expone_propiedades(par):
    servicio, cliente = par
    _tray(servicio)
    dest = servicio.get_unique_name()
    assert _get(cliente, "org.kde.StatusNotifierItem", "Category", dest)[0] == "ApplicationStatus"
    assert _get(cliente, "org.kde.StatusNotifierItem", "Id", dest)[0] == "verdantis"
    assert _get(cliente, "org.kde.StatusNotifierItem", "Status", dest)[0] == "Active"
    assert _get(cliente, "org.kde.StatusNotifierItem", "Menu", dest)[0] == "/MenuBar"


def test_sni_publica_pixmap(par):
    """Sin pixmap el systray puede caer al tema y mostrar el icono genérico."""
    servicio, cliente = par
    _tray(servicio)
    v = _get(cliente, "org.kde.StatusNotifierItem", "IconPixmap",
             servicio.get_unique_name())[0]
    [(ancho, alto, datos)] = v
    assert (ancho, alto) == (48, 48)
    assert len(datos) == 48 * 48 * 4


def test_sni_activar_abre_el_centro(par):
    servicio, cliente = par
    abierto = []
    _tray(servicio, abierto=abierto)
    _call(cliente, "/StatusNotifierItem", "org.kde.StatusNotifierItem",
          "Activate", GLib.Variant("(ii)", (0, 0)),
          destino=servicio.get_unique_name())
    assert abierto == [1]


# ── RED 2: el menú lista historial y limpiar ─────────────────────────────

def test_menu_layout_tiene_los_items(par):
    servicio, cliente = par
    _tray(servicio)
    rev, layout = _call(cliente, "/MenuBar", "com.canonical.dbusmenu",
                        "GetLayout", GLib.Variant("(ii)", (0, -1)),
                        "(u(ia{sv}av))",
                        destino=servicio.get_unique_name()).unpack()
    assert rev >= 1
    _id, props, hijos = layout
    labels = [h[1].get("label") for h in hijos]
    assert "Abrir historial" in labels
    assert "Limpiar historial" in labels


def test_menu_click_en_limpiar_llama_al_callback(par):
    servicio, cliente = par
    limpiado = []
    _tray(servicio, limpiado=limpiado)
    dest = servicio.get_unique_name()
    _, layout = _call(cliente, "/MenuBar", "com.canonical.dbusmenu",
                      "GetLayout", GLib.Variant("(ii)", (0, -1)),
                      "(u(ia{sv}av))", destino=dest).unpack()
    _id, _props, hijos = layout
    idx = [h[1].get("label") for h in hijos].index("Limpiar historial")
    item_id = hijos[idx][0]
    _call(cliente, "/MenuBar", "com.canonical.dbusmenu", "Event",
          GLib.Variant("(isvu)", (item_id, "clicked",
                                  GLib.Variant("s", ""), 0)), destino=dest)
    assert limpiado == [1]


def test_menu_click_en_abrir_llama_al_callback(par):
    servicio, cliente = par
    abierto = []
    _tray(servicio, abierto=abierto)
    dest = servicio.get_unique_name()
    _, layout = _call(cliente, "/MenuBar", "com.canonical.dbusmenu",
                      "GetLayout", GLib.Variant("(ii)", (0, -1)),
                      "(u(ia{sv}av))", destino=dest).unpack()
    hijos = layout[2]
    idx = [h[1].get("label") for h in hijos].index("Abrir historial")
    _call(cliente, "/MenuBar", "com.canonical.dbusmenu", "Event",
          GLib.Variant("(isvu)", (hijos[idx][0], "clicked",
                                  GLib.Variant("s", ""), 0)), destino=dest)
    assert abierto == [1]
