"""Iconos, URLs, códigos de verificación y portapapeles (sin GSK).

Extraído de `toast_window.py`: helpers de proceso, no del render.
"""
import os
import re
import subprocess
import configparser
import ctypes

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

# `_resample` vivía en el mismo módulo antes del split; sin este import el
# `except` de _get_app_icon_from_desktop escondía un NameError y el icono de
# archivo nunca se escalaba.
from toast_core import _resample

# ── Bundled font: Manrope (OFL) ──────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _register_bundled_font():
    """Registra los TTF de Manrope en fontconfig al importar (idempotente)."""
    try:
        fc = ctypes.CDLL("libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        # Sin restype c_void_p, ctypes trunca el puntero de 64 bits a int y
        # FcConfigAppFontAddFile segfaulta (GTK4 cambia el layout de memoria).
        fc.FcConfigGetCurrent.argtypes = []
        fc.FcConfigGetCurrent.restype = ctypes.c_void_p
        cfg = fc.FcConfigGetCurrent()
        for name in ("Manrope-Regular.ttf", "Manrope-Bold.ttf"):
            path = os.path.join(_FONT_DIR, name)
            if os.path.exists(path):
                fc.FcConfigAppFontAddFile(cfg, path.encode())
    except Exception:
        pass


_register_bundled_font()


_DESKTOP_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/local/share/applications",
    "/usr/share/applications",
]

_desktop_cache = None


def _rebuild_desktop_cache():
    global _desktop_cache
    _desktop_cache = {}
    for d in _DESKTOP_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            for f in os.listdir(d):
                if not f.endswith(".desktop"):
                    continue
                path = os.path.join(d, f)
                try:
                    cp = configparser.ConfigParser()
                    cp.read(path)
                    entry = {
                        "path": path,
                        "Name": cp.get("Desktop Entry", "Name", fallback=""),
                        "Icon": cp.get("Desktop Entry", "Icon", fallback=""),
                        "StartupWMClass": cp.get(
                            "Desktop Entry", "StartupWMClass", fallback=""),
                    }
                    stem = f[:-8].lower()
                    _desktop_cache.setdefault(stem, []).append(entry)
                    wm = entry["StartupWMClass"].lower()
                    if wm:
                        _desktop_cache.setdefault(wm, []).append(entry)
                    nm = entry["Name"].lower()
                    if nm:
                        _desktop_cache.setdefault(nm, []).append(entry)
                except Exception:
                    pass
        except Exception:
            pass


def _get_app_icon_from_desktop(app_name, size=80, mode="cover",
                               desktop_entry=None):
    """Icono de la app desde .desktop: primero `desktop-entry`, luego app_name."""
    path = _exact_desktop_file(app_name, desktop_entry)
    if not path:
        return None
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        icon_name = cp.get("Desktop Entry", "Icon", fallback="")
        if icon_name:
            if icon_name.startswith("/") and os.path.exists(icon_name):
                return _resample(
                    GdkPixbuf.Pixbuf.new_from_file(icon_name), size, mode=mode)
            return _icon_from_theme(icon_name, size)
    except Exception:
        pass
    return None


def _exact_desktop_file(app_name, desktop_entry=None):
    """Resuelve el .desktop con match EXACTO (stem/WMClass/Name), sin substring.

    `desktop-entry` es la fuente canónica del spec freedesktop y lo que Plasma
    usa (`KService::serviceByDesktopName`); `app_name` es sólo fallback.
    """
    candidatos = []
    for valor in (desktop_entry, app_name):
        if valor:
            valor = str(valor).strip().lower()
            if valor.endswith(".desktop"):
                valor = valor[:-8]
            if valor and valor not in candidatos:
                candidatos.append(valor)
    if not candidatos:
        return None
    if _desktop_cache is None:
        _rebuild_desktop_cache()
    for clave in candidatos:
        entries = _desktop_cache.get(clave)
        if entries:
            return entries[0]["path"]
    _rebuild_desktop_cache()
    for clave in candidatos:
        entries = _desktop_cache.get(clave)
        if entries:
            return entries[0]["path"]
    return None


def _get_app_display_name(app_name):
    """Nombre visible de la app (match exacto de .desktop, sino el raw)."""
    if not app_name:
        return ""
    path = _exact_desktop_file(app_name)
    if not path:
        return app_name
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        return cp.get("Desktop Entry", "Name", fallback=app_name)
    except Exception:
        return app_name


_URL_RE = re.compile(r'https?://[^\s<>"\'\)\]]+', re.IGNORECASE)
_BARE_HOST_RE = re.compile(
    r'(?<![\w./-])(?:[a-z][\w-]*\.)+[a-z]{2,}(?::\d+)?(?:/[^\s<>"\'\)\]]*)?'
    r'|\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/[^\s<>"\'\)\]]*)?',
    re.IGNORECASE,
)


def _strip_urls(text):
    """Quita URLs del TEXTO VISIBLE del body (el destino es para el click)."""
    if not text:
        return text
    parts = re.split(r'(<[^>]*>)', text)
    out = "".join(
        (_BARE_HOST_RE.sub("", _URL_RE.sub("", part))
         if not part.startswith("<") else part)
        for part in parts
    )
    out = re.sub(r'<a\s+[^>]*>\s*</a>', '', out)
    return re.sub(r'\n{2,}', '\n', out).strip("\n")


def _icon_from_theme(icon_name, size=16):
    """Icono del tema hicolor/Breeze por nombre (reintento en minúsculas)."""
    if not icon_name:
        return None
    attempts = [icon_name]
    lowered = icon_name.lower()
    if lowered != icon_name:
        attempts.append(lowered)
    for attempt in attempts:
        try:
            display = Gdk.Display.get_default()
            theme = (Gtk.IconTheme.get_for_display(display) if display
                     else Gtk.IconTheme.new())
            # GTK4: lookup_icon(nombre, fallbacks, size, scale, direction, flags)
            # GTK3 usaba lookup_icon(nombre, size, flags): llamarla así lanza
            # TypeError y el except de abajo escondía que NINGÚN icono resolvía.
            paintable = theme.lookup_icon(
                attempt, None, size, 1, Gtk.TextDirection.LTR,
                Gtk.IconLookupFlags.FORCE_REGULAR)
            if paintable:
                archivo = paintable.get_file()
                ruta = archivo.get_path() if archivo else None
                if ruta:
                    return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        ruta, size, size, True)
        except Exception:
            pass
    return None


# Patrones para copiar códigos de verificación SIN falsos positivos.
# Un número suelto no es un código: en el historial real hay años (1991),
# versiones (b200148) y menciones (@usuario4161). Solo contamos un número
# cuando una palabra de verificación aparece CERCA (misma frase, ±40 chars).
_CODE_WORDS = (
    r"c[oó]digo|verificaci[oó]n|confirmaci[oó]n|validaci[oó]n|"
    r"clave|pin|otp|c[oó]digo de acceso|codigo"
)
_CODE_RE = re.compile(
    r"(?<![\d/])(?P<code>\d{4,8})(?![\d/-])", re.UNICODE)
_CODE_CONTEXT_RE = re.compile(_CODE_WORDS, re.IGNORECASE | re.UNICODE)


def _find_code(text):
    """Devuelve el código de verificación del body, o None si no hay.

    Exige que una palabra clave de verificación esté a ±40 caracteres del
    número. Así un año ("Wyeth, 1991") o una versión ("b200148") no se
    confunden con un código.
    """
    if not text:
        return None
    for m in _CODE_RE.finditer(text):
        lo = max(0, m.start() - 40)
        hi = min(len(text), m.end() + 40)
        if _CODE_CONTEXT_RE.search(text[lo:hi]):
            return m.group("code")
    return None





def _copy_to_clipboard(text):
    """Copia al portapapeles sin robar foco (wl-copy en Wayland, xclip/xsel en X11).

    A diferencia de KDE (que necesita takeFocus para QClipboard), wl-copy
    habla con el compositor directamente: compatible con keyboard_mode=NONE.
    """
    if not text:
        return False
    if os.environ.get("WAYLAND_DISPLAY"):
        cmd = ["wl-copy", text]
    elif _tiene_comando("xclip"):
        cmd = ["xclip", "-selection", "clipboard"]
    else:
        cmd = ["xsel", "--clipboard", "--input"]
    try:
        if cmd[0] in ("xclip", "xsel"):
            subprocess.run(cmd, input=text, text=True, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, check=False, input=text, text=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _tiene_comando(nombre):
    """True si `nombre` está en PATH (sin lanzar nada)."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isfile(os.path.join(d, nombre)) and os.access(
                os.path.join(d, nombre), os.X_OK):
            return True
    return False


def _extract_markup_url(text):
    """Extrae el href del primer <a href="..."> en un body con markup."""
    if not text or "<a " not in text:
        return ""
    m = re.search(r'<a\s+[^>]*href=["\']([^"\']+)["\']', text, re.IGNORECASE)
    if m:
        url = m.group(1)
        if url.startswith(("http://", "https://", "mailto:", "tel:")):
            return url
    return ""


__all__ = ['browser_labels', '_BARE_HOST_RE', '_CODE_CONTEXT_RE', '_CODE_RE', '_CODE_WORDS', '_DESKTOP_DIRS', '_FONT_DIR', '_URL_RE', '_copy_to_clipboard', '_desktop_cache', '_exact_desktop_file', '_extract_markup_url', '_find_code', '_get_app_display_name', '_get_app_icon_from_desktop', '_icon_from_theme', '_rebuild_desktop_cache', '_register_bundled_font', '_strip_urls', '_tiene_comando']


def browser_labels(app_name, summary, body):
    """(línea de app, hide_title) para navegadores.

    Con body se pliega el título en "App - pestaña" para no duplicarlo. Sin
    body visible (vacío o solo URL sanitizada) el título vuelve a su fila:
    si no, la card queda con una sola línea y un hueco grande.
    """
    visible = (_strip_urls(body) or "").strip()
    if visible:
        return "{} - {}".format(app_name, summary), True
    return app_name, False
