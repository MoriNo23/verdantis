"""Urgencia `critical` (spec freedesktop 1.2): no expira y se distingue.

Antes un critical duraba 1.5x el timeout y seguía desapareciendo: el usuario
no alcanzaba a leer una alerta crítica. Acá la regla es que NO expire y que
lleve un rail de acento propio para reconocerla en la pila.
"""
import app_info as ai
import verdantis_daemon as vd
import wayland_popup as wp

from test_render_gsk import _nodos


def test_acento_critical_es_propio_y_gana_al_de_la_app():
    assert ai.CRITICAL_ACCENT != ai.DEFAULT_ACCENT
    assert ai.accent_for(2) == ai.CRITICAL_ACCENT
    assert ai.accent_for(2, "#123456") == ai.CRITICAL_ACCENT
    assert ai.accent_for(1) == ai.DEFAULT_ACCENT
    assert ai.accent_for(1, "#123456") == "#123456"


def test_critical_no_expira_aunque_traiga_timeout():
    assert vd._duration_for(5000, False, 2) == 0
    assert vd._duration_for(5000, False, 1) == 5000
    assert vd._duration_for(0, False, 1) == 0
    assert vd._duration_for(5000, True, 1) == 0


def test_critical_anade_rail_de_acento_al_render():
    """Mismo acento, distinta urgencia: el nodo GSK debe cambiar."""
    data_c, _ = _nodos("Alerta", urgencia=2, acento=ai.CRITICAL_ACCENT)
    data_n, _ = _nodos("Alerta", urgencia=1, acento=ai.CRITICAL_ACCENT)
    assert data_c != data_n, "el render de critical no se distingue del normal"
