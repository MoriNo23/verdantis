"""La surface agrandada por la sombra debe ser transparente afuera de la card.

Si la ventana layer-shell conserva el fondo opaco del tema, se ve un bloque
negro rectangular detrás del toast (el "fondo negro" que tapaba la sombra).
"""
import toast_window as wp


def test_css_de_ventana_hace_transparente_fuera_de_la_card(monkeypatch):
    vistos = []
    monkeypatch.setattr(wp, "_CSS_YA_PUESTO", False)
    monkeypatch.setattr(
        wp.Gtk.StyleContext, "add_provider_for_display",
        lambda display, provider, priority: vistos.append(provider.to_string()))
    monkeypatch.setattr(wp.Gdk, "Display", type("D", (), {
        "get_default": staticmethod(lambda: object())}))
    wp._add_window_css()
    # GTK normaliza `transparent` a rgba(0,0,0,0) al serializar el provider.
    assert any("rgba(0,0,0,0)" in css for css in vistos), vistos
