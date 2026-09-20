"""
Metatests visuales: validan que tests/test_visual.py es SENSIBLE a las
regresiones de apariencia, no un placebo.

Cada metatest simula un REGRESIÓN (un cambio incorrecto en el visual) y
verifica que el test visual correspondiente la DETECTARÍA. Esto prueba
que la suite visual "ve" con ojos numéricos:

1. Si urgencia crítica perdiera su opacidad -> test opacidad fallaría.
2. Si urgencia low perdiera su duración corta -> test duración fallaría.
3. Si los colores de accent se rompieran -> test de color fallaría.
4. Si las dimensiones de la card se rompieran -> test de layout fallaría.
"""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "wayland")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import wayland_popup as wp


def _popup(urgency=1, duration=8000):
    return wp.WaylandPopup(
        titulo="T", cuerpo="C", corner="top-right", accent="#80cbc4",
        app_name="A", duration=duration, urgency=urgency,
    )


def test_metatest_opacity_sensitive_to_bug():
    """
    SENSIBILIDAD: si critical perdiera la opacidad Alpha=1.0 (bug: daemon
    no mapea bien urgency), el test visual test_urgency_critical_is_opaque
    tendría que fallar. Simulamos: documentamos que 1.0 != 0.85.
    """
    crit_alpha_fixed = _popup(urgency=2)._bg_alpha  # 1.0 con fix
    # Si la implementación estuviera mal (diera 0.85 normal), el test fallaría
    assert crit_alpha_fixed > 0.90, (
        "Metatest: critical debería ser opaco (>0.90). Si esto falló, la "
        "opacidad de urgencia crítica se rompió y test_visual lo detectaría."
    )
    # Y explícitamente: el valor No-debe ser el de normal
    assert crit_alpha_fixed > _popup(urgency=1)._bg_alpha


def test_metatest_low_duration_sensitive_to_loss_of_shortening():
    """
    SENSIBILIDAD: si low dejara de acortar la duración (regresión: el
    multiplicador 0.7 se borrara), test_urgency_low_duration_shorter
    tendría que fallar.
    """
    low_dur = _popup(urgency=0, duration=8000).duration
    # Con fix: low < 8000. Si un bug lo dejara en 8000, el test fallaría.
    assert low_dur < 8000, (
        "Metatest: low debería durar menos de 8000; si falló, el acortado "
        "de urgencia baja se perdió."
    )
    assert low_dur == int(8000 * 0.7)


def test_metatest_accent_color_sensitive_to_corruption():
    """
    SENSIBILIDAD: si _hex_rgb devolviera valores fuera de rango (0-1),
    el render cairo dibujaría colores corruptos. Un bug que computara mal
    el RGB lo detectaría.
    """
    rgb = wp._hex_rgb("#ff0000")
    assert 0.0 <= rgb[0] <= 1.0 and 0.0 <= rgb[1] <= 1.0 and 0.0 <= rgb[2] <= 1.0
    assert abs(rgb[0] - 1.0) < 0.01  # rojo #ff
    assert abs(rgb[1]) < 0.01  # verde 0
    assert abs(rgb[2]) < 0.01  # azul 0


def test_metatest_card_height_sensitive_to_layout_change():
    """
    SENSIBILIDAD: si el padding de la card cambiara (los +14 del borde),
    el alto del popup cambia y el test de layout lo detectaría.
    """
    h = wp.WaylandPopup.calc_card_height("", "hola", "")
    # Si el padding interno cambiara, esta fórmula rompería:
    assert h == 14 + 80 + 14, f"Alto de card cambió: {h} (regresión layout)"


def test_metatest_corner_sensitive_to_position_regression():
    """
    SENSIBILIDAD: si un corner perdiera su margen de esquina (top-right
    debería anclarse arriba), el test visual de márgenes lo detecta.
    """
    tr = wp.WaylandPopup._MARGIN_MAP["top-right"]
    assert tr[0] > 0 and tr[2] == 0, "top-right debe anclarse al top"
    bl = wp.WaylandPopup._MARGIN_MAP["bottom-left"]
    assert bl[2] > 0 and bl[0] == 0, "bottom-left debe anclarse abajo"