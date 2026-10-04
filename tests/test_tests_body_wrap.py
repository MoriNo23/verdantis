"""
Metatest de sensibilidad para el contrato de wrap del body
(tests/test_body_wrap.py).

El bug que esos tests cubren: el body se envolvía por palabra (`WORD_CHAR`) SIN
justificar, así que el renglón que corta antes de la palabra siguiente quedaba
con un hueco visible de 23-43 px al final (el espacio del corte) — el reporte
del usuario en vivo.

La inyección usa el proxy de layout de `test_body_colapso._con_heuristica`
(la misma técnica: recompilar las dos gemelas sustituyendo UNA línea), pero
en vez de la línea del presupuesto del cap cambia la del `set_justify`: es el
otro punto por donde pasa el wrap.
"""

import inspect
import textwrap

import wayland_popup as wp
from wayland_popup import NotificationWidget

import test_body_wrap as wrap

# La línea del wrap justificado y su versión vieja (sin justificar).
JUSTIFICADO = "layout.set_justify(True)"
SIN_JUSTIFICAR = "pass  # sin justificar"


def _sin_justificar(fn):
    """Recompila `fn` con el `set_justify` del body eliminado.

    `inspect.getsource` + sustitución + exec con los globals del módulo: el
    metatest no copia el código que vigila, así que no puede divergir de él.
    """
    src = textwrap.dedent(inspect.getsource(fn))
    assert JUSTIFICADO in src, (
        "Metatest roto: %s no tiene la línea de justificado que este metatest "
        "quitaría. Si el wrap cambió de forma, la inyección ya no simularía el "
        "bug que test_body_wrap.py debe detectar." % fn.__name__
    )
    src = src.replace(JUSTIFICADO, SIN_JUSTIFICAR)
    ns = {}
    exec(compile(src, "<metatest:sin_justificar>", "exec"),
         wp.__dict__, ns)
    return ns[fn.__name__]


def _inyectar_sin_justificar(monkeypatch):
    """Deja el módulo con las DOS gemelas sin justificar."""
    monkeypatch.setattr(wp, "_body_metrics",
                        _sin_justificar(wp._body_metrics))
    monkeypatch.setattr(NotificationWidget, "_draw_text",
                        _sin_justificar(NotificationWidget._draw_text))


def test_metatest_el_body_justifica(monkeypatch):
    """Sanidad: el código real justifica en las dos gemelas y envuelve por
    palabra.

    Si alguien sacara el `set_justify` (el bug) o cambiara el wrap a `CHAR`
    (que llena el margen partiendo palabras), este test lo dice antes que los
    tests de píxeles."""
    for fn in (wp._body_metrics, NotificationWidget._draw_text):
        src = inspect.getsource(fn)
        assert JUSTIFICADO in src, (
            "%s debe justificar el body: sin set_justify queda el hueco del "
            "corte al final del renglón" % fn.__name__
        )
        assert "set_wrap(Pango.WrapMode.WORD_CHAR)" in src, (
            "%s debe seguir envolviendo por palabra: el wrap del body es "
            "WORD_CHAR (justificar estira espacios, no parte palabras)"
            % fn.__name__
        )


def test_metatest_la_version_real_justifica(monkeypatch):
    """Contraparte (smoke): con el código real el renglón queda justificado.

    Sin esto el metatest podría "detectar" un bug en un código que tampoco
    cumple el contrato."""
    px, (x0, top, col_w) = wrap._pixeles_del_body(wrap.OVERFLOW)
    _w, _h, bands, _ = wrap._body_bands(wrap.OVERFLOW)
    for b in bands:
        hueco, gap_max = wrap._huecos(px, b, x0, x0 + col_w)
        assert hueco <= gap_max + wrap.HOLGURA, (
            "Metatest roto: la versión real deja un hueco de %d px en la fila "
            "%d (mayor que el espacio más ancho de la línea, %d px)"
            % (hueco, b[0], gap_max)
        )


def test_metatest_bug_detecta_el_hueco_del_corte(monkeypatch):
    """Con el `set_justify` inyectado fuera, el predicado de wrap queda en rojo.

    Es el bug reportado: un renglón que corta antes de la palabra siguiente
    queda con el hueco del corte (23-43 px) y `test_el_renglon_se_justifica_
    hasta_el_margen` lo detecta."""
    _inyectar_sin_justificar(monkeypatch)
    px, (x0, top, col_w) = wrap._pixeles_del_body(wrap.OVERFLOW)
    _w, _h, bands, _ = wrap._body_bands(wrap.OVERFLOW)
    rotos = [
        (b[0], wrap._huecos(px, b, x0, x0 + col_w)[0])
        for b in bands
        if wrap._huecos(px, b, x0, x0 + col_w)[0] > wrap._huecos(px, b, x0, x0 + col_w)[1] + wrap.HOLGURA
    ]
    assert rotos, (
        "Metatest roto: con el bug inyectado ningún renglón queda con hueco "
        "visible; `test_el_renglon_se_justifica_hasta_el_margen` no detectaría "
        "que falte el `set_justify` (sería un placebo). Huecos por fila: %s"
        % [(b[0], wrap._huecos(px, b, x0, x0 + col_w)[0]) for b in bands]
    )
