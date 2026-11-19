"""El icono del systray es la marca verde esmeralda, no la "V" dibujada a mano."""
import systray


def test_pixmap_es_la_marca_esmeralda():
    ancho, alto, pixeles = systray._pixmap_verdantis(48)[0]
    assert (ancho, alto) == (48, 48)
    assert len(pixeles) == 48 * 48 * 4
    # Cairo entrega ARGB32 en memoria little-endian: B,G,R,A. La marca usa
    # esmeralda (R~16 G~185 B~129), no el teal viejo de la "V" (B~196).
    assert any(pixeles[i] < 120 and pixeles[i + 1] > 140 and pixeles[i + 2] < 170
               for i in range(0, len(pixeles), 4))
