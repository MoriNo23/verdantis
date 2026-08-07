"""
Tests de helpers de presentación de wayland_popup:
- _get_app_display_name: display name con match EXACTO, sin caer en PWA difusos.
- _strip_urls: el texto visible del body no muestra URLs (es un botón).
"""
import sys
import os

os.environ.setdefault("GDK_BACKEND", "wayland")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import wayland_popup as wp


# --- _get_app_display_name ---

def test_display_name_exact_match_returns_its_name(tmp_path, monkeypatch):
    # app_name coincide EXACTO con un stem → lee su Name del .desktop real
    df = tmp_path / "brave.desktop"
    df.write_text("[Desktop Entry]\nName=Brave Nightly\nIcon=x\nType=Application\n")
    monkeypatch.setattr(wp, "_desktop_cache", {
        "brave": [{"Name": "Brave Nightly", "path": str(df)}],
    })
    assert wp._get_app_display_name("Brave") == "Brave Nightly"


def test_display_name_no_fuzzy_pwa(monkeypatch):
    # PWA de Brave instaladas (brave-<appid>, ej "xat de masha"): el app_name
    # crudo "Brave" NO debe resolver difuso al PWA. Regla: match exacto o raw.
    monkeypatch.setattr(wp, "_desktop_cache", {
        # NO hay entrada exacta "brave"; solo PWA con prefijo brave-
        "brave-djgodba": [{"Name": "xat de masha", "path": "/x/pwa.desktop"}],
    })
    assert wp._get_app_display_name("Brave") == "Brave"


def test_display_name_empty(monkeypatch):
    monkeypatch.setattr(wp, "_desktop_cache", {})
    assert wp._get_app_display_name("") == ""


def test_display_name_roundtrip_ignores_cache_ok(monkeypatch):
    monkeypatch.setattr(wp, "_desktop_cache", None)
    # _desktop_cache=None hace rebuild real (lee el sistema); solo chequeamos que
    # devuelve algo y no crashea al mostrar un nombre desconocido.
    name = wp._get_app_display_name("AppQueNoExisteXYZ")
    assert name == "AppQueNoExisteXYZ"


# --- _strip_urls ---

def test_strip_urls_http():
    assert wp._strip_urls("Hola https://xat.com/chat verás") == "Hola  verás"


def test_strip_urls_www_upper_case():
    assert "http" not in wp._strip_urls("Ve HTTP://EJEMPLO.COM/a?b=1#c aquí")


def test_strip_urls_none_or_empty():
    assert wp._strip_urls("") == ""
    assert wp._strip_urls(None) is None


def test_strip_urls_preserves_normal_text():
    assert wp._strip_urls("plano sin urls") == "plano sin urls"


def test_strip_urls_keeps_href_attr():
    # El href es un atributo (no se dibuja); NO se borra ni rompe el markup
    body = 'Click <a href="https://github.com/MoriNo23/verdantis">here</a> ok'
    assert wp._strip_urls(body) == body


def test_strip_urls_removes_plain_url_but_keeps_tags():
    body = 'Ve https://xat.com/chat ahora  además <b>negrita</b>'
    assert wp._strip_urls(body) == "Ve  ahora  además <b>negrita</b>"


def test_strip_urls_bare_host_ip_port():
    # Brave inyecta el host del sitio como primera línea: hay que sacarlo
    body = '<a href="http://127.0.0.1:8766/">127.0.0.1:8766</a>\n\nClické el toast'
    assert wp._strip_urls(body) == "Clické el toast"


def test_strip_urls_bare_domain():
    assert wp._strip_urls("Mira xat.com ahora") == "Mira  ahora"
    assert wp._strip_urls("www.ejemplo.com/path?q=1") == ""


def test_strip_urls_collapses_newlines():
    assert wp._strip_urls("a\n\n\nb") == "a\nb"
    assert wp._strip_urls("\n\n\nx") == "x"


# --- Icono: SOLO match exacto (no cae en el PWA) ---

def test_app_icon_no_fuzzy_pwa(monkeypatch):
    # PWA brave-<appid> presente, app_name "Brave" sin match exacto → None (tema)
    monkeypatch.setattr(wp, "_desktop_cache", {
        "brave-djgodba": [{"Name": "xat de masha", "path": "/x/pwa.desktop", "Icon": "xat"}],
    })
    assert wp._get_app_icon_from_desktop("Brave", 16) is None


def test_app_icon_exact_match_uses_that_desktop(monkeypatch):
    monkeypatch.setattr(wp, "_desktop_cache", {
        "brave": [{"Name": "Brave", "path": "/x/brave.desktop", "Icon": "brave-icon"}],
    })
    # "brave-icon" no existe en el tema → None (pero el camino correcto: usa el
    # Icon del .desktop exacto, nunca el del PWA)
    assert wp._get_app_icon_from_desktop("Brave", 16) is None


def test_exact_desktop_file_helper():
    assert wp._exact_desktop_file("") is None
    assert wp._exact_desktop_file(None) is None


# --- Sanitize: <a href> se renderiza plano (el toast es el botón) ---

def test_sanitize_strips_link_markup_keeps_label():
    out = wp._sanitize_pango_markup('<a href="https://x.com">Abrir página</a>')
    assert out == "Abrir página"
    assert "<a" not in out and "underline" not in out and "span" not in out


def test_sanitize_keeps_bold_and_plain():
    assert wp._sanitize_pango_markup("<b>Negrita</b> y plano") == "<b>Negrita</b> y plano"
    assert wp._sanitize_pango_markup("plano") == "plano"