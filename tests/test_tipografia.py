"""Escala tipográfica del toast: jerarquía real, sin cards que exploten.

Antes de v0.15.11 título y body compartían 11 px y la app bajaba a 10: la
jerarquía dependía solo del peso. Ahora la escala es title > body > app y estos
tests la fijan, además de acotar el alto del card para que un body largo no
empuje el contenido fuera de la superficie.
"""
import toast_window as wp


def test_jerarquia_de_tamanos():
    assert wp._TITLE_FS > wp._BODY_FS > wp._APP_FS


def test_minimos_legibles():
    assert wp._TITLE_FS >= 13
    assert wp._BODY_FS >= 12
    assert wp._APP_FS >= 11


def test_escala_por_resolucion_conserva_la_jerarquia():
    """El `font_scale` de monitores chicos no puede aplanar la escala."""
    for fs in (0.85, 0.92, 1.0, 1.15):
        title = max(9, round(wp._TITLE_FS * fs))
        body = max(9, round(wp._BODY_FS * fs))
        app = max(8, round(wp._APP_FS * fs))
        assert title >= body >= app


def test_body_largo_no_explota_el_card():
    """3 líneas visibles: el alto queda acotado (la card mide 360 de ancho)."""
    largo = "palabra " * 120
    alto = wp.ToastWindow.calc_card_height(
        "Brave", largo, "", text_width=212, actions_count=0, has_copy=True)
    assert alto <= 220, "card de %s px: ¿se perdió el cap de 3 líneas?" % alto
