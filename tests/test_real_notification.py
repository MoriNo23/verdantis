"""
Test de EJEMPLO que reproduce una NOTIFICACIÓN REAL end-to-end en Verdantis.

Flujo real (igual al daemon en producción):

  DBus (gdbus/notify-send)
    -> NotificationManager.notify(app_name, summary, body, actions, hints, timeout)
    -> construye WaylandPopup con los kwargs REALES (urgency, url, banner, accent)
    -> renderiza el body con wrap/ellipsis + botón expandir si desborda

Este test ejercita ese camino completo (manager -> popup -> widget), con un
payload realista como el que envía una app (Firefox con body largo + hyperlink
+ urgency normal), SIN display: el popup se construye, el widget se dibuja
headless, y se verifican las propiedades que el ojo vería.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "offscreen")
# Sin WAYLAND_DISPLAY: WaylandPopup.prepare() hace return temprano (no crashea)

sys.path.insert(0, "/home/extra/repositorios/verdantis/src")

import wayland_popup as wp
from verdantis_daemon import NotificationManager

# Payload realista como lo mandaría una app por el bus DBus (spec freedesktop 1.2)
REAL_BODY = (
    "Your download of <b>verdantis-0.1.0.tar.gz</b> has finished. "
    "Click <a href=\"https://github.com/MoriNo23/verdantis\">here</a> to open "
    "the release page. Este texto es lo bastante largo como para envolver "
    "dentro del ancho de la tarjeta y desbordar las tres líneas visibles, "
    "por lo que debe aparecer el botón Ver más para expandir el toast y "
    "poder leer el mensaje completo sin que se corte contra el borde."
)

REAL_HINTS = {
    "urgency": 1,                              # BYTE 1 = normal
    "x-kde-urls": ["https://github.com/MoriNo23/verdantis"],  # click abre URL
    "desktop-entry": "firefox",
    "accent": "#89b4fa",
}


def _render_widget(cuerpo, expanded):
    """Dibuja el NotificationWidget headless y devuelve (widget, altura)."""
    import cairo
    from gi.repository import Gdk
    w = wp.NotificationWidget("Firefox", "", "Descarga completada", cuerpo,
                              None, None, "#89b4fa")
    w._expanded = expanded
    h = w.desired_height()
    a = Gdk.Rectangle()
    a.x, a.y, a.width, a.height = 0, 0, 360, h
    w.get_allocation = lambda a=a: a
    w._draw(w, cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, h)))
    return w, h


def test_real_notification_manager_builds_popup():
    """El manager (vía daemon) construye el popup con los kwargs REALES.

    Reproduce el camino completo del daemon: notify() con hints reales debe
    crear la notificación, extraer la URL del hyperlink/click, aplicar la
    urgency y construir el WaylandPopup sin crash (headless).

    Nota: tras el refactor de batching (commit t_c93ad5ab) notify() encola en
    _pending y el popup se construye al drenar el pump. Usamos un scheduler
    no-op y disparamos el pump a mano; el popup se construye headless (sin
    ventana GTK) pero con los kwargs reales del daemon."""
    mgr = NotificationManager(corner="top-right")
    mgr._scheduler = lambda ms, cb: 0  # no auto-dispara; llamamos _pump() abajo

    def headless_show(nid, kwargs):
        # Popup REAL con los kwargs del daemon, pero sin abrir ventana GTK
        # (prepare()/set_stack_margin() requieren WAYLAND_DISPLAY).
        popup = wp.WaylandPopup(**kwargs)
        mgr._active.append((nid, popup))

    mgr._show_popup = headless_show
    nid = mgr.notify(
        app_name="Firefox",
        app_icon="",
        summary="Descarga completada",
        body=REAL_BODY,
        actions=["default", "Abrir"],
        hints=dict(REAL_HINTS),
        expire_timeout=10000,
    )
    mgr._pump()  # drena la cola -> _active poblado
    # La notificación se registró con los datos parseados
    info = mgr._notifications[nid]
    assert info["app_name"] == "Firefox"
    assert info["desktop_entry"] == "firefox"
    assert info["urgency"] == 1
    # La URL del hint x-kde-urls se extrajo (click -> abre la página)
    assert "github.com/MoriNo23/verdantis" in info["url"]
    # El popup real entró en la lista de activos (con el widget construido)
    assert len(mgr._active) == 1
    popup = mgr._active[0][1]
    assert popup.titulo == "Descarga completada"
    assert popup.cuerpo == REAL_BODY
    assert popup.urgency == 1
    assert popup.accent == "#89b4fa"
    assert popup.duration == 10000


def test_real_notification_renders_and_expands():
    """La noti real (body largo + markup) renderiza y tiene botón expandir.

    Colapsada: 3 líneas + "..." (el wrap no deja que el texto se salga por el
    borde). Expandida: muestra todo y el botón queda para volver a contraer."""
    # Colapsada: el texto envuelve a >3 líneas visuales -> hay overflow
    total = wp._count_body_lines(REAL_BODY, wp._TEXT_COL_W, 14)
    assert total > wp.NotificationWidget._MAX_VISIBLE_LINES, f"wrap={total}"

    w_c, h_c = _render_widget(REAL_BODY, expanded=False)
    w_e, h_e = _render_widget(REAL_BODY, expanded=True)

    # El botón aparece colapsado y persiste expandido (para poder contraer)
    assert w_c._expand_rect is not None, "body largo debe mostrar 'Ver más'"
    assert w_e._expand_rect is not None, "expandido debe mantener 'Ver menos'"
    # Expandido es más alto -> la card crece para leer cómodo
    assert h_e > h_c, f"c={h_c} e={h_e}"
    # El botón no se solapa con el título (está debajo del bloque de texto)
    assert float(w_c._expand_rect[1]) >= 55.0, f"top={w_c._expand_rect[1]}"
    # Y cabe dentro de la card
    assert float(w_e._expand_rect[3]) <= h_e + 0.01


def test_real_notification_markup_body_render_no_crash():
    """El body con <b> y <a href> (body-markup/hyperlinks) se dibuja sin crash
    y Pango lo acepta (mismo camino que en producción)."""
    # El widget acepta el markup (lo dibuja con set_markup dentro de _draw_text)
    w, _ = _render_widget(REAL_BODY, expanded=False)
    assert w._cuerpo == REAL_BODY
    # Y la URL del hyperlink del body se extrae (click abriría la página)
    assert wp._extract_markup_url(REAL_BODY) == "https://github.com/MoriNo23/verdantis"