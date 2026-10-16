"""
Tests de los hyperlinks del body (spec `body-hyperlinks`).

El contrato: cada `<a href>` con scheme soportado se renderiza como link
(span accent + underline) y el click sobre SU zona abre ESA url — no la
primera del body. `_strip_urls` sigue fuera (URLs planas no son links).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import wayland_popup as wp
from wayland_popup import WaylandPopup
from test_contrato_dbus import _manager_headless, _closes, _invokes


# --- 1.1 Transformación pura: markup + tabla de zonas ---

def test_body_markup_span_y_rangos_byte_exactos():
    text = ('Mirá <a href="https://ej.com/a">ver</a> o '
            '<a href="https://ej.com/b">responder</a> ya')
    mk, links = wp.body_markup(text, accent="#112233")
    span = '<span underline="single" color="#112233">'
    assert span + 'ver</span>' in mk
    assert span + 'responder</span>' in mk
    assert '<a' not in mk, "el markup Pango no tolera <a>"
    assert [u for u, _, _ in links] == ["https://ej.com/a", "https://ej.com/b"]
    # Los rangos son byte-exactos sobre el texto PLANO que Pango renderiza
    plain = mk.replace(span, "").replace("</span>", "")
    for (_u, s, e), label in zip(links, ("ver", "responder")):
        assert plain[s:e] == label, (
            "rango del link debe aislar el label en coords del texto renderizado")


def test_body_markup_scheme_no_soportado_no_es_link():
    mk, links = wp.body_markup('<a href="ftp://x">algo</a> y sigue')
    assert links == []
    assert "algo" in mk
    assert "underline" not in mk, "sin scheme válido no hay estilo de link"


def test_body_markup_sin_links_pasa_plano():
    mk, links = wp.body_markup("Texto común sin markup", accent="#112233")
    assert mk == "Texto común sin markup"
    assert links == []


# --- 1.2 Decisión de hit-test ---

def test_link_at_rango_semiabierto():
    links = [("https://a", 2, 5), ("https://b", 10, 14)]
    assert wp.link_at(links, 2) == "https://a"
    assert wp.link_at(links, 4) == "https://a"
    assert wp.link_at(links, 5) is None, "rango semiabierto: end no es link"
    assert wp.link_at(links, 12) == "https://b"
    assert wp.link_at(links, 0) is None
    assert wp.link_at(links, 99) is None


# --- 1.3 Flujo manager: click en un link abre ESA url ---

def test_click_en_segundo_link_abre_esa_url_y_cierra_razon_2(monkeypatch):
    popens = []
    monkeypatch.setattr(
        "verdantis_daemon.subprocess.Popen", lambda cmd, **k: popens.append(cmd))
    m = _manager_headless()
    nid = m.notify(
        app_name="t", summary="s",
        body=('Mirá <a href="https://ej.com/a">ver</a> o '
              '<a href="https://ej.com/b">responder</a>'),
        actions=["default", "Abrir"], hints={"transient": True},
        expire_timeout=5000,
    )
    m._pump()
    m._on_link_clicked(nid, "https://ej.com/b")
    assert popens == [["xdg-open", "https://ej.com/b"]], (
        "el click sobre el segundo link abre SU url, no la primera")
    assert _invokes(m._dbus_bus) == [], (
        "un link no es action key: sin ActionInvoked")
    assert _closes(m._dbus_bus) == [(nid, 2)], (
        "cierra igual que un click del cuerpo (razón 2, spec contrato-dbus)")


def test_click_link_a_host_local_no_abre(monkeypatch):
    popens = []
    monkeypatch.setattr(
        "verdantis_daemon.subprocess.Popen", lambda cmd, **k: popens.append(cmd))
    m = _manager_headless()
    nid = m.notify(
        app_name="t", summary="s",
        body='<a href="http://127.0.0.1:9/x">local</a>',
        hints={"transient": True}, expire_timeout=5000,
    )
    m._pump()
    m._on_link_clicked(nid, "http://127.0.0.1:9/x")
    assert popens == [], "guard _is_local_url: hosts locales nunca se abren"
    assert _closes(m._dbus_bus) == [(nid, 2)]


# --- 1.4 Medición == dibujado (misma transformación) ---

def test_medicion_del_body_usa_el_markup_de_links():
    body = 'Texto <a href="https://ej.com/a">ver nota</a> fin'
    mk, _links = wp.body_markup(body)
    # calc_card_height sobre el body crudo debe igualar al body YA transformado
    # (la medición consume el mismo markup que el dibujado).
    assert WaylandPopup.calc_card_height("", body, "") == \
        WaylandPopup.calc_card_height("", mk, "")
