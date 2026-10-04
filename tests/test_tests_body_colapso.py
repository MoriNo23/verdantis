"""
Metatest de sensibilidad para el contrato de `toast-body-colapso`
(tests/test_body_colapso.py).

El bug que esos tests cubren es el presupuesto del cap de líneas: se estimaba
como `max_lines × int(font_size × 1.6)` en vez de `max_lines × la altura real
de la línea`. La línea lógica real de Manrope 11 mide 21 px y la estimación da
17.6, así que el cap siempre cortaba una línea antes — un body de exactamente 2
líneas quedaba en 1 línea + "..." sin botón "Ver más".

La inyección se hace RE-COMPILANDO las dos funciones gemelas (`_body_metrics` y
`NotificationWidget._draw_text`) con esa única línea sustituida por la
heurística vieja, a partir de su fuente REAL (`inspect.getsource`): el metatest
no copia el código que vigila, así que no puede divergir de él ni compilar un
doble que "se parece" al buggy. Los globals son los del módulo, de modo que la
versión inyectada se comporta exactamente como la original salvo en el
presupuesto.
"""

import inspect
import textwrap

import wayland_popup as wp
from wayland_popup import NotificationWidget

from test_body_colapso import (
    OVERFLOW, TWO_LINES, _body_bands, _real_line_h,
)

# La línea del presupuesto con la fórmula medida (D1) y su versión vieja.
MEDIDO = "layout.set_height(int(max_lines * line_h) * Pango.SCALE)"
HEURISTICA = "layout.set_height(max_lines * int(font_size * 1.6 * Pango.SCALE))"


def _con_heuristica(fn):
    """Recompila `fn` con el presupuesto viejo (`font_size × 1.6`)."""
    src = textwrap.dedent(inspect.getsource(fn))
    assert MEDIDO in src, (
        "Metatest roto: la línea del presupuesto medido no está en %s. Si la "
        "fórmula del cap cambió de forma, este metatest ya no inyectaría el bug "
        "que los tests de test_body_colapso.py deben detectar."
        % fn.__name__
    )
    src = src.replace(MEDIDO, HEURISTICA)
    ns = {}
    exec(compile(src, "<metatest:heuristica>", "exec"), wp.__dict__, ns)
    return ns[fn.__name__]


def _inyectar(monkeypatch):
    """Deja el módulo con las DOS gemelas usando la heurística vieja."""
    monkeypatch.setattr(wp, "_body_metrics", _con_heuristica(wp._body_metrics))
    monkeypatch.setattr(NotificationWidget, "_draw_text",
                        _con_heuristica(NotificationWidget._draw_text))


def _contrato_roto(font_scale=1.0):
    """Los predicados de test_body_colapso con el bug inyectado.

    Devuelve las tres cosas que el contrato exige y que con el bug se rompen:
    cuántas líneas se dibujan de un body de 2, cuántas de uno con overflow y
    cuánto se reserva para el body."""
    cap = NotificationWidget._MAX_VISIBLE_LINES
    _w, h2, bands2, _ = _body_bands(TWO_LINES)
    w, _h, bands, (_x0, top, col_w) = _body_bands(OVERFLOW, font_scale=font_scale)
    reservado = w._expand_rect[1] - wp._BTN_GAP - top
    return {
        "lineas_2": len(bands2),
        "lineas_overflow": len(bands),
        "reservado": reservado,
        "reservado_esperado": cap * _real_line_h(OVERFLOW, col_w, font_scale),
        "lineas_2_esperadas": 2,
        "overflow_esperadas": cap,
    }


def test_metatest_el_presupuesto_es_el_medido():
    """Sanidad: las DOS gemelas presupuestan con la altura real de la línea.

    Si alguien reintrodujera la heurística en una sola de las dos, este test lo
    dice antes que los tests de píxeles (y con el motivo, no con un 42 == 63).
    """
    for fn in (wp._body_metrics, NotificationWidget._draw_text):
        src = inspect.getsource(fn)
        assert MEDIDO in src, (
            "%s debe presupuestar el cap con la altura REAL de la línea "
            "(spec `toast-body-colapso`), no con font_size × 1.6" % fn.__name__
        )
        assert "get_line_readonly(0).get_pixel_extents()" in src, (
            "%s debe medir la línea del layout que va a dibujar, no estimarla"
            % fn.__name__
        )


def test_metatest_la_version_real_cumple_el_contrato():
    """Contraparte (smoke): con el código real los tres predicados se cumplen.

    Sin esto el metatest podría estar "detectando" un bug en un código que
    tampoco cumple el contrato."""
    r = _contrato_roto()
    assert r["lineas_2"] == r["lineas_2_esperadas"] == 2
    assert r["lineas_overflow"] == r["overflow_esperadas"] == 3
    assert r["reservado"] == r["reservado_esperado"]


def test_metatest_bug_roba_la_segunda_linea_del_body(monkeypatch):
    """Con la heurística inyectada, el body de 2 líneas vuelve a 1 + "...".

    Es el bug reportado: la 2ª línea ilegible y, como el cap no declara
    overflow, sin botón "Ver más" que la alcanzara.
    """
    _inyectar(monkeypatch)
    r = _contrato_roto()
    assert r["lineas_2"] == 1, (
        "Metatest roto: con el bug inyectado el body de 2 líneas debería "
        "colapsar a 1 (se dibujaron %d). Si no, "
        "`test_body_de_exactamente_dos_lineas_se_muestra_completo` no "
        "detectaría la heurística (sería un placebo)." % r["lineas_2"]
    )


def test_metatest_bug_roba_la_tercera_linea_del_cap(monkeypatch):
    """Con la heurística inyectada, el overflow vuelve a 2 líneas + "..."."""
    _inyectar(monkeypatch)
    r = _contrato_roto()
    assert r["lineas_overflow"] == 2, (
        "Metatest roto: con el bug inyectado el cap debería mostrar 2 de sus 3 "
        "líneas (se dibujaron %d). Si no, "
        "`test_overflow_dibuja_las_tres_lineas_del_cap` no detectaría la "
        "heurística (sería un placebo)." % r["lineas_overflow"]
    )


def test_metatest_bug_reserva_menos_que_tres_lineas_reales(monkeypatch):
    """Con la heurística inyectada, lo reservado no es 3 × la línea real.

    Es el mismo bug medido del lado de la MEDICIÓN (`calc_card_height` vía
    `_body_metrics`), para que el metatest no dependa solo del dibujado.
    """
    _inyectar(monkeypatch)
    r = _contrato_roto()
    line_h = r["reservado_esperado"] // 3      # la altura real de línea (63/3)
    assert r["reservado"] == 2 * line_h < r["reservado_esperado"], (
        "Metatest roto: con el bug inyectado se reservan 2 líneas reales (%d "
        "px) en vez de las 3 del cap (%d px); lo medido fue %s. Si no, "
        "`test_altura_reservada_del_body_coincide_con_lo_dibujado` no "
        "detectaría la heurística."
        % (r["reservado"], r["reservado_esperado"], r)
    )