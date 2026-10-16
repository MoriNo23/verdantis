"""Fallback X11 (GTK, sin layer-shell) para la notificación one-shot de verdantis.

Se carga SOLO en el branch X11 (import perezoso desde `verdantis.main`): el
daemon y el path Wayland no pagan este import. Un solo toolkit en el
proyecto — GTK3, reutilizando el render cairo/Pango de `NotificationWidget`;
Qt quedó fuera por completo.

El posicionamiento es de verdad: `Gtk.Window.move()` contra el workarea del
monitor (`Gdk.Monitor.get_workarea()`, respeta paneles) + keep-above + type
hint NOTIFICATION. Riesgo documentado: en un X11 sin compositing manager el
fondo puede salir negro en vez de RGBA (los X11 modernos lo traen); la
ventana pide visual RGBA si existe.
"""
import os
# GDK_BACKEND=x11 ANTES de que cualquiera toque Gdk — convención de
# `wayland_popup` (que hace setdefault a 'wayland' y por eso no lo pisa):
# sin esto, `--force-fallback` dentro de una sesión Wayland elegiría backend
# wayland y `move()` sería ignorado.
os.environ.setdefault('GDK_BACKEND', 'x11')

import sys
import time

# `wayland_popup` PRIMERO: fija Gtk/Gdk 3.0 (pitfall de imports gi) y aporta
# el render — la ventana de acá es solo el contenedor.
from wayland_popup import NotificationWidget, _CARD_WIDTH
from app_info import APP_ID, DEFAULT_ACCENT
from gi.repository import Gtk, GLib, Gdk


def posicion_esquina(corner, workarea, margin, size):
    """(esquina, workarea, margen, tamaño) → (x, y). Cálculo puro, sin display.

    `workarea` es la tupla (x, y, w, h) de `Gdk.Monitor.get_workarea()`: su
    origen ya descuenta paneles, así que la esquina queda anclada dentro del
    área disponible y no debajo del panel."""
    wx, wy, ww, wh = workarea
    w, h = size
    x = wx + ww - w - margin if "right" in corner else wx + margin
    y = wy + wh - h - margin if "bottom" in corner else wy + margin
    return x, y


class NotificacionX11:
    """Toast one-shot en `Gtk.Window` común (fallback X11, sin layer-shell).

    Misma superficie de parámetros que el viejo fallback Qt: la rejija del
    one-shot es un simple cambio de módulo. La ventana se construye recién en
    `show()` (necesita display); la posición sale del cálculo puro
    `posicion_esquina`. Sin display, GTK emite su propio error y sale ≠ 0."""

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
        self._hover_credit_ms = 0   # ms de hover: el crédito que pausa el wipe
        self._closed = False

    def _build_ui(self):
        self.window = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.window.set_decorated(False)
        self.window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_keep_above(True)
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

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
        self.window.set_size_request(_CARD_WIDTH, self._h)
        self.window.add(self._card)
        self.window.connect("destroy", lambda *a: Gtk.main_quit())
        # Solo Escape cierra por teclado (antes: cualquier tecla).
        self.window.connect(
            "key-press-event",
            lambda w, e: self._close()
            if e.keyval == Gdk.KEY_Escape else False)

    def _posicionar(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display else None
        if monitor is None or not self.window:
            return
        wa = monitor.get_workarea()
        x, y = posicion_esquina(
            self.corner, (wa.x, wa.y, wa.width, wa.height),
            self.margin, (_CARD_WIDTH, self._h))
        self.window.move(x, y)

    def _resize_card(self, new_h):
        """Alto nuevo (expandir/contraer o hover): redimensiona y re-ancla."""
        if not self.window or not self._card:
            return
        self._h = new_h
        self._card.set_size_request(_CARD_WIDTH, new_h)
        self.window.set_size_request(_CARD_WIDTH, new_h)
        self.window.queue_resize()
        self.window.show_all()
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

    def _close(self, *a):
        if self._closed:
            return
        self._closed = True
        if self.window:
            self.window.destroy()   # "destroy" → Gtk.main_quit()
            self.window = None

    def show(self):
        # Sin display, crear la ventana aborta con core (Gtk-ERROR de style
        # context): mejor aviso por stderr + exit 1 (spec `entrada-fallback`,
        # "Forzar fallback en headless").
        if not Gtk.init_check()[0]:
            print(f"[{APP_ID}] sin display de GTK: no hay display para el "
                  "fallback X11", file=sys.stderr)
            sys.exit(1)
        self._build_ui()
        self.window.show_all()
        self._posicionar()
        self._start = time.monotonic()
        if self.duration > 0:
            GLib.timeout_add(50, self._tick)
        Gtk.main()
