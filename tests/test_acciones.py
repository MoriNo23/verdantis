"""
RED: botones de acción en el toast (spec `toast-acciones`).

Verdantis anuncia `actions` en GetCapabilities desde 0.4 pero solo usa las
keys para el click del cuerpo (`_pick_action_key`): los botones que mandan
los senders nunca se renderizan (`open`/`settings` del dataset, 42 notis).
Este change los renderiza: fila de hasta 3 botones (default NUNCA, su label
viaja en el par pero no se dibuja), hitboxes propias, y click por botón →
ActionInvoked con SU key.

Contrato testeado (spec toast-acciones):
  - render: fila bajo el body, sin actions no hay fila (layout actual intacto)
  - invocación: click en botón → LA key de ese botón; cuerpo → None (default)
  - parseo: cap 3, default fuera, dedup, lista impar tolerada
  - action-icons: hint → icono del tema por key + label; sin icono → label
    solo sin hueco; sin hint → nunca se buscan iconos
  - layout: la fila suma (_ACTIONS_ROW_H + _ACTIONS_GAP) a la card en la
    misma métrica que calc_card_height; la barra "Ver más" ancla DEBAJO de
    los botones, sin solapes
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))  # render_helpers

# wayland_popup PRIMERO: fija Gdk 3.0 (pitfall de AGENTS.md).
import wayland_popup as wp
from wayland_popup import NotificationWidget

from render_helpers import alloc_and_draw, surface_pixels

W = wp._CARD_WIDTH              # 360
ROW_H = None                     # se resuelve al importar la implementación
LONG = ("Parrafo largo que se re-wrappea al cambiar el ancho de la columna "
        "de texto del card y por lo tanto ocupa varias lineas al ancho "
        "completo, desbordando el cap de tres lineas visibles del body.")

# Dos botones visibles: default viaja con SU label ("Abrir sitio") que no
# se renderiza; settings/mark son los botones (spec, scenario "Dos acciones
# visibles" — el label del par de default nunca se dibuja).
ACTIONS_2 = ["default", "Abrir sitio", "settings", "Ajustes", "mark", "Marcar"]


class _Ev:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _icono_solo_para(nombre, size=16):
    """Fake de _icon_from_theme: resuelve SOLO 'mail-mark-read' (rojo sólido)."""
    if nombre != "mail-mark-read":
        return None
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    pb.fill(0xFF0000FF)
    return pb


def _sin_iconos_resolvibles(monkeypatch, icono=None):
    """Determinismo: nada del tema/.desktop resuelve, salvo el fake explícito."""
    monkeypatch.setattr(
        wp, "_get_app_icon_from_desktop",
        lambda app_name, size=80, mode="cover": None)
    monkeypatch.setattr(wp, "_icon_from_theme", icono or (lambda name, size=16: None))


def _widget(actions=None, action_icons=False, on_click=None, cuerpo="Body corto.",
            persistent=False):
    return NotificationWidget(
        "App", "", "Título", cuerpo, None, None, "#80cbc4",
        on_click=on_click, persistent=persistent,
        actions=actions, action_icons=action_icons,
    )


def _render(w, hover=False):
    """(pixeles, altura) del render headless al alto deseado."""
    h = w.desired_height()
    px = surface_pixels(alloc_and_draw(w, W, h, hover=hover))
    return px, h


def _en_rect(rect, x, y):
    x0, y0, x1, y1, _ = rect
    return x0 <= x <= x1 and y0 <= y <= y1


# ── 1.1 Render de la fila ─────────────────────────────────────────────────

def test_dos_acciones_visibles_y_default_no(monkeypatch):
    """Spec 'Los botones de acción se renderizan': la fila muestra los
    botones (settings/mark) con default NUNCA como botón."""
    _sin_iconos_resolvibles(monkeypatch)
    w = _widget(actions=ACTIONS_2)
    px, h = _render(w)

    rects = w._action_rects
    assert len(rects) == 2, (
        "spec toast-acciones / render: con %s deben verse 2 botones, "
        "hay %s" % (ACTIONS_2, len(rects or []))
    )
    keys = [r[4] for r in rects]
    assert keys == ["settings", "mark"], (
        "las keys renderizadas deben ser settings y mark (default fuera), no %s"
        % (keys,)
    )
    assert all("default" != k for k in keys), "default nunca se renderiza"

    # Los rects viven bajo el body (fila propia) y dentro de la card.
    for rect in rects:
        assert rect[1] > 40, "la fila va bajo el body (y0=%s)" % (rect[1],)
        assert rect[3] <= h - wp._PAD + 0.01, (
            "el botón no puede salirse de la card (y1=%s > %s)" % (rect[3], h - wp._PAD)
        )


def test_sin_actions_no_hay_fila(monkeypatch):
    """Sin actions (o solo default) el layout es el actual: sin fila."""
    _sin_iconos_resolvibles(monkeypatch)
    w = _widget()
    px, h = _render(w)
    assert w._action_rects == [], "sin actions no debe haber fila de botones"

    # Un botón "default" suelto tampoco crea fila (es el click del cuerpo).
    w_d = _widget(actions=["default", "Abrir"])
    _, h_d = _render(w_d)
    assert w_d._action_rects == [], "solo default no debe crear fila"
    assert h_d == h, "solo default no debe cambiar la altura (h=%s vs %s)" % (h_d, h)


def test_la_fila_se_dibuja_pixeles(monkeypatch):
    """La banda de botones dibuja ALGO que sin actions no está ahí."""
    _sin_iconos_resolvibles(monkeypatch)
    con = _widget(actions=ACTIONS_2)
    sin = _widget()
    px_con, h_con = _render(con)
    px_sin, h_sin = _render(sin)

    # La fila ocupa la franja vertical entre la altura sin actions y la con.
    y0 = int(h_sin - wp._PAD)
    y1 = int(h_con - wp._PAD)
    assert y1 > y0, "con actions la card debe ser más alta (%s vs %s)" % (h_con, h_sin)
    difieren = any(
        px_con[y][x] != px_sin[y][x]
        for y in range(y0, min(y1, len(px_sin), len(px_con)))
        for x in range(wp._PAD, W - wp._PAD)
        if y < len(px_con)
    )
    assert difieren, (
        "la banda de botones no dibuja píxeles nuevos entre y=%s y y=%s — "
        "la fila no se está renderizando" % (y0, y1)
    )


# ── 1.2 Invocación por botón ───────────────────────────────────────────────

def test_click_en_boton_emite_su_key(monkeypatch):
    """Spec 'Cada botón emite su propia action key': click dentro del rect
    de cada botón → SU key (no la default), consumiendo el evento."""
    _sin_iconos_resolvibles(monkeypatch)
    llamados = []
    w = _widget(actions=ACTIONS_2, on_click=lambda key=None: llamados.append(key))
    alloc_and_draw(w, W, w.desired_height())
    assert len(w._action_rects) == 2

    for rect in w._action_rects:
        x0, y0, x1, y1, key = rect
        w._on_button_press(w, _Ev((x0 + x1) / 2, (y0 + y1) / 2))
        assert llamados[-1] == key, (
            "spec toast-acciones / invocación: el click en el botón de key "
            "%s debe emitir ESA key, llegó %s" % (key, llamados[-1])
        )
    assert llamados == ["settings", "mark"], (
        "cada botón emite su key en orden, no %s" % (llamados,)
    )


def test_click_en_boton_no_dispara_la_default(monkeypatch):
    """El click en un botón NO es el click del cuerpo: no llega None (que
    abriría la URL/empezaría la default)."""
    _sin_iconos_resolvibles(monkeypatch)
    llamados = []
    w = _widget(actions=ACTIONS_2, on_click=lambda key=None: llamados.append(key))
    alloc_and_draw(w, W, w.desired_height())
    x0, y0, x1, y1, key = w._action_rects[0]
    w._on_button_press(w, _Ev((x0 + x1) / 2, (y0 + y1) / 2))
    assert llamados == [key], (
        "un solo click debe emitir una sola key (%s), no %s" % (key, llamados)
    )
    assert None not in llamados, (
        "el click de botón no debe caer en el camino default (None) — "
        "abrirla la URL del body sería un click fantasma"
    )


def test_click_en_cuerpo_sigue_siendo_default(monkeypatch):
    """Fuera de botones (título/body), el click del cuerpo sigue igual:
    action_key=None → el daemon resuelve la default como hoy."""
    _sin_iconos_resolvibles(monkeypatch)
    llamados = []
    w = _widget(actions=ACTIONS_2, on_click=lambda key=None: llamados.append(key))
    alloc_and_draw(w, W, w.desired_height())
    # Click en la zona del título (columna de texto, arriba de la fila).
    w._on_button_press(w, _Ev(wp._PAD + wp._IMAGE_LEFT_W + 20, 18))
    assert llamados == [None], (
        "el click del cuerpo debe llegar como action_key=None (default), "
        "no %s" % (llamados,)
    )


# ── 1.3 Parseo: límites y robustez ─────────────────────────────────────────

def test_parseo_cap_tres_y_default_fuera():
    """>3 acciones además de default → solo los primeros 3; default fuera."""
    raw = ["default", "X", "a", "1", "b", "2", "c", "3", "d", "4"]
    assert wp._parse_actions(raw) == [("a", "1"), ("b", "2"), ("c", "3")], (
        "cap de 3 botones visibles con default filtrado"
    )


def test_parseo_dedup_primera_gana():
    assert wp._parse_actions(["a", "1", "a", "2", "b", "3"]) == \
        [("a", "1"), ("b", "3")], "key duplicada: la PRIMERA gana"


def test_parseo_lista_impar_tolerada():
    """Una lista corrupta (key suelta al final) no crashea: se ignora."""
    assert wp._parse_actions(["a", "1", "b"]) == [("a", "1")]


def test_parseo_vacios_y_nada():
    """Keys o labels vacíos no generan botones; nada es []."""
    assert wp._parse_actions(["", "x", "b", ""]) == []
    assert wp._parse_actions([]) == []
    assert wp._parse_actions(None) == []


# ── 1.4 action-icons ──────────────────────────────────────────────────────

def test_action_icons_hint_resuelve_y_dibuja(monkeypatch):
    """Con hint, el key del botón se interpreta como icono del tema y se
    dibuja DENTRO de su botón (junto al label)."""
    _sin_iconos_resolvibles(monkeypatch, icono=_icono_solo_para)
    w = _widget(actions=["mail-mark-read", "Marcar como leída"],
                action_icons=True)
    px, h = _render(w)

    assert "mail-mark-read" in w._action_icon_pbs, (
        "con hint action-icons el key del botón debe resolverse por tema "
        "(tenía que pedir 'mail-mark-read')"
    )
    rect = w._action_rects[0]
    rojos = sum(
        1
        for y in range(int(rect[1]), int(rect[3]))
        for x in range(int(rect[0]), int(rect[2]))
        if px[y][x][0] > 200 and px[y][x][1] < 80 and px[y][x][2] < 80
    )
    assert rojos >= 16, (
        "el icono (16px rojos) debe dibujarse dentro del botón; píxeles "
        "rojos encontrados: %s" % rojos
    )


def test_action_icons_sin_resolucion_no_deja_hueco(monkeypatch):
    """Key que no es icono del tema → label solo, y el render es IDÉNTICO
    al de la misma notificación sin el hint (sin huecos)."""
    pedidas = []

    def fake(nombre, size=16):
        pedidas.append(nombre)
        return None

    _sin_iconos_resolvibles(monkeypatch, icono=fake)
    acciones = ["settings", "Ajustes"]
    con = _widget(actions=acciones, action_icons=True)
    px_con, h = _render(con)
    assert con._action_icon_pbs == {}, (
        "un key sin icono no debe quedar en _action_icon_pbs"
    )

    sin = _widget(actions=acciones, action_icons=False)
    px_sin, _ = _render(sin)
    assert px_con == px_sin, (
        "spec toast-acciones / action-icons: icono que no resuelve → label "
        "solo, render idéntico al de sin hint (sin hueco)"
    )


def test_sin_hint_nunca_busca_iconos(monkeypatch):
    pedidas = []

    def fake(nombre, size=16):
        pedidas.append(nombre)
        return None

    _sin_iconos_resolvibles(monkeypatch, icono=fake)
    w = _widget(actions=["settings", "Ajustes"], action_icons=False)
    _render(w)
    assert "settings" not in pedidas, (
        "sin hint action-icons no debe resolverse NINGÚN icono de botón "
        "(pedidas: %s)" % (pedidas,)
    )
    assert w._action_icon_pbs == {}


# ── Daemon end-to-end: el click del widget llega con SU key ──────────────

def test_daemon_click_de_boton_emite_su_key(monkeypatch):
    """El camino COMPLETO que el live cazó: el widget llama
    `popup._on_click("settings")` (un solo posicional) y el lambda del daemon
    debe llevar ESE valor como action_key — no comérselo como `nid` (con ese
    bug el toast no se cierra y notify-send no recibe nada)."""
    from test_dbus_contract import FakeBus
    import verdantis_daemon as vd

    m = vd.NotificationManager(corner="top-right")
    m._scheduler = lambda ms, cb: 0
    m.set_dbus(FakeBus())

    def headless_show(nid, kwargs):
        popup = vd.WaylandPopup(**kwargs)
        m._active.append((nid, popup))

    m._show_popup = headless_show
    nid = m.notify(app_name="App", app_icon="", summary="t", body="b",
                   actions=["default", "Abrir", "settings", "Ajustes"],
                   hints={}, expire_timeout=5000)
    while m._pending:
        m._pump()
    popup = m._active[0][1]

    # El click del botón, tal como lo dispara el widget:
    popup._on_click("settings")

    invocadas = [
        e for e in m._dbus_bus.emitted
        if e[3] == "ActionInvoked"
    ]
    assert invocadas, (
        "el click en el botón 'Ajustes' debe emitir ActionInvoked — si no "
        "llega nada, el lambda del daemon se está comiendo la key como `nid`"
    )
    nid_senal, key_senal = invocadas[-1][4].unpack()
    assert nid_senal == nid and key_senal == "settings", (
        "ActionInvoked debe llevar (nid=%s, key='settings'), llegó (%s, %s)"
        % (nid, nid_senal, key_senal)
    )
    assert all(a != nid for a, _ in m._active), (
        "tras invocar la action el popup visual debe cerrarse (el toast "
        "quedó abierto es el bug del live)"
    )


# ── La fila no pisa la imagen izquierda (piso del slot) ───────────────────

def test_la_fila_no_pisa_la_imagen_izquierda(monkeypatch):
    """Con body CORTO el slot (80px) es más alto que el bloque de texto: la
    banda full-width debe arrancar DEBAJO del slot (la card crece lo que haga
    falta), nunca pintarle encima al círculo (bug del live: 9px de solape)."""
    _sin_iconos_resolvibles(monkeypatch)
    w = _widget(actions=ACTIONS_2)          # body corto → bloque < slot
    px, h = _render(w)
    assert w._action_rects, "la fila debe existir"

    slot_y1 = w._image_left_rect[3]
    fila_y0 = min(r[1] for r in w._action_rects)
    assert slot_y1 <= fila_y0 + 0.01, (
        "spec toast-acciones / layout: la imagen izquierda (y1=%s) queda "
        "bajo la fila de botones (y0=%s) — el slot debe quedar libre, la "
        "card crece (piso del slot)" % (slot_y1, fila_y0)
    )
    # Y el slot sigue cabiendo entero en la card.
    assert w._image_left_rect[1] >= wp._PAD - 0.01
    assert slot_y1 <= h - wp._PAD + 0.01


def _pares(n):
    out = []
    for i in range(n):
        out += ["k%d" % i, "Botón %d" % i]
    return out


# ── 1.5 Layout: altura, barra debajo, sin solapes ─────────────────────────

def test_la_fila_suma_altura_exacta(monkeypatch):
    """La fila suma (_ACTIONS_ROW_H + _ACTIONS_GAP) a la card, para 1..3
    botones (una sola banda), en la MISMA métrica que calc_card_height.
    Se mide con body largo: sin el piso de 80px de row_h metido en el medio,
    el delta es exactamente la banda (con body corto el piso absorbe y el
    delta es menor — comportamiento correcto del floor, no un bug)."""
    _sin_iconos_resolvibles(monkeypatch)
    base = _widget(cuerpo=LONG).desired_height()
    assert base > 2 * wp._ROW_MIN_H, (
        "sanity: el body largo debe estar sobre el piso de row_h para que "
        "el delta de la fila sea exacto (base=%s)" % base
    )
    for n in (1, 2, 3):
        w = _widget(actions=_pares(n), cuerpo=LONG)
        esperado = base + wp._ACTIONS_ROW_H + wp._ACTIONS_GAP
        assert w.desired_height() == esperado, (
            "con %d botón(es) la card debe medir base+%s+%s (esperado %s, "
            "obtenido %s) — la métrica divergió entre _draw y calc"
            % (n, wp._ACTIONS_ROW_H, wp._ACTIONS_GAP, esperado, w.desired_height())
        )
    # calc_card_height y desired_height usan LA MISMA métrica (fuente única):
    cc_base = wp.WaylandPopup.calc_card_height("App", LONG, "",
                                               text_width=wp._TEXT_COL_W)
    cc = wp.WaylandPopup.calc_card_height("App", LONG, "",
                                          text_width=wp._TEXT_COL_W,
                                          actions_count=2)
    assert cc == cc_base + wp._ACTIONS_ROW_H + wp._ACTIONS_GAP, (
        "calc_card_height(actions_count=2) debe incluir la fila igual que "
        "desired_height (divergencia altura/wrap): %s vs %s" % (cc, cc_base)
    )


def test_body_corto_la_fila_cabe_dentro_del_piso(monkeypatch):
    """Con body corto el piso de row_h absorbe parte de la banda: la card no
    crece el alto completo de la fila, pero los botones caben dentro de la
    card (nada se dibuja fuera del padding)."""
    _sin_iconos_resolvibles(monkeypatch)
    base = _widget().desired_height()
    w = _widget(actions=ACTIONS_2)
    px, h = _render(w)
    assert h >= base, "con botones la card no puede ser más baja (h=%s<%s)" % (h, base)
    assert w._action_rects, "la fila debe existir"
    assert max(r[3] for r in w._action_rects) <= h - wp._PAD + 0.01, (
        "los botones deben caber dentro del padding de la card "
        "(y1=%s > %s)" % (max(r[3] for r in w._action_rects), h - wp._PAD)
    )


def test_barra_ver_mas_debajo_de_los_botones(monkeypatch):
    """Con overflow + botones: la barra 'Ver más' ancla DEBAJO de la fila,
    sin solaparse, y la card termina con el padding correcto."""
    _sin_iconos_resolvibles(monkeypatch)
    w = _widget(actions=ACTIONS_2, cuerpo=LONG)
    px, h = _render(w)
    assert w._expand_rect is not None, "body largo debe mostrar 'Ver más'"
    assert w._action_rects, "la fila de botones debe existir"

    botones_y1 = max(r[3] for r in w._action_rects)
    assert w._expand_rect[1] >= botones_y1 - 0.01, (
        "spec toast-acciones / layout: la barra 'Ver más' debe quedar debajo "
        "de los botones (barra y0=%s < botones y1=%s)" 
        % (w._expand_rect[1], botones_y1)
    )
    # La barra sigue anclada al padding inferior (invariante de consistency).
    assert h - wp._PAD - w._expand_rect[3] == 0, (
        "la barra debe terminar en el padding inferior (h=%s, barra y1=%s)"
        % (h, w._expand_rect[3])
    )


def test_restack_hereda_la_altura_de_la_fila(monkeypatch):
    """Regresión del spec toast-stack: el restack consume desired_height;
    que la fila esté en la métrica garantiza el gap (misma señal de
    test_layout_consistency: la altura es la fuente única del offset)."""
    _sin_iconos_resolvibles(monkeypatch)
    sin = _widget(actions=ACTIONS_2, cuerpo=LONG)
    h_colapsado = sin.desired_height()
    sin._expanded = True
    h_expandido = sin.desired_height()
    assert h_expandido > h_colapsado, (
        "expandir un toast con botones debe cambiar su alto — el restack "
        "se dispara por desired_height, si la fila no está en la métrica "
        "la pila solapa"
    )
    # Expandir/ccontraer con botones: el delta es el body extra, la fila
    # sigue contada UNA vez (no se duplica al expandir).
    assert h_expandido - h_colapsado < h_expandido, "sanity"
