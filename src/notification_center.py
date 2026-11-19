"""Centro de notificaciones: vista con las tarjetas del historial.

Reemplaza lo que hacía el applet de la bandeja de Plasma, que solo puede listar
el modelo de SU daemon (`NotificationManager.Server`): mientras Verdantis es
dueño de `org.freedesktop.Notifications`, ese servidor es inválido y el applet
muestra "no disponible". Acá la data es la nuestra (`history.jsonl`).

Este módulo expone:
- `card_fields(record, now)`: el registro crudo → textos de la tarjeta.
- `menu_items()`: items del menú de la bandeja (ids estables para DBusMenu).
- `CenterWindow`: la ventana GTK4 con la lista, de solo lectura (import
  perezoso de gi).
"""
import time

_BODY_MAX = 200

# (action, label) — el orden es el del menú y el índice + 1 es el id DBusMenu.
_MENU = (
    ("open", "Abrir historial"),
    ("clear", "Limpiar historial"),
)


def _relativo(ts, now):
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return ""
    delta = max(0, int(now) - ts)
    if delta < 60:
        return "ahora"
    if delta < 3600:
        return "hace %d min" % (delta // 60)
    if delta < 86400:
        return "hace %d h" % (delta // 3600)
    if delta < 86400 * 7:
        dias = delta // 86400
        return "ayer" if dias == 1 else "hace %d días" % dias
    return time.strftime("%d/%m/%Y", time.localtime(ts))


def card_fields(record, now=None):
    """Registro del historial → textos de una tarjeta del centro."""
    if now is None:
        now = time.time()
    record = record or {}
    body = record.get("body") or ""
    try:
        from wayland_popup import _strip_urls
        body = _strip_urls(body)
    except Exception:
        pass
    body = " ".join(body.split())[:_BODY_MAX]
    app = (record.get("app_name") or "").strip() or "?"
    title = (record.get("summary") or "").strip() or app
    return {
        "app": app,
        "title": title,
        "body": body,
        "when": _relativo(record.get("timestamp"), now),
        "url": record.get("url") or "",
        "id": record.get("id"),
    }


def menu_items():
    """Items del menú de la bandeja, con ids estables (1..N)."""
    return [
        {"id": i + 1, "label": label, "action": action}
        for i, (action, label) in enumerate(_MENU)
    ]


def _records_recientes(limit):
    try:
        import history_store
        return list(reversed(history_store.read()))[:limit]
    except Exception:
        return []


def _css():
    """CSS del centro: mismo lenguaje de card que el toast, foco con acento."""
    from app_info import DEFAULT_ACCENT
    from wayland_popup import _CARD_BG_HEX, _CARD_RADIUS
    return (
        ".center-list row { background: %s; border-radius: %dpx;"
        " margin: 6px 10px; }"
        ".center-list row:hover { background: shade(%s, 1.12); }"
        ".center-window { background: #14151c; }"
        ".center-title { font-weight: 700; font-size: 15px; }"
        # El anillo de foco por defecto es el azul de Adwaita: fuera del
        # acento de identidad. El foco se conserva (accesibilidad).
        "button:focus { outline: 2px solid %s; outline-offset: -2px; }"
        % (_CARD_BG_HEX, _CARD_RADIUS, _CARD_BG_HEX, DEFAULT_ACCENT))


class CenterWindow:
    """Ventana con la lista de las últimas notificaciones archivadas.

    Se crea bajo demanda (al activar el ícono de la bandeja) y se oculta al
    cerrarla: el daemon vive sin ventanas visibles.
    """

    def __init__(self, limit=50):
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, Gdk
        self._Gtk = Gtk
        self._limit = limit
        # Mismo lenguaje de card que el toast (radio + fondo), sin heredar el
        # render GSK: acá las filas son widgets GTK con hover propio.
        css = Gtk.CssProvider()
        css.load_from_string(_css())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._win = Gtk.Window(title="Notificaciones")
        self._win.add_css_class("center-window")
        self._win.set_default_size(420, 620)
        self._win.set_resizable(True)
        self._win.connect("close-request", self._on_close)
        esc = Gtk.EventControllerKey.new()
        esc.connect("key-pressed", self._on_key)
        self._win.add_controller(esc)

        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cab.set_margin_top(10)
        cab.set_margin_bottom(6)
        cab.set_margin_start(14)
        cab.set_margin_end(8)
        titulo = Gtk.Label(label="Notificaciones")
        titulo.set_xalign(0)
        titulo.add_css_class("center-title")
        cab.append(titulo)
        self._conteo = Gtk.Label(label="")
        self._conteo.set_xalign(0)
        self._conteo.add_css_class("dim-label")
        self._conteo.set_hexpand(True)
        cab.append(self._conteo)
        limpiar = Gtk.Button(label="Limpiar")
        limpiar.connect("clicked", self._on_clear)
        cab.append(limpiar)
        caja.append(cab)

        self._lista = Gtk.ListBox()
        self._lista.set_selection_mode(Gtk.SelectionMode.NONE)
        self._lista.add_css_class("center-list")
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self._lista)
        caja.append(scroll)
        self._win.set_child(caja)
        self.refresh()

    # ── construcción de la lista ─────────────────────────────────────────

    def refresh(self):
        Gtk = self._Gtk
        while True:
            fila = self._lista.get_row_at_index(0)
            if fila is None:
                break
            self._lista.remove(fila)
        records = _records_recientes(self._limit)
        for rec in records:
            self._lista.append(self._fila(card_fields(rec), rec))
        self._conteo.set_text(
            "sin notificaciones" if not records
            else "%d notificaciones" % len(records))

    def _fila(self, campos, rec):
        Gtk = self._Gtk
        fila = Gtk.ListBoxRow()
        fila.record = rec
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for lado in ("top", "bottom", "start", "end"):
            getattr(caja, "set_margin_" + lado)(10 if lado in ("start", "end") else 8)
        cab = Gtk.Label(label="%s · %s" % (campos["app"], campos["when"]))
        cab.set_xalign(0)
        cab.add_css_class("dim-label")
        cab.add_css_class("caption")
        caja.append(cab)
        titulo = Gtk.Label(label=campos["title"])
        titulo.set_xalign(0)
        titulo.set_ellipsize(3)
        titulo.add_css_class("heading")
        caja.append(titulo)
        if campos["body"]:
            cuerpo = Gtk.Label(label=campos["body"])
            cuerpo.set_xalign(0)
            cuerpo.set_wrap(True)
            cuerpo.set_lines(3)
            cuerpo.set_ellipsize(3)
            caja.append(cuerpo)
        fila.set_child(caja)
        return fila

    # ── eventos ──────────────────────────────────────────────────────────

    def _on_clear(self, _btn):
        try:
            import history_store
            history_store.clear()
        except Exception:
            pass
        self.refresh()

    def _on_key(self, _ctrl, keyval, _code, _state):
        if keyval == 0xFF1B:      # Escape
            self.hide()
            return True
        return False

    def _on_close(self, *_a):
        self._win.set_visible(False)
        return True               # no destruir: el daemon sigue vivo

    def show(self):
        self.refresh()
        self._win.present()

    def hide(self):
        self._win.set_visible(False)
