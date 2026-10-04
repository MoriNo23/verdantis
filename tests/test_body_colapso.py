"""
Spec `toast-body-colapso`: el cap de líneas del body se presupuesta con la
altura REAL de la línea, no con una aproximación por tamaño de fuente.

RED (bug 0.8.0 → fix 0.8.1): el presupuesto era
`max_lines × int(font_size × 1.6)` — 17.6 px por línea con la body font 11 —
cuando la línea lógica real de Manrope 11 mide **21 px**. El presupuesto
quedaba siempre ~una línea corto y Pango cortaba antes de tiempo:

  * un body de EXACTAMENTE 2 líneas se dibujaba con 1 línea + "..." — y sin
    botón "Ver más" (el cap no lo declaraba overflow), así que la 2ª línea
    quedaba ilegible y sin forma de llegar;
  * un body con overflow mostraba 2 líneas + "..." en vez de las 3 del cap.

Cómo miden estos tests: por PÍXELS. `_body_bands` renderiza el toast headless y
devuelve las bandas de tinta del BODY (filas con píxeles del color `_left_body`
dentro de la columna de texto, agrupadas en renglones). El número de bandas ES
el número de líneas dibujadas, y la tinta de cada banda se compara contra el
MISMO body renderizado COMPLETO (`expanded=True`): si el cap recortara antes de
la última línea del cap, las bandas superiores no coincidirían.

La región escaneada termina donde arranca la barra "Ver más" (o en el padding
inferior sin barra), NO en la altura medida del body — medir la zona con el
valor bajo prueba dejaría el test Circular.
"""

import inspect

import pytest

import wayland_popup as wp
from render_helpers import alloc_and_draw, surface_pixels

W = 360                               # ancho del card
BODY_RGB = wp._hex_rgb("#cdd6f4")     # `_left_body`: la tinta del body
TOL = 12                              # separado de `_left_title` (el título)
ROW_GAP = 2                           # filas vacías que cortan una banda

# Body REAL del historial que reporta el bug: 2 líneas a la columna única de
# 240 con la body font de producción. Sin overflow → sin botón "Ver más".
TWO_LINES = "Conexión «pvpn-killswitch» activada."

# Body REAL del historial (xat) que desborda el cap de 3 líneas: 6 naturales.
OVERFLOW = ("Bienvenido Larp a Capuchino. Un pequeño espacio donde trataremos "
            "de temas variados en un circulo amistoso. Disfruten su estancia !! "
            "El Ultimo power fue Twenty")

ONE_LINE = "Conexión estable"


def _es_tinta(px, x, y):
    r, g, b, _a = px[y][x]
    return (abs(r - BODY_RGB[0] * 255) <= TOL
            and abs(g - BODY_RGB[1] * 255) <= TOL
            and abs(b - BODY_RGB[2] * 255) <= TOL)


def _body_bands(cuerpo, font_scale=1.0, expanded=False, app="App"):
    """Render headless del toast → (widget, alto_card, bandas, geometría).

    Cada banda es `(primera_fila, última_fila, x_izq, x_der)` de la tinta del
    body: un renglón dibujado. `font_scale` se fija explícitamente (en vez de
    heredar la resolución de la pantalla del runner) para que el presupuesto
    del cap sea el mismo en cualquier máquina.
    """
    w = wp.NotificationWidget(app, "", "Titulo", cuerpo, None, None, "#80cbc4")
    w._font_scale = font_scale
    w._expanded = expanded
    h = w.desired_height()
    px = surface_pixels(alloc_and_draw(w, W, h))
    x0 = wp._PAD + wp._IMAGE_LEFT_W + wp._IMAGE_LEFT_GAP
    col_w = W - x0 - wp._PAD - w._strip_w()
    top = wp._PAD + wp._rows_above_body(app, w._hide_title)
    # El cuerpo no puede invadir la barra "Ver más": el scan termina donde la
    # barra empieza (o en el padding inferior si no hay barra).
    bottom = w._expand_rect[1] if w._expand_rect else h - wp._PAD
    bands = []
    for y in range(top, bottom):
        xs = [x for x in range(x0, x0 + col_w) if _es_tinta(px, x, y)]
        if not xs:
            continue
        if bands and y - bands[-1][1] <= ROW_GAP:
            bands[-1][1] = y
            bands[-1][3] = max(bands[-1][3], xs[-1])
        else:
            bands.append([y, y, xs[0], xs[-1]])
    return w, h, [tuple(b) for b in bands], (x0, top, col_w)


def _body_fs(font_scale):
    """El tamaño de body que dibuja el widget con esa escala (constante del
    módulo `_BODY_FS`, la fuente única que también mide `calc_card_height`)."""
    return max(9, round(wp._BODY_FS * font_scale))


def _real_line_h(cuerpo, col_w, font_scale):
    """Altura lógica REAL de la línea del font renderizado (referencia).

    Mide un layout SIN cap —la misma fuente, ancho y wrap que dibuja el body—
    porque el PRESUPUESTO es justamente lo que el contrato pone a prueba. Es
    la altura que el diseño D1 declara como única autoridad del cap.
    """
    from gi.repository import Pango, PangoCairo
    ctx = Pango.Context()
    ctx.set_font_map(PangoCairo.font_map_get_default())
    layout = Pango.Layout(ctx)
    layout.set_font_description(
        Pango.FontDescription("Manrope " + str(_body_fs(font_scale))))
    layout.set_text(wp._sanitize_pango_markup(cuerpo), -1)
    layout.set_width(int(col_w * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    return layout.get_line_readonly(0).get_pixel_extents()[1].height


# ---------------------------------------------------------------------------
# Requirement: El body sin overflow se muestra completo
# ---------------------------------------------------------------------------

def test_body_de_exactamente_dos_lineas_se_muestra_completo():
    """Scenario "Body de exactamente dos líneas": las dos se ven enteras.

    Con el presupuesto heurístico (17.6 px/línea) el cap de 2 líneas (35.2 px)
    no alcanzaba ni una línea real (21 px): Pango colapsaba el texto a 1 línea +
    "..." y, como el cap no lo declaraba overflow, el toast salía SIN botón
    "Ver más" — la 2ª línea, ilegible y sin forma de llegar.
    """
    assert wp._count_body_lines(TWO_LINES, wp._TEXT_COL_W, wp._BODY_FS) == 2, (
        "el cuerpo del test debe wrappear a EXACTAMENTE 2 líneas en la columna "
        "de %d px con la body font %d" % (wp._TEXT_COL_W, wp._BODY_FS)
    )
    w, h, bands, _ = _body_bands(TWO_LINES)
    _, h_full, full, _ = _body_bands(TWO_LINES, expanded=True)
    assert len(bands) == 2, (
        "las 2 líneas del body deben dibujarse completas; se dibujaron %d "
        "(bands=%s) — el cap cortó antes de tiempo" % (len(bands), bands)
    )
    assert bands == full, (
        "sin overflow el body debe ser IDÉNTICO al render completo (sin \"...\" "
        "ni recorte): colapsado=%s completo=%s" % (bands, full)
    )
    assert w._expand_rect is None, (
        "un body de 2 líneas no tiene nada que expandir: no debe haber barra "
        "\"Ver más\" (rect=%s)" % (w._expand_rect,)
    )
    assert h == h_full, (
        "sin \"...\" ni botón la card colapsada mide lo mismo que la completa: "
        "%s vs %s" % (h, h_full)
    )


def test_body_de_una_linea_se_muestra_entero():
    """Scenario "Body de una línea": entero, sin "..." ni botón."""
    w, h, bands, _ = _body_bands(ONE_LINE)
    _, h_full, full, _ = _body_bands(ONE_LINE, expanded=True)
    assert len(bands) == 1, (
        "un body de una línea se dibuja en un solo renglón: %s" % (bands,)
    )
    assert bands == full, (
        "sin overflow el body debe ser IDÉNTICO al render completo: %s vs %s"
        % (bands, full)
    )
    assert w._expand_rect is None, (
        "un body de una línea no tiene nada que expandir: no debe haber barra"
    )
    assert h == h_full


# ---------------------------------------------------------------------------
# Requirement: El ellipsis cae tras el número exacto de líneas del cap
# ---------------------------------------------------------------------------

def test_overflow_dibuja_las_tres_lineas_del_cap():
    """Scenario "Body largo con overflow": 3 líneas completas + botón."""
    cap = wp.NotificationWidget._MAX_VISIBLE_LINES
    assert wp._count_body_lines(OVERFLOW, wp._TEXT_COL_W, wp._BODY_FS) > cap, (
        "el cuerpo del test debe desbordar el cap de %d líneas" % cap
    )
    w, _h, bands, _ = _body_bands(OVERFLOW)
    _, _, full, _ = _body_bands(OVERFLOW, expanded=True)
    assert len(full) > cap, (
        "el render completo debe tener más de %d renglones: %s" % (cap, full)
    )
    assert len(bands) == cap, (
        "con overflow el cap dibuja sus %d líneas completas; se dibujaron %d "
        "(bands=%s) — el presupuesto del cap cortó una línea antes de tiempo"
        % (cap, len(bands), bands)
    )
    assert w._expand_rect is not None, (
        "el body desborda el cap: la barra \"Ver más\" debe estar"
    )
    # Las 3 líneas del cap caen donde caen las 3 primeras del render completo:
    # el cap muestra las mismas líneas enteras, no otras más apretadas.
    assert [b[0] for b in bands] == [b[0] for b in full[:cap]], (
        "las líneas del cap deben ocupar la posición de las %d primeras del "
        "body completo: %s vs %s" % (cap, bands, full[:cap])
    )


def test_el_ellipsis_cae_al_final_de_la_tercera_linea():
    """Scenario "El ellipsis nunca aparece antes": el corte es en la 3ª línea.

    El contrato observable es qué se ve: las 2 primeras líneas del cap deben ser
    IDÉNTICAS a las del render completo (nada se recortó antes de la última
    línea del cap) y la 3ª debe arrancar donde arranca su renglón natural — o
    sea, el corte cae DENTRO de la tercera línea, no antes.

    Dónde pone Pango el "..." dentro de esa línea lo decide el propio Pango: el
    código le pide `EllipsizeMode.END` sobre el cap, así que el marcador cae al
    final de la última línea dibujada por construcción. Eso se fija abajo con
    los marcadores del fuente; medir la tinta del glifo "…" pixel a pixel no
    distingue nada (a 11 px los puntos del glifo son del mismo color que los
    trazos de una letra).
    """
    cap = wp.NotificationWidget._MAX_VISIBLE_LINES
    _w, _h, bands, _ = _body_bands(OVERFLOW)
    _, _, full, _ = _body_bands(OVERFLOW, expanded=True)
    assert bands[:2] == full[:2], (
        "las 2 primeras líneas del cap deben ser idénticas a las del body "
        "completo (el \"...\" no puede caer antes): %s vs %s"
        % (bands[:2], full[:2])
    )
    assert bands[2][0] == full[2][0] and bands[2][2] == full[2][2], (
        "la 3ª línea es la misma 3ª línea del body completo y arranca en el "
        "mismo punto (el corte cae en su cola): %s vs %s"
        % (bands[2], full[2])
    )
    assert len(bands) == cap < len(full), (
        "el cap dibuja %d de las %d líneas naturales: el corte es en la última "
        "del cap" % (len(bands), len(full))
    )
    for fn in (wp._body_metrics, wp.NotificationWidget._draw_text):
        src = inspect.getsource(fn)
        assert "set_ellipsize(Pango.EllipsizeMode.END)" in src, (
            "%s debe pedir el ellipsis al FINAL de la última línea dibujada "
            "(EllipsizeMode.END): con otro modo el \"...\" caería en otro "
            "lugar" % fn.__name__
        )


# ---------------------------------------------------------------------------
# Requirement: La altura de la card coincide con lo dibujado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("font_scale", [0.85, 1.0])
def test_altura_reservada_del_body_coincide_con_lo_dibujado(font_scale):
    """Scenarios "Sin hueco ni solape" + "Coherencia en cualquier escala".

    Lo reservado (de la barra hacia arriba) es exactamente N × la altura real
    de línea, y lo dibujado ocupa esa misma región: la barra ancla justo bajo
    la última línea, sin franja vacía y sin pisar el texto. Se corre con dos
    escalas (body 9 y body 11) porque el bug era proporcional al font.
    """
    w, h, bands, (_x0, top, col_w) = _body_bands(OVERFLOW, font_scale=font_scale)
    cap = wp.NotificationWidget._MAX_VISIBLE_LINES
    line_h = _real_line_h(OVERFLOW, col_w, font_scale)
    reservado = w._expand_rect[1] - wp._BTN_GAP - top
    assert reservado == cap * line_h, (
        "lo reservado para el body debe ser %d × la altura real de línea "
        "(%d px, font_scale %s); se reservaron %d px"
        % (cap, line_h, font_scale, reservado)
    )
    assert len(bands) == cap, (
        "lo dibujado (%d renglones) debe llenar lo reservado (%d px = %d "
        "líneas)" % (len(bands), reservado, cap)
    )
    assert bands[-1][1] < w._expand_rect[1], (
        "solape: la última línea del body (%d) entra en la barra \"Ver más\" "
        "(%d)" % (bands[-1][1], w._expand_rect[1])
    )
    # La tinta no llena los renglones de punta a punta (interlineado arriba y
    # abajo), pero lo que sobra bajo la última línea no puede sumar un
    # renglón entero: eso sería una franja vacía entre el texto y la barra.
    tinta = bands[-1][1] - bands[0][0] + 1
    assert reservado - tinta <= line_h, (
        "franja vacía: entre la última línea dibujada (%d) y el final de lo "
        "reservado (%d) sobra más de un interlineado (%d)"
        % (bands[-1][1], top + reservado, line_h)
    )
    assert h == wp.WaylandPopup.calc_card_height(
        "App", OVERFLOW, "", font_scale=font_scale), (
        "desired_height y calc_card_height deben coincidir también con "
        "overflow: %s vs %s" % (h, wp.WaylandPopup.calc_card_height(
            "App", OVERFLOW, "", font_scale=font_scale))
    )