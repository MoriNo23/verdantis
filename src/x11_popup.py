"""Fallback X11 (GTK4, sin layer-shell) para la notificación one-shot de verdantis.

Se carga SOLO en el branch X11 (import perezoso desde `verdantis.main`): el
daemon y el path Wayland no pagan este import. Un solo toolkit en el
proyecto — GTK4, reutilizando el render GSK de `NotificationWidget`; Qt quedó
fuera por completo.

GTK4 no expone mover la ventana ni hints de "keep above": sin layer-shell el
gestor de ventanas decide dónde aparece el toast. Tampoco hace falta pedir un
visual RGBA — GSK compone con alpha. Riesgo documentado: en un X11 sin
compositing manager el fondo puede salir negro; los X11 modernos lo traen.
"""
import os
import ctypes
# GDK_BACKEND=x11 ANTES de que cualquiera toque Gdk — convención de
# `wayland_popup` (que hace setdefault a 'wayland' y por eso no lo pisa):
# sin esto, `--force-fallback` dentro de una sesión Wayland elegiría backend
# wayland y la ventana no se comportaría como fallback X11.
os.environ.setdefault('GDK_BACKEND', 'x11')

import sys
import time

# GTK4 eliminó Gtk.Window.move()/set_keep_above() y Gdk.Monitor.get_workarea().
# En X11 lo reponemos con Xlib (presente en cualquier sesión X11) + EWMH.
_X = ctypes.CDLL("libX11.so.6")
_X.XOpenDisplay.argtypes = [ctypes.c_char_p]
_X.XOpenDisplay.restype = ctypes.c_void_p
_X.XCloseDisplay.argtypes = [ctypes.c_void_p]
_X.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
_X.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
_X.XInternAtom.restype = ctypes.c_ulong
_X.XChangeProperty.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
    ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_ulong), ctypes.c_int]
_X.XFlush.argtypes = [ctypes.c_void_p]
_XA_ATOM = 4          # Xatom.h
_PROP_REPLACE = 0     # X.h

# `wayland_popup` PRIMERO: carga libgtk4-layer-shell y fija Gtk/Gdk 4.0 y aporta
# el render — la ventana de acá es solo el contenedor.
from wayland_popup import NotificationWidget, _CARD_WIDTH
from app_info import APP_ID, DEFAULT_ACCENT
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkX11', '4.0')
from gi.repository import Gtk, GLib, Gdk, GdkX11


class NotificacionX11:
    """Toast one-shot en `Gtk.Window` común (fallback X11, sin layer-shell).

    Misma superficie de parámetros que el viejo fallback Qt: la rejija del
    one-shot es un simple cambio de módulo. La ventana se construye recién en
    `show()` (necesita display); sin display, aviso por stderr + exit 1."""

    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, margin=16, corner="top-right", accent=DEFAULT_ACCENT,
                 app_name="", app_icon="", on_click=None, buttons_actionable=True):
        self.titulo = titulo
        self.cuerpo = cuerpo
        self.icon_path = icon_path
        self.image_path = image_path
        self.duration = duration
        self.margin = margin
        self.corner = corner
        self.accent = accent
        self.app_name = app_name
        self.app_icon = app_icon
        self._on_click = on_click
        self._buttons_actionable = buttons_actionable
        self.window = None
        self._card = None
        self._h = 0
        self._start = 0
        self._loop = None
        self._hover_credit_ms = 0   # ms de hover: el crédito que pausa el wipe
        self._closed = False

    def _build_ui(self):
        self.window = Gtk.Window()
        self.window.set_decorated(False)
        # GTK4 ya no tiene set_size_request en toplevel: default_size manda.
        self.window.connect("close-request", lambda *a: self._close())
        self.window.connect("destroy", lambda *a: self._loop.quit())

        self._card = NotificationWidget(
            self.app_name, self.app_icon, self.titulo, self.cuerpo,
            self.icon_path, self.image_path, self.accent,
            on_click=self._on_click,
            on_resize=self._resize_card,
            on_close=self._close,
            persistent=(self.duration == 0),
            buttons_actionable=self._buttons_actionable,
        )
        self._h = self._card.desired_height()
        self._card.set_size_request(_CARD_WIDTH, self._h)
        self.window.set_default_size(_CARD_WIDTH, self._h)
        self.window.set_child(self._card)
        # Solo Escape cierra por teclado (antes: cualquier tecla).
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key)
        self.window.add_controller(controller)

    def _on_key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._close()
            return True
        return False

    def _resize_card(self, new_h):
        """Alto nuevo (expandir/contraer o hover): redimensiona la ventana."""
        if not self.window or not self._card:
            return
        self._h = new_h
        self._card.set_size_request(_CARD_WIDTH, new_h)
        self.window.set_default_size(_CARD_WIDTH, new_h)
        self.window.queue_resize()
        self._posicionar()

    def _tick(self):
        if self._closed or self.duration <= 0:
            return False
        # Hover = pausa del vencimiento (spec `toast-franja-descarte`), igual
        # que el tick Wayland: el crédito congela el wipe tick a tick.
        if self._card and self._card._hover:
            self._hover_credit_ms = min(
                self._hover_credit_ms + 50, self.duration)
        # monotonic: NTP/suspend no congela ni acelera el timer (auditoría #14)
        elapsed = ((time.monotonic() - self._start) * 1000
                   - self._hover_credit_ms)
        remaining = max(0, self.duration - elapsed)
        self._card.set_fraction(remaining / self.duration)
        if remaining <= 0:
            self._close()
            return False
        return True

    def _posicionar(self):
        """Ancla la esquina pedida y pide keep-above vía EWMH (spec entrada-fallback)."""
        try:
            surface = self.window.get_surface()
            xid = GdkX11.X11Surface.get_xid(surface)
            display = _X.XOpenDisplay(None)
            if not display:
                return
            mon = (Gdk.Display.get_default().get_monitors().get_item(0)
                   if Gdk.Display.get_default() else None)
            g = mon.get_geometry() if mon else None
            sw = g.width if g else 1920
            sh = g.height if g else 1080
            x = sw - _CARD_WIDTH - self.margin if "right" in self.corner \
                else self.margin
            y = sh - self._h - self.margin if "bottom" in self.corner \
                else self.margin
            _X.XMoveWindow(display, xid, x, y)
            state = _X.XInternAtom(display, b"_NET_WM_STATE", False)
            above = _X.XInternAtom(display, b"_NET_WM_STATE_ABOVE", False)
            atoms = (ctypes.c_ulong * 1)(above)
            _X.XChangeProperty(display, xid, state, _XA_ATOM, 32,
                               _PROP_REPLACE, atoms, 1)
            _X.XFlush(display)
            _X.XCloseDisplay(display)
        except Exception:
            pass  # fallback estético: sin Xlib el WM decide (no tumbamos el toast)

    def _close(self, *a):
        if self._closed:
            return
        self._closed = True
        if self.window:
            self.window.destroy()   # "destroy" → MainLoop.quit()
            self.window = None

    def show(self):
        # Sin display, crear la ventana aborta con core: mejor aviso por
        # stderr + exit 1 (spec `entrada-fallback`, "Forzar fallback en
        # headless"). En GTK4 init_check() inicializa Gtk y abre el display X11
        # (sin esto get_default() da None aunque DISPLAY esté definido).
        Gtk.init_check()
        if Gdk.Display.get_default() is None:
            print(f"[{APP_ID}] sin display de GTK: no hay display para el "
                  "fallback X11", file=sys.stderr)
            sys.exit(1)
        self._loop = GLib.MainLoop()
        self._build_ui()
        self.window.present()   # show() no mapea en GTK4: present() sí crea la GdkSurface/XID
        self._posicionar()
        self._start = time.monotonic()
        if self.duration > 0:
            GLib.timeout_add(50, self._tick)
        self._loop.run()
