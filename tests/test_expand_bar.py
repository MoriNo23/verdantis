"""Regresión: Thunderbird con body largo revienta al dibujar 'Ver más'.

El chevron de la barra de expandir usaba una variable `acc` que se borró
cuando los botones pasaron a blanco neutro. Sólo se ejecutaba con body de más
de 3 líneas, por eso los tests con bodies cortos no lo vieron.
"""
from test_render_gsk import _nodos


def test_expand_bar_con_body_largo_no_lanza():
    data, w = _nodos("palabra " * 120)
    assert w._expand_rect is not None
    assert "rgba" in data
