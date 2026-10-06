"""
La métrica del widget y la altura que la card reserva son EL MISMO número.

`_layout_metrics` (lo que `_draw` usa para posicionar) y
`WaylandPopup.calc_card_height` (lo que `desired_height` y el stack manager
usan para reservar) recalculan el stack por separado. El change
`bajar-complejidad-draw` no las unifica (non-goal explícito: el radio de
impacto es `desired_height` + el stack manager + el dashboard), así que este
test es la red que vigila que no diverjan — la divergencia es exactamente el
bug de "la barra flota 8px sobre el padding" que `test_layout_consistency.py`
cazó una vez.

La coincidencia se exige sobre una matriz de cuerpos (1 línea, 2, overflow,
expandido), de flags (app_name, hide_title) y de escalas de fuente: si alguien
toca la fórmula en un lado y no en el otro, algún caso de la matriz lo nombra.
"""

import pytest

import wayland_popup as wp

W = wp._TEXT_COL_W       # 240: la columna única

UNA_LINEA = "hola"
DOS_LINEAS = "Conexión «pvpn-killswitch» activada."
LARGO = ("Bienvenido Larp a Capuchino. Un pequeño espacio donde trataremos de "
         "temas variados en un circulo amistoso. Disfruten su estancia !! El "
         "Ultimo power fue Twenty")


def _row_h_de_calc(app, cuerpo, expanded, hide_title, font_scale, actions):
    """Lo que la card reserva, sin el padding vertical ni el banner."""
    h = wp.WaylandPopup.calc_card_height(
        app, cuerpo, "", text_width=W, expanded=expanded,
        hide_title=hide_title, font_scale=font_scale,
        actions_count=len(actions) if actions else 0,
    )
    return h - wp._PAD - wp._PAD


def _row_h_de_metrics(app, cuerpo, expanded, hide_title, font_scale, actions):
    """Lo que el dibujado va a usar, por la vía de la métrica pura."""
    body_fs = max(9, round(wp._BODY_FS * font_scale))
    return wp._layout_metrics(
        cuerpo=cuerpo, text_col_w=W, body_fs=body_fs, app_name=app,
        hide_title=hide_title, expanded=expanded, has_actions=bool(actions),
        icon_size=wp._IMAGE_LEFT_W,
        max_lines=wp.NotificationWidget._MAX_VISIBLE_LINES,
        btn_h=wp.NotificationWidget._BTN_H,
    ).row_h


@pytest.mark.parametrize("cuerpo,expandido", [
    (UNA_LINEA, False), (UNA_LINEA, True),
    (DOS_LINEAS, False), (DOS_LINEAS, True),
    (LARGO, False), (LARGO, True),
])
@pytest.mark.parametrize("app,hide_title", [("xat-notifier", False), ("", False),
                                            ("Brave", True)])
@pytest.mark.parametrize("font_scale", [0.85, 1.0])
def test_lo_que_reserva_y_lo_que_dibuja_coinciden(cuerpo, expandido, app,
                                                  hide_title, font_scale):
    """El stack de `calc_card_height` y el de `_layout_metrics` son el mismo."""
    reservado = _row_h_de_calc(app, cuerpo, expandido, hide_title, font_scale, None)
    dibujado = _row_h_de_metrics(app, cuerpo, expandido, hide_title, font_scale, None)
    assert reservado == dibujado, (
        "la card reserva %s px pero el dibujado usa %s px (app=%r, expandido=%s, "
        "font_scale=%s, cuerpo=%r...): la fórmula divergió"
        % (reservado, dibujado, app, expandido, font_scale, cuerpo[:30])
    )


def test_la_coincidencia_tambien_con_actions():
    """La fila de botones suma igual en ambas vías."""
    for cuerpo in (UNA_LINEA, LARGO):
        for expanded in (False, True):
            reservado = _row_h_de_calc("xat-notifier", cuerpo, expanded, False,
                                       1.0, ["default", "Abrir"])
            dibujado = _row_h_de_metrics("xat-notifier", cuerpo, expanded, False,
                                         1.0, ["default", "Abrir"])
            assert reservado == dibujado, (
                "con actions la card reserva %s px y el dibujado usa %s px "
                "(cuerpo=%r, expandido=%s)" % (reservado, dibujado, cuerpo[:30],
                                               expanded)
            )