"""
Tests del ENTRY POINT (`src/verdantis.py`) — la decisión de arquitectura.

El módulo contiene la decisión que su propio docstring declara:

    "`--daemon` delega al daemon DBus (GTK + layer-shell, SIN Qt). El
    one-shot elige backend por sesión: Wayland con layer-shell
    (WaylandPopup) → X11 con ventana GTK posicionable (x11_popup); en
    Wayland SIN layer-shell falla limpio (stderr + exit ≠ 0)."

Eso son CUATRO comportamientos:

1. `--daemon` delega al daemon con el argv reescrito (solo el corner).
2. La decisión de backend (`WAYLAND_DISPLAY` → Wayland; `--force-fallback`
   salta el branch Wayland; sin `WAYLAND_DISPLAY` → fallback X11).
3. El error en Wayland sin layer-shell: stderr nombrando layer-shell y
   exit ≠ 0, SIN caer a un fallback mal posicionado (spec `entrada-fallback`).
4. El import perezoso: NINGÚN path (daemon, Wayland, fallback) importa
   PyQt6 ni `qt_fallback` — Qt fue eliminado del proyecto.

Estos tests son de regresión de la arquitectura: cualquier cambio que
rompa la delegación, la decisión, el error limpio o saque Qt de vuelta se
entera acá, no en producción.
"""

import os
import subprocess
import sys

import pytest

import verdantis
import verdantis_daemon
import wayland_popup


class _PopupFake:
    """WaylandPopup de mentira: registra construcción y show()."""

    construidos = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.mostrado = False
        _PopupFake.construidos.append(self)

    def show(self):
        self.mostrado = True


class _PopupRoto:
    """WaylandPopup que revienta — para probar el error en Wayland."""

    def __init__(self, **kwargs):
        raise RuntimeError("sin layer-shell")


class _NotiFake:
    """NotificacionX11 de mentira: registra construcción y show()."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.mostrado = False
        _NotiFake.construidas.append(self)

    construidas = []

    def show(self):
        self.mostrado = True


@pytest.fixture
def _fallback_fingido(monkeypatch):
    """Cablea el fake de NotificacionX11 en x11_popup y limpia los registros.

    El import REAL de `x11_popup` es parte de lo que se prueba: es el
    `from x11_popup import …` perezoso de main, y no puede arrastrar Qt."""
    import x11_popup
    _PopupFake.construidos = []
    _NotiFake.construidas = []
    monkeypatch.setattr(x11_popup, "NotificacionX11", _NotiFake)
    return x11_popup


def _mods_qt():
    """Snapshot de TODO rastro de Qt/fallback Qt en `sys.modules` AHORA.

    Se compara un snapshot antes/después del run en vez de suprimir
    `sys.modules` (reemplazarlo entero rompe el import machinery y colgó la
    suite): el contrato es que NINGÚN path CARGUE Qt, no que Qt no esté en
    memoria por otra razón (hoy ya no puede estarlo: `qt_fallback.py` y
    PyQt6 fueron eliminados)."""
    return {m for m in sys.modules
            if m.startswith("PyQt6") or m == "qt_fallback"}


def _main_con(argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["verdantis"] + argv)
    verdantis.main()


def test_daemon_delega_con_argv_reescrito(monkeypatch):
    """`--daemon` llama al main del daemon con SOLO el corner: ni title, ni
    body, ni flags del one-shot viajan (el daemon no los entiende)."""
    llamadas = []
    monkeypatch.setattr(verdantis_daemon, "main",
                        lambda: llamadas.append(list(sys.argv)))
    _main_con(["--daemon", "--corner", "top-left",
               "--title", "basura-del-one-shot"], monkeypatch)
    assert llamadas == [["verdantis", "--corner", "top-left"]], (
        "el daemon debe recibir el argv reescrito: solo --corner"
    )


def test_daemon_no_carga_qt(monkeypatch):
    """El path daemon es GTK + layer-shell: no puede cargar PyQt6 ni
    importar el módulo del fallback (imports perezosos, spec `entrada-fallback`)."""
    antes = _mods_qt()
    monkeypatch.setattr(verdantis_daemon, "main", lambda: None)
    _main_con(["--daemon"], monkeypatch)
    assert _mods_qt() == antes, (
        "el path --daemon cargó Qt: ningún path del proyecto puede importarlo"
    )


def test_wayland_cuando_hay_display(monkeypatch):
    """Con `WAYLAND_DISPLAY` seteado, el one-shot va por WaylandPopup y NO
    construye ninguna ventana de fallback."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test-0")
    _PopupFake.construidos = []
    _NotiFake.construidas = []
    antes = _mods_qt()
    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupFake)
    _main_con(["--title", "T", "--body", "B"], monkeypatch)
    assert len(_PopupFake.construidos) == 1, "debe construir UN solo popup"
    assert _PopupFake.construidos[0].kwargs["titulo"] == "T"
    assert _PopupFake.construidos[0].kwargs["cuerpo"] == "B"
    assert _PopupFake.construidos[0].mostrado, "popup.show() tiene que correr"
    assert not _NotiFake.construidas, (
        "el path Wayland no crea ventana de fallback"
    )
    assert _mods_qt() == antes, (
        "el path Wayland no toca Qt: el fallback se importa recién si hace falta"
    )


def test_sin_wayland_cae_al_fallback_x11(monkeypatch, _fallback_fingido):
    """Sin `WAYLAND_DISPLAY` y sin forzar nada: el fallback X11 es el camino.

    Y el branch SÍ importa `x11_popup` (el import perezoso existe para NO
    pagarlo en los otros paths, no para no pagarlo nunca) — pero sin tocar
    ni PyQt6 ni `qt_fallback`."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    antes = _mods_qt()
    _main_con(["--title", "T", "--body", "B"], monkeypatch)
    assert len(_NotiFake.construidas) == 1
    assert _NotiFake.construidas[0].kwargs["titulo"] == "T"
    assert _NotiFake.construidas[0].kwargs["cuerpo"] == "B"
    assert _NotiFake.construidas[0].mostrado
    assert "x11_popup" in sys.modules, (
        "el branch X11 debe importar x11_popup (recién acá, perezoso)"
    )
    assert _mods_qt() == antes, (
        "el branch fallback importó rastro de Qt: el fallback es GTK"
    )


def test_wayland_sin_layer_shell_falla_limpio(monkeypatch, capsys,
                                               _fallback_fingido):
    """Si WaylandPopup revienta (sin layer-shell), el one-shot NO cae a un
    fallback mal posicionado: stderr nombrando layer-shell + exit ≠ 0
    (spec `entrada-fallback`, "En Wayland sin layer-shell el one-shot falla
    limpio")."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test-0")
    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupRoto)
    with pytest.raises(SystemExit) as ex:
        _main_con(["--force-wayland", "--title", "T"], monkeypatch)
    assert ex.value.code != 0, "sin layer-shell el exit tiene que ser ≠ 0"
    err = capsys.readouterr().err
    assert "layer-shell" in err, (
        "el error de stderr tiene que nombrar layer-shell (la causa real)"
    )
    assert not _NotiFake.construidas, (
        "en Wayland NO hay fallback: ninguna ventana de fallback puede crearse"
    )


def test_force_fallback_salta_wayland_although_haya_display(monkeypatch,
                                                            _fallback_fingido):
    """`--force-fallback` fuerza el branch X11 incluso con Wayland disponible."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test-0")

    class _PopupProhibido:
        def __init__(self, **kwargs):
            raise AssertionError("no debe construir el popup Wayland")

    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupProhibido)
    _main_con(["--force-fallback"], monkeypatch)
    assert len(_NotiFake.construidas) == 1, (
        "--force-fallback va por el branch X11"
    )
    assert _NotiFake.construidas[0].mostrado


def test_sesion_x11_sin_wayland_usa_fallback(monkeypatch, _fallback_fingido):
    """Sesión X11 pura (sin `WAYLAND_DISPLAY`, sin flags): fallback X11,
    sin construir el popup Wayland (escenario "Sesión X11" del spec)."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    class _PopupProhibido:
        def __init__(self, **kwargs):
            raise AssertionError("sin WAYLAND_DISPLAY no hay popup Wayland")

    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupProhibido)
    _main_con(["--title", "Hola"], monkeypatch)
    assert len(_NotiFake.construidas) == 1
    assert _NotiFake.construidas[0].kwargs["titulo"] == "Hola"
    assert not _PopupFake.construidos


def test_force_fallback_sin_display_falla_limpio():
    """Escenario "Forzar fallback en headless" del spec `entrada-fallback`:
    sin display real, el branch X11 emite el error por stderr y termina con
    exit code 1 — sin ventana a medias y sin abort de GTK (core dump).

    Corre en SUBPROCESO: el display de Gtk no se puede deshacer en el
    proceso de la suite (ya está inicializado por los otros tests)."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
    env["GDK_BACKEND"] = "x11"
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(
        [sys.executable, os.path.join(raiz, "src", "verdantis.py"),
         "--force-fallback", "--title", "headless"],
        env=env, capture_output=True, timeout=60)
    stderr = r.stderr.decode(errors="replace")
    assert r.returncode == 1, (
        f"sin display el exit tiene que ser 1 ( GTK no puede abortar con "
        f"core): code={r.returncode}, stderr={stderr[:300]}"
    )
    assert "sin display" in stderr, (
        f"el error de stderr tiene que decir que no hay display: {stderr[:300]}"
    )
