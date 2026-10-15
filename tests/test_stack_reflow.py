"""
RED: la pila de toasts nunca solapa (spec `toast-stack` del change
layout-imagen-izquierda).

Un test por scenario del spec:

  - "Expandir con toasts debajo": al expandir con "Ver más", los toasts de abajo
    se reposicionan (offsets = suma de las alturas reales + 12 de gap).
  - "Contraer devuelve el espacio": al contraer vuelven a su posición.
  - "El re-wrap por hover también re-flowea": el cambio de alto por hover
    (franja de 44 px) reposiciona igual que cualquier otro cambio de alto.
  - "El reflow es estable": expandir/contraer repetido converge siempre al
    estado correcto, sin oscilaciones ni acumulación de error.
  - "Un toast que entra no tapa al que ya estaba": el hueco del que entra se
    reserva ANTES de mapear su superficie (el primer frame commiteado ya está
    en su offset, nunca sobre el de arriba).

CÓMO SE EJERCE SIN VENTANAS REALES: se deja correr el `_build_ui` REAL de
`WaylandPopup` (el que instala el `on_resize` del card y el `set_stack_margin`)
con `Gtk.Window.new` y las llamadas de GtkLayerShell parcheadas a una window
falsa que registra tamaños. Así:

  - el manager, el popup, el card, el resize y el cálculo de márgenes son 100%
    código real — lo único simulado es la superficie del compositor;
  - el `on_resize` que el manager inyecta es el que el card realmente invoca
    (no una reimplementación del test), así que el test no puede "ganar" por su
    cuenta;
  - no aparece ni un toast en el escritorio del usuario ni se depende de que
    haya display (los offsets se leen del registro de márgenes).

Hoy la suite está ROJA porque `set_stack_margin` solo se llama al mostrar y al
cerrar: el camino `on_resize` redimensiona la propia ventana y no mueve a los
demás.
"""
import os


# wayland_popup PRIMERO: fija Gdk 3.0 antes de que un import suelto de Gdk
# cargue 4.0 y crashee (pitfall documentado en AGENTS.md).
import pytest

import verdantis_daemon as vd
import wayland_popup as wp
from wayland_popup import NotificationWidget, WaylandPopup

GAP = 12                       # gap entre cards (spec toast-stack)
BASE_MARGIN = 16               # margen base del corner top-right
LONG = "Cuerpo largo " * 40    # desborda el cap de 3 líneas → barra "Ver más"
SHORT = "Corto."
TOP_EDGE = int(wp.GtkLayerShell.Edge.TOP)   # borde vertical del corner top-*'


# ── window falsa: registra todo lo que el layer-shell le pediría ───────────

class FakeWin:
    """Window layer-shell falsa: registra tamaños y no toca el compositor.

    `__getattr__` devuelve un no-op para cualquier llamada GTK que C agregue en
    el camino del resize: el test interesa por los MARGENES que fija
    `set_margin`, no por la API de Gtk.
    """

    def __init__(self):
        FakeWin._n = getattr(FakeWin, "_n", 0) + 1
        self.id = FakeWin._n
        self.size_request = None
        self.committed = 0
        self.shown = 0

    def __getattr__(self, nombre):
        def _noop(*a, **k):
            return None
        return _noop

    def set_size_request(self, w, h):
        self.size_request = (w, h)

    def queue_resize(self):
        pass

    def show_all(self):
        self.shown += 1

    def get_screen(self):
        class _Screen:
            @staticmethod
            def get_rgba_visual():
                return None
        return _Screen()


class Harness:
    """Manager real + popups reales (card real) + márgenes registrados."""

    def __init__(self, monkeypatch):
        self.llamadas = []           # (win_id, índice) por `set_stack_margin`
        self.margen_por_win = {}     # win_id -> último margen superior
        self._monkeypatch = monkeypatch

        monkeypatch.setattr(
            wp.Gtk, "Window",
            type("W", (), {"new": staticmethod(lambda *a: FakeWin())}))

        def _set_margin(win, edge, valor):
            if int(edge) == TOP_EDGE:
                self.margen_por_win[win.id] = int(valor)

        monkeypatch.setattr(wp.GtkLayerShell, "set_margin", _set_margin)
        for nombre in ("try_force_commit", "init_for_window", "set_layer",
                       "set_namespace", "set_anchor", "set_exclusive_zone"):
            monkeypatch.setattr(
                wp.GtkLayerShell, nombre, lambda *a: None)
        monkeypatch.setattr(wp.GtkLayerShell, "is_supported", lambda: True)
        monkeypatch.setattr(wp.GtkLayerShell, "is_layer_window", lambda w: True)
        # prepare() aborta sin WAYLAND_DISPLAY; el wiring se prueba igual.
        monkeypatch.setattr(
            WaylandPopup, "prepare", lambda self: self._build_ui())

        self.mgr = vd.NotificationManager(
            corner="top-right", scheduler=lambda ms, cb: None)

        # Spy del reposicionamiento: registra QUIÉN se reposiciona y con qué
        # índice, sin cambiar el comportamiento.
        original = WaylandPopup.set_stack_margin
        registro = self.llamadas          # closure: el harness, no el popup

        def spy(popup, index):
            # El offset puede reservarse ANTES de que exista la window (así el
            # primer frame ya llega en su hueco, spec `toast-stack`): sin window
            # todavía no hay nada que reposicionar — el margen se registra
            # cuando `_build_ui` lo aplica (`GtkLayerShell.set_margin`).
            if popup.window is not None:
                registro.append((popup.window.id, index))
            return original(popup, index)

        monkeypatch.setattr(WaylandPopup, "set_stack_margin", spy)

    # -- notificaciones ----------------------------------------------------
    def mostrar(self, n, cuerpo=LONG, persistent=True):
        """Muestra n notificaciones y devuelve sus popups (vía _show_popup real)."""
        for i in range(n):
            self.mgr.notify(summary="n%d" % i, app_name="App", body=cuerpo,
                            expire_timeout=0 if persistent else 6000)
            while self.mgr._pending:
                nid, kwargs, _ = self.mgr._pending.pop(0)
                self.mgr._show_popup(nid, kwargs)
        return [p for _, p in self.mgr._active]

    # -- lecturas ----------------------------------------------------------
    @property
    def popups(self):
        return [p for _, p in self.mgr._active]

    def alto(self, popup):
        return popup._card.desired_height()

    def tops(self):
        """Margen superior de cada popup activo, en orden de pila.

        Es ESTADO, no evento: el margen que cada window tiene puesto ahora. Por
        eso `forget()` no lo borra (si no, un popup al que no se volvió a
        reposicionar aparecería como "sin margen" en vez de "en su sitio").
        """
        return [self.margen_por_win.get(p.window.id) for p in self.popups]

    def forget(self):
        """Olvida las LLAMADAS de reposicionamiento registradas hasta ahora."""
        self.llamadas.clear()



@pytest.fixture
def pila(monkeypatch):
    return Harness(monkeypatch)


# ── "Expandir con toasts debajo" ──────────────────────────────────────────

def _reposicionaron(pila, popups):
    """True si el harness vio reposicionar a TODOS los toasts, en orden de
    pila y una vez cada uno.

    No se asserta el VALOR que recibe `set_stack_margin`: el contrato es la
    geometría resultante (el gap de 12 px, que verifica
    `test_offsets_de_alturas_reales_mantienen_el_gap`), no si el manager pasa
    el índice o el offset acumulado. Lo que sí es observable y se exige es que
    no quede ningún toast activo sin reposicionar — ése es el solape.
    """
    esperados = [p.window.id for p in popups]
    vistos = [win_id for win_id, _ in pila.llamadas]
    return vistos == esperados


def test_expandir_reposiciona_todos_los_activos(pila):
    """Al expandir el toast de arriba, TODOS los activos se reposicionan (no
    sólo el que cambió de alto) y en orden de pila.

    Rojo hoy: `on_resize` → `_resize_card` y nada más; `set_stack_margin` no se
    vuelve a llamar (0 registros)."""
    popups = pila.mostrar(3)
    assert len(popups) == 3
    pila.forget()

    popups[0]._card.toggle_expanded()

    assert _reposicionaron(pila, popups), (
        "spec toast-stack / 'Expandir con toasts debajo': al expandir hay que "
        "re-llamar el reposicionamiento de TODOS los toasts activos, en orden "
        "de pila; registradas %s para %s"
        % (pila.llamadas, [p.window.id for p in popups])
    )


def test_offsets_de_alturas_reales_mantienen_el_gap(pila):
    """Los offsets salen de las ALTURAS REALES: con toasts de distinta altura,
    el margen del siguiente es el del anterior + su alto + 12 de gap.

    Rojo hoy: el margen de cada popup sale de SU propio alto
    (`índice * (alto_propio + 12)`), que con alturas distintas solapa; y sin
    restack los márgenes ni siquiera se recalculan."""
    popups = pila.mostrar(3, cuerpo=SHORT)
    # El de arriba crece (body largo) y el del medio también: alturas distintas.
    popups[0]._cuerpo = LONG
    popups[0]._card._cuerpo = LONG
    popups[1]._cuerpo = LONG * 2
    popups[1]._card._cuerpo = LONG * 2
    pila.forget()

    popups[0]._card.toggle_expanded()

    altos = [pila.alto(p) for p in popups]
    esperado = [BASE_MARGIN + sum(altos[:i]) + i * GAP
                for i in range(len(popups))]
    assert pila.tops() == esperado, (
        "spec toast-stack / 'La pila nunca solapa': el margen de cada card es "
        "la suma de las alturas reales + 12 de gap; con alturas %s los márgenes "
        "serían %s y se registraron %s"
        % (altos, esperado, pila.tops())
    )


def test_contraer_devuelve_el_espacio(pila):
    """Al contraer, los toasts de abajo vuelven a su posición (mismo estado que
    antes de expandir).

    Rojo hoy: idem — no hay restack, así que el espacio no se devuelve."""
    popups = pila.mostrar(3)
    tops_iniciales = pila.tops()
    assert tops_iniciales, "el harness debe registrar el margen inicial de la pila"

    pila.forget()
    popups[0]._card.toggle_expanded()
    assert pila.tops() != tops_iniciales, (
        "expandir el de arriba tiene que mover a los de abajo (si no se movieron, "
        "el test no probaría el reflow)"
    )

    pila.forget()
    popups[0]._card.toggle_expanded()      # contraer
    assert pila.tops() == tops_iniciales, (
        "spec toast-stack / 'Contraer devuelve el espacio': al contraer, los "
        "toasts de abajo vuelven a %s; quedaron en %s"
        % (tops_iniciales, pila.tops())
    )


# ── "El re-wrap por hover también re-flowea" ─────────────────────────────

def test_el_rewrap_por_hover_tambien_reflowea(pila):
    """El re-wrap por hover (franja de 44 px que cambia el wrap del body) es un
    cambio de alto más: reposiciona la pila igual que expandir.

    El body va EXPANDIDO a propósito: colapsado, el cap de 3 líneas hace que el
    wrap a 196 px no cambie el alto y la puerta de resize de 0.7.0 no dispara
    nada (ahí el re-wrap es real pero no cambia de tamaño: eso es otro test).

    Rojo hoy: el resize por hover redimensiona la propia ventana y no mueve a
    los demás."""
    popups = pila.mostrar(3)
    card = popups[0]._card
    card._expanded = True
    card.set_size_request(wp._CARD_WIDTH, card.desired_height())
    pila.forget()

    card._on_enter(card, None)

    assert _reposicionaron(pila, popups), (
        "spec toast-stack / 'El re-wrap por hover también re-flowea': entrar al "
        "hover cambia el alto del card y debe re-flowear la pila; registradas "
        "%s para %s" % (pila.llamadas, [p.window.id for p in popups])
    )


# ── "El reflow es estable" ───────────────────────────────────────────────

def test_expandir_y_contraer_repetido_converge(pila):
    """Varios ciclos de expandir/contraer: la pila vuelve SIEMPRE al mismo
    estado (mismos márgenes, mismo orden) y no acumula error ni oscila.

    Rojo hoy: los márgenes quedan clavados en el estado inicial y los índices
    que se registran no siguen a la expansión (converge "en falso")."""
    popups = pila.mostrar(3)
    tops_iniciales = pila.tops()

    for ciclo in range(3):
        pila.forget()
        popups[0]._card.toggle_expanded()          # expandir
        assert _reposicionaron(pila, popups), (
            "ciclo %d: expandir debe reposicionar toda la pila en orden; %s"
            % (ciclo, pila.llamadas)
        )
        pila.forget()
        popups[0]._card.toggle_expanded()          # contraer
        assert pila.tops() == tops_iniciales, (
            "ciclo %d: al volver a contraer la pila debe quedar en %s (sin "
            "deriva); quedó en %s"
            % (ciclo, tops_iniciales, pila.tops())
        )


# ── "Un toast que entra no tapa al que ya estaba" ────────────────────────

def _margenes_al_mapear(pila, monkeypatch):
    """(offsets con los que cada card mapeó su superficie, popup de arriba).

    Se espía `prepare` —el punto donde la window se mapea y se commitea— y se
    lee el offset que la card tenía EN ESE MOMENTO: lo que importa es el primer
    frame, no el estado final (el reflow posterior siempre corrige, pero el
    frame mal puesto ya se vio).
    """
    base = WaylandPopup.prepare          # el lambda del harness: _build_ui
    visto = []

    def spy(self):
        visto.append(self._stack_margin)
        return base(self)

    monkeypatch.setattr(WaylandPopup, "prepare", spy)
    # Body distinto en cada uno: si no, el dedup los tomaría como el mismo
    # evento y el segundo ni entraría a la pila.
    arriba, = pila.mostrar(1, cuerpo=SHORT)
    visto.clear()
    pila.mostrar(1, cuerpo=LONG)
    return visto, arriba


def test_el_que_entra_ya_llega_en_su_hueco(pila, monkeypatch):
    """Scenario "Un toast que entra no tapa al que ya estaba" (spec
    `toast-stack`): el hueco se reserva ANTES de mapear la superficie, así que
    el primer frame del que entra ya está debajo del toast de arriba.

    Rojo hoy: `_show_popup` llama `prepare()` —que mapea y commitea con el
    offset 0— y recién después reflowea: la card nueva se presenta un frame
    ENCIMA de la de arriba (el toast que "la tapa")."""
    visto, arriba = _margenes_al_mapear(pila, monkeypatch)

    esperado = pila.alto(arriba) + GAP
    assert visto == [esperado], (
        "spec toast-stack / 'Un toast que entra no tapa al que ya estaba': el "
        "offset del que entra tiene que estar puesto ANTES de mapear su "
        "superficie (alto de arriba %s + gap %s = %s); al mapear tenía %s"
        % (pila.alto(arriba), GAP, esperado, visto)
    )