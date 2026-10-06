"""
La métrica de layout del card, testeada SIN display.

`_layout_metrics` (change `bajar-complejidad-draw`) es la aritmética del stack
que antes vivía en el medio de `_draw` — 338 líneas donde la métrica era
inalcanzable sin montar un widget y un cairo. Al ser pura (no toca cairo ni el
widget), se verifica directo: sin display, sin píxeles, sin render.

Estos asserts fijan las cuatro propiedades de las que depende el dibujado:

- el cap de líneas corta exacto (`cap` = min(natural, MAX_VISIBLE_LINES));
- `has_more` solo con overflow real, y persiste al expandir (para poder
  contraer);
- el piso de la columna nunca es menor que el slot de 80 px (spec
  `toast-imagen-izquierda`: la imagen siempre tiene que caber);
- `bands_h` suma la barra "Ver más" y la fila de botones solo cuando existen.
"""

import wayland_popup as wp

CUERPO_CORTO = "Conexión «pvpn-killswitch» activada."
CUERPO_LARGO = ("Bienvenido Larp a Capuchino. Un pequeño espacio donde trataremos "
                "de temas variados en un circulo amistoso. Disfruten su estancia "
                "!! El Ultimo power fue Twenty")


def _lay(cuerpo=CUERPO_CORTO, col=240, fs=11, app_name="xat-notifier",
         hide_title=False, expanded=False, has_actions=False,
         icon_size=wp._IMAGE_LEFT_W, max_lines=3):
    return wp._layout_metrics(
        cuerpo=cuerpo, text_col_w=col, body_fs=fs, app_name=app_name,
        hide_title=hide_title, expanded=expanded, has_actions=has_actions,
        icon_size=icon_size, max_lines=max_lines, btn_h=wp.NotificationWidget._BTN_H,
    )


def test_cap_corta_exacto_el_body():
    """`cap` es el número de renglones visibles: min(naturales, MAX)."""
    corto = _lay(CUERPO_CORTO)
    assert corto.cap == min(corto.total_lines, 3)
    largo = _lay(CUERPO_LARGO)
    assert largo.total_lines > 3, "el cuerpo del test tiene que desbordar el cap"
    assert largo.cap == 3, "con overflow el cap muestra exactamente MAX líneas"


def test_has_more_solo_con_overflow():
    """`has_more` (barra "Ver más") solo con overflow, y en ambos estados.

    Sin overflow no hay barra. Con overflow, expandido también: el botón tiene
    que seguir ahí para poder CONTRACTIR de nuevo.
    """
    assert _lay(CUERPO_CORTO).has_more is False
    assert _lay(CUERPO_LARGO, expanded=True).has_more is True
    assert _lay(CUERPO_LARGO).has_more is True


def test_expandido_muestra_el_body_entero():
    """Expandido, el body ocupa su alto natural (no el cappeado)."""
    col, fs = 240, 11
    _, natural_h = wp._body_metrics(CUERPO_LARGO, col, fs, max_lines=None)
    assert _lay(CUERPO_LARGO, expanded=True).body_h == natural_h
    # Y colapsado es estrictamente más corto: el cap está haciendo algo.
    assert _lay(CUERPO_LARGO).body_h < natural_h


def test_piso_nunca_menor_que_el_slot():
    """La columna de texto nunca es más baja que el slot de 80 px.

    Spec `toast-imagen-izquierda`: la imagen tiene que caber antes de la primera
    banda. Con un cuerpo de UNA línea el texto (22 + 21 = 43 px) es más corto que
    el slot, así que el piso lo manda el slot; con más texto el piso es el bloque.
    """
    una_linea = _lay("hola")          # 1 línea natural
    assert una_linea.total_lines == 1
    assert una_linea.piso == wp._IMAGE_LEFT_W, (
        "con una sola línea el piso lo manda el slot de %d px (el bloque de "
        "texto mide %d)" % (wp._IMAGE_LEFT_W, una_linea.content_h)
    )
    largo = _lay(CUERPO_LARGO)
    assert largo.piso == largo.content_h > wp._IMAGE_LEFT_W, (
        "con overflow el piso es el bloque de texto, no el slot"
    )
    # Y el caso intermedio: 2 líneas de body ya miden 84 px, más que el slot.
    dos_lineas = _lay(CUERPO_CORTO)
    assert dos_lineas.total_lines == 2
    assert dos_lineas.piso == dos_lineas.content_h == 84


def test_bands_h_suma_barra_y_fila_de_botones():
    """`bands_h` = barra "Ver más" (solo con overflow) + fila de botones."""
    btn = wp.NotificationWidget._BTN_H
    assert _lay(CUERPO_CORTO).bands_h == 0, "sin overflow no hay barra"
    sin_acc = _lay(CUERPO_LARGO)
    assert sin_acc.bands_h == btn + wp._BTN_GAP
    con_acc = _lay(CUERPO_LARGO, has_actions=True)
    assert con_acc.bands_h == sin_acc.bands_h + wp._ACTIONS_ROW_H + wp._ACTIONS_GAP


def test_text_h_y_row_h_encadenan():
    """La cadena del stack: piso → bandas → piso de fila."""
    lay = _lay(CUERPO_LARGO, has_actions=True)
    assert lay.text_h == lay.piso + lay.bands_h
    assert lay.row_h == max(lay.text_h, wp._ROW_MIN_H)