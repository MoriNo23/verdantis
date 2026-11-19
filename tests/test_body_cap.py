"""El body dibujado respeta el mismo cap que medimos para la altura."""
import toast_core as tc


def test_layout_dibujado_capea_tres_lineas():
    cuerpo = ("Notificacion Seniat from No responder\n\n"
              "logo Estimado contribuyente, ANTHONY JERUAN Perez "
              "y mucho mas texto para pasar de tres lineas clarified.")
    lay = tc._body_layout(cuerpo, 12, 212, max_lines=3)
    assert lay.get_line_count() <= 3, (
        "medimos 3 lineas pero dibujamos %d" % lay.get_line_count())


def test_jerarquia_titulo_body_con_dos_px_de_diferencia():
    assert tc._TITLE_FS - tc._BODY_FS >= 2
