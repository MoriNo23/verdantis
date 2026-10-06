"""
Metatests de sensibilidad para test_action_zones.py: verifican que la suite
DETECTARÍA la regresión al diseño viejo (pill 28x28 esquinado + botón
expandir compacto a la derecha), los bugs que motivaron el rediseño.
"""
import inspect

import wayland_popup as wp

W, H = 360, 120


def _old_pill_rect():
    """El rect del pill 28x28 esquinado de antes del rediseño
    (cx_r = W - pad - 6, cy_t = 6, cs = 28)."""
    cx_r = W - 14 - 6
    cy_t = 6
    cs = 28
    return (cx_r - cs, cy_t, cx_r, cy_t + cs)


def test_metatest_strip_test_rejects_old_pill():
    """Simula el bug (pill 28x28) y verifica que el predicado de
    test_close_rect_is_full_height_strip lo rechaza."""
    x0, y0, x1, y1 = _old_pill_rect()
    ok = (x1 - x0 == wp.NotificationWidget._CLOSE_STRIP_W
          and (x0, y0, x1, y1) == (W - wp.NotificationWidget._CLOSE_STRIP_W, 0, W, H))
    assert not ok, (
        "Metatest: el pill 28x28 esquinado debe fallar el test de franja "
        "vertical; si no, el test es un placebo"
    )


def test_metatest_midcard_click_was_outside_old_pill():
    """El punto crítico (W-10, H/2) quedaba FUERA del pill viejo: es
    exactamente el misclick que abría el video. El test de cobertura debe
    exigir lo que el pill no cubría."""
    x0, y0, x1, y1 = _old_pill_rect()
    inside = x0 <= W - 10 <= x1 and y0 <= H / 2 <= y1
    assert not inside, (
        "Metatest: el click a mitad de card debe caer fuera del pill viejo "
        "(reproduce el bug real que motivó la franja)"
    )


def test_metatest_fullwidth_test_rejects_old_pill():
    """Simula el pill compacto de expandir (~90px a la derecha) y verifica
    que el predicado de test_expand_rect_is_full_width lo rechaza."""
    pill_w = 90
    old_x0 = (W - 14) - pill_w - 8
    old_x1 = W - 14
    assert not (old_x0 <= 14 + 2), (
        "Metatest: el pill compacto debe fallar el test de barra full-width"
    )
    assert old_x1 >= W - 14 - 2  # x1 sí llegaba: la sensibilidad está en x0


def test_metatest_source_has_zone_markers():
    """Los marcadores de la nueva geometría deben estar en el source (si
    alguien los quita, los spec tests de geometría fallan).

    Desde `bajar-complejidad-draw` los marcadores viven en los helpers del
    orquestador (`_draw_expand_bar`, `_frame`), no en `_draw`; se buscan en el
    source de toda la clase. La forma de `bar_x1` cambió con el NamedTuple del
    frame (`fr.W/fr.pad/fr.strip_w`), el invariante es el mismo: la barra
    termina antes del pad y de la franja de cierre."""
    src = inspect.getsource(wp.NotificationWidget)
    assert "self._expand_rect = (bar_x0, btn_y, bar_x1, btn_y + btn_h)" in src, (
        "Metatest: el hit-rect de expandir debe ser la barra full-width"
    )
    assert "bar_x1 = fr.W - fr.pad - fr.strip_w" in src, (
        "Metatest: la barra debe terminar antes del pad y de la franja de cierre"
    )
    assert "strip_w = self._strip_w()" in src, (
        "Metatest: la reserva del ancho de franja debe salir del gate "
        "hover-dependiente _strip_w (sin hover la franja no se dibuja y su "
        "ancho no se reserva)"
    )


def test_metatest_layout_reservation_propagates():
    """Si el wrap perdiera la reserva de la franja, el texto quedaría debajo
    del tinte al hacer hover. El predicado del test de reserva debe detectar
    el texto 44px más ancho."""
    wide = wp._count_body_lines("x" * 400, wp._CARD_WIDTH - 28, 13)
    narrow = wp._count_body_lines("x" * 400, wp._CARD_WIDTH - 28 - 44, 13)
    assert narrow > wide, (
        "Metatest: el wrap a 44px menos da más líneas; si el gate _strip_w "
        "dejara de descontarse, test_persistent_text_width_reserves_strip_only_"
        "on_hover lo detecta"
    )
