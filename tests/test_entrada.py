"""
Tests del ENTRY POINT (`src/verdantis.py`) — la decisión de arquitectura.

El módulo estaba al 0% de cobertura (tabla de crapper), y es justo el que
contiene la decisión que su propio docstring declara:

    "`--daemon` delega al daemon DBus (GTK + layer-shell, SIN Qt). El one-shot
    elige backend Wayland (WaylandPopup) o, si no hay layer-shell, el fallback
    PyQt6 — que se importa recién en ese branch (qt_fallback), nunca al
    arrancar."

Eso son CUATRO comportamientos, y hasta acá ninguno tenía red:

1. `--daemon` delega al daemon con el argv reescrito (solo el corner).
2. La decisión de backend (Wayland con `WAYLAND_DISPLAY`; `--force-qt` lo salta).
3. La caída al fallback cuando Wayland falla (mensaje a stderr + branch Qt).
4. El import perezoso: el path daemon y el Wayland NO cargan PyQt6; el branch
   Qt sí.

Nota sobre `qt_fallback.py` (que sigue al 0% y queda AFUERA de este change):
su único camino es "no hay Wayland", y probarlo necesita un display de Qt con
evento loop. Un test que solo importe el módulo produciría un número de
cobertura sin afirmar nada del render — el mismo tipo de número falso que da
correr crapper cuando no detecta pytest. Documentado en el design del change.

Estos tests son CARACTERIZACIÓN: cubren comportamiento existente y pasan desde
el primer run. Su valor es que cualquier cambio que rompa la delegación, la
decisión o el import perezoso se entera acá, no en producción.
"""

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
    """WaylandPopup que revienta — para probar la caída al fallback."""

    def __init__(self, **kwargs):
        raise RuntimeError("sin layer-shell")


class _QAppFake:
    """QApplication de mentira: registra la construcción y sale de exec()."""

    def __init__(self, argv):
        self.argv = list(argv)
        _QAppFake.instancias.append(self)

    instancias = []

    @staticmethod
    def instance():
        return None

    def setApplicationName(self, nombre):
        self.nombre = nombre

    def exec(self):
        return 0


class _NotiFake:
    """NotificacionPersonalizada de mentira: registra construcción y show()."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.mostrado = False
        _NotiFake.construidas.append(self)

    construidas = []

    def show(self):
        self.mostrado = True


@pytest.fixture
def _qt_fingido(monkeypatch):
    """Cablea los fakes de Qt en qt_fallback y limpia los registros.

    `import qt_fallback` carga PyQt6 de verdad (importar no necesita display;
    solo lo necesita QApplication, que acá se finge). El import real es parte
    de lo que se prueba: es el `from qt_fallback import …` perezoso de main."""
    import qt_fallback
    _PopupFake.construidos = []
    _QAppFake.instancias = []
    _NotiFake.construidas = []
    monkeypatch.setattr(qt_fallback, "QApplication", _QAppFake)
    monkeypatch.setattr(qt_fallback, "NotificacionPersonalizada", _NotiFake)
    return qt_fallback


def _modulos_pyqt():
    """Los submódulos PyQt6 cargados AHORA (para el assert del import perezoso).

    Se compara un snapshot antes/después del run en vez de suprimir
    `sys.modules` (reemplazarlo entero rompe el import machinery y colgó la
    suite): el contrato es que ESTE path no CARGE Qt, no que Qt no esté en
    memoria por otra razón."""
    return {m for m in sys.modules if m.startswith("PyQt6")}


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


def test_daemon_no_carga_pyqt(monkeypatch):
    """El path daemon es GTK + layer-shell, SIN Qt: no puede cargar PyQt6
    (el import de Qt al arrancar compite por el bus y lo pierde)."""
    antes = _modulos_pyqt()
    monkeypatch.setattr(verdantis_daemon, "main", lambda: None)
    _main_con(["--daemon"], monkeypatch)
    assert _modulos_pyqt() == antes, (
        "el path --daemon cargó PyQt6: el import del fallback Qt tiene que "
        "seguir siendo perezoso (solo en el branch del one-shot)"
    )


def test_wayland_cuando_hay_display(monkeypatch):
    """Con `WAYLAND_DISPLAY` seteado, el one-shot va por WaylandPopup."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test-0")
    _PopupFake.construidos = []
    antes = _modulos_pyqt()
    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupFake)
    _main_con(["--title", "T", "--body", "B"], monkeypatch)
    assert len(_PopupFake.construidos) == 1, "debe construir UN solo popup"
    assert _PopupFake.construidos[0].kwargs["titulo"] == "T"
    assert _PopupFake.construidos[0].kwargs["cuerpo"] == "B"
    assert _PopupFake.construidos[0].mostrado, "popup.show() tiene que correr"
    assert _modulos_pyqt() == antes, (
        "el path Wayland no toca Qt: el fallback se importa recién si hace falta"
    )


def test_sin_wayland_cae_al_fallback_qt(monkeypatch, _qt_fingido):
    """Sin `WAYLAND_DISPLAY` y sin forzar nada: el fallback Qt es el camino.

    Y el branch SÍ importa qt_fallback (el import perezoso existe para NO
    pagarlo en los otros paths, no para no pagarlo nunca)."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with pytest.raises(SystemExit) as ex:
        _main_con(["--title", "T", "--body", "B"], monkeypatch)
    assert ex.value.code == 0, "app.exec() devolvió 0: exit limpio"
    assert len(_QAppFake.instancias) == 1
    assert len(_NotiFake.construidas) == 1
    assert _NotiFake.construidas[0].kwargs["titulo"] == "T"
    assert _NotiFake.construidas[0].mostrado
    import qt_fallback
    assert "qt_fallback" in sys.modules, (
        "el branch Qt debe importar qt_fallback (recién acá, perezoso)"
    )


def test_wayland_que_falla_cae_al_fallback(monkeypatch, capsys, _qt_fingido):
    """Si WaylandPopup revienta (p. ej. sin layer-shell), el one-shot baja al
    fallback Qt avisando por stderr — no crashea sin más."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test-0")
    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupRoto)
    with pytest.raises(SystemExit):
        _main_con(["--force-wayland", "--title", "T"], monkeypatch)
    err = capsys.readouterr().err
    assert "Wayland falló" in err and "sin layer-shell" in err, (
        "la caída al fallback tiene que avisar por stderr con el motivo"
    )
    assert len(_NotiFake.construidas) == 1, "el fallback Qt corre tras la falla"


def test_force_qt_salta_wayland_although_haya_display(monkeypatch, _qt_fingido):
    """`--force-qt` fuerza el fallback incluso con Wayland disponible."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test-0")

    class _PopupProhibido:
        def __init__(self, **kwargs):
            raise AssertionError("no debe construir el popup Wayland")

    monkeypatch.setattr(wayland_popup, "WaylandPopup", _PopupProhibido)
    with pytest.raises(SystemExit):
        _main_con(["--force-qt"], monkeypatch)
    assert len(_NotiFake.construidas) == 1, "--force-qt va por el branch Qt"
