"""
Metatest de sensibilidad para los hyperlinks del body
(tests/test_body_hyperlinks.py, spec `body-hyperlinks`).

Los bugs cubiertos: (1) todos los links resuelven a la URL del PRIMERO (el
comportamiento aplanado de hoy, donde el click abre siempre la primera URL);
(2) los rangos colapsados (zona de tamaño 0) dejan el link inclickeable. Se
inyecta la versión bugueada de `body_markup` y se verifica que el predicado
correspondiente queda en rojo; sin esto, la suite sería un placebo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import wayland_popup as wp


def test_metatest_todos_los_links_a_la_primer_url(monkeypatch):
    """Inyección: la tabla mapea CADA zona a la URL del primer link.
    El predicado de 1.1 (cada link con SU url) debe quedar en rojo."""
    real = wp.body_markup

    def _bug(text, accent="#80cbc4"):
        mk, links = real(text, accent)
        if not links:
            return mk, links
        first = links[0][0]
        return mk, [(first, s, e) for _u, s, e in links]

    monkeypatch.setattr(wp, "body_markup", _bug)
    _mk, links = wp.body_markup(
        'A <a href="https://a">x</a> B <a href="https://b">y</a>')
    assert [u for u, _s, _e in links] != ["https://a", "https://b"], (
        "Metatest roto: con el bug inyectado (todo → primer link) el "
        "predicado de urls por-link queda en verde"
    )


def test_metatest_rangos_colapsados_dejan_de_resolver(monkeypatch):
    """Inyección: zonas de tamaño 0 (start == end). El predicado de hit-test
    (1.2: el índice dentro del label resuelve la url) debe quedar en rojo."""
    real = wp.body_markup

    def _bug(text, accent="#80cbc4"):
        mk, links = real(text, accent)
        return mk, [(u, 0, 0) for u, _s, _e in links]

    monkeypatch.setattr(wp, "body_markup", _bug)
    _mk, links = wp.body_markup('A <a href="https://a">x</a>')
    assert wp.link_at(links, 0) != "https://a", (
        "Metatest roto: con rangos colapsados el click sobre el link "
        "seguiría resolviendo — el hit-test no estaría cubierto"
    )
