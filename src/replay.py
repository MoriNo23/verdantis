"""Replay del historial por CLI: `list`, `replay` y `clear`.

El replay NO pasa por el bus: reconstruye el toast con el render real
(`WaylandPopup` o el fallback X11, la misma elección de rama que el one-shot)
directo desde `history.jsonl`. Consecuencias deliberadas: no re-archiva (el
historial no se infla), no lo filtra el dedup del daemon y funciona aunque
verdantis no sea el dueño de `org.freedesktop.Notifications`. A cambio, click
y cierre no emiten señales (no hay sender): el click abre la URL con
`xdg-open` como en cualquier one-shot.

Los imports de gi son perezosos a propósito: `list` y `clear` no tocan display.
"""
import os
import subprocess
import sys
import time

import history_store
import app_info

# Parámetros que el fallback X11 acepta: su __init__ no conoce urgency ni
# actions (el replay por X11 pierde urgencia y botones — el fallback es
# minimal a propósito, un solo toolkit en el proyecto), pero sí el click
# de la URL (spec `replay`: igual comportamiento en ambos backends).
_X11_KEYS = ("titulo", "cuerpo", "icon_path", "image_path", "duration",
             "margin", "corner", "accent", "app_name", "app_icon",
             "on_click", "buttons_actionable")

# Default de duración del server cuando el registro no la trae (spec 1.2:
# expire_timeout < 0 → default del server). Espeja el 6000 del daemon.
_DURATION_DEFAULT = 6000


def seleccionar(records, last=5, app=None, id=None):
    """Registros a mostrar, en orden de llegada (más viejo primero).

    `id` es filtro exacto y gana sobre `last`, y toma el ÚLTIMO match: los ids
    se repiten (cada reinicio del daemon resetea el contador) y `--id 5` puede
    tener decenas de coincidencias en el JSONL. `app` filtra por subcadena
    (case-insensitive) y `last` recorta a los N más recientes."""
    if id is not None:
        return [r for r in records if r.get("id") == id][-1:]
    out = records
    if app:
        out = [r for r in out
               if app.lower() in (r.get("app_name") or "").lower()]
    return out[-last:] if last else out


def _click_abre_url(url):
    """Callback de click del replay: abre la URL archivada con `xdg-open` y
    pide el cierre retornando True — no hay daemon que cierre por él
    (el callback del daemon retorna None; ver `WaylandPopup._on_button_press`)."""
    def cb(key=None):
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return True
    return cb


def record_a_kwargs(record, duration=None):
    """Registro del JSONL → kwargs del popup (mismo shape que el daemon).

    `avatar_file` es el PNG archivado de la imagen izquierda (en /tmp vive lo
    que la sesión quiso); si no está, el popup resuelve icono de app o
    placeholder por su cuenta. `duration` pisa la archivada (los persistentes
    traen 0 y se quedarían en pantalla hasta que los cierres)."""
    hints = record.get("hints") or {}
    app_name = record.get("app_name") or ""
    summary = record.get("summary") or ""

    icon_path = None
    fname = record.get("avatar_file")
    if fname:
        ruta = history_store.icon_path(fname)
        if os.path.exists(ruta):
            icon_path = ruta
    banner_path = None
    bname = record.get("banner_file")
    if bname:
        ruta = history_store.icon_path(bname)
        if os.path.exists(ruta):
            banner_path = ruta

    try:
        urgency = int(hints.get("urgency", 1))
    except (TypeError, ValueError):
        urgency = 1
    if urgency not in (0, 1, 2):
        urgency = 1

    d = record.get("duration")
    if duration is not None:
        d = duration
    if not isinstance(d, int):
        d = _DURATION_DEFAULT

    url = record.get("url") or ""
    # Import perezoso: la detección de navegador y la defensa de URLs locales
    # viven en el daemon (que sí importa gi) y el replay ya paga gi al dibujar,
    # pero `list`/`clear` no tocan display.
    from verdantis_daemon import _is_browser, _is_local_url
    if url and _is_local_url(url):
        url = ""

    kwargs = {
        "titulo": summary,
        "cuerpo": record.get("body") or "",
        "icon_path": icon_path,
        "image_path": banner_path,
        "duration": d,
        "urgency": urgency,
        "app_name": app_name,
        "app_icon": record.get("app_icon") or "",
        "actions": record.get("actions") or [],
        "accent": hints.get("accent", app_info.DEFAULT_ACCENT),
        # Sin sender no hay señales. Con URL archivada el click abre y pide
        # cierre (True); sin URL es None: ningún cursor que mienta.
        "on_close": None,
        "on_click": _click_abre_url(url) if url else None,
        # Los botones reproducidos renderizan por fidelidad, no ejecutan.
        "buttons_actionable": False,
    }
    if _is_browser(app_name, hints.get("desktop-entry", "")):
        # Misma regla que el daemon: "Brave - <tab>" y el título se pliega ahí.
        kwargs["app_label"] = "{} - {}".format(app_name, summary)
        kwargs["hide_title"] = True
    return kwargs


def mostrar_toast(kwargs, force_wayland=False, force_fallback=False):
    """Muestra UN toast con el backend de la sesión.

    Rama única para el one-shot y el replay (antes duplicada en
    `verdantis.main`): Wayland con layer-shell → `WaylandPopup`; X11 o
    `--force-fallback` → `NotificacionX11`; Wayland SIN layer-shell → error por
    stderr y exit ≠ 0, sin fallback mal posicionado (spec `entrada-fallback`)."""
    is_wayland = (
        force_wayland
        or (not force_fallback and os.environ.get("WAYLAND_DISPLAY"))
    )
    if is_wayland:
        try:
            from wayland_popup import WaylandPopup
            WaylandPopup(**kwargs).show()
            return
        except Exception as e:
            # En Wayland SIN layer-shell NO hay fallback: una ventana toplevel
            # sin anclaje sale donde quiere el compositor — peor que ningún
            # toast (spec `entrada-fallback`, "falla limpio").
            print(f"[{app_info.APP_ID}] Wayland sin layer-shell ({e}); "
                  f"no hay fallback en sesión Wayland", file=sys.stderr)
            sys.exit(1)

    # Import perezoso del fallback X11: el path Wayland no lo carga.
    from x11_popup import NotificacionX11
    NotificacionX11(**_para_x11(kwargs)).show()


def _para_x11(kwargs):
    """Descarta lo que el fallback X11 no acepta en su `__init__`."""
    return {k: v for k, v in kwargs.items() if k in _X11_KEYS}


def cmd_list(args):
    """Tabla del historial: id, fecha, app, summary."""
    recs = seleccionar(history_store.read(), last=args.last, app=args.app)
    if not recs:
        print("historial vacío: {}".format(history_store._history_path()),
              file=sys.stderr)
        return
    for r in recs:
        print("{:>6}  {}  {:<14}  {}".format(
            r.get("id"), _fecha(r.get("timestamp")),
            _plano(r.get("app_name"), 14), _plano(r.get("summary"), 70)))


def cmd_replay(args):
    """Muestra los registros elegidos uno por uno (espera vencimiento/cierre)."""
    recs = seleccionar(history_store.read(), last=args.last, app=args.app,
                       id=args.id)
    if not recs:
        print("no hay notificaciones para reproducir en {}".format(
            history_store._history_path()), file=sys.stderr)
        return
    for r in recs:
        mostrar_toast(
            record_a_kwargs(r, duration=args.duration),
            force_fallback=args.force_fallback,
        )


def cmd_clear(args):
    """Borra historial + iconos. Sin `--yes` no toca nada (es irreversible)."""
    path = history_store._history_path()
    if not args.yes:
        print("Se borrarán {} registros y los iconos de {}".format(
            len(history_store.read()), path), file=sys.stderr)
        # El comando real: no existe un binario `verdantis` instalado.
        print("Confirmá con: .venv/bin/python src/verdantis.py clear --yes",
              file=sys.stderr)
        sys.exit(1)
    n, icons = history_store.clear()
    print("Borrado {}: {} registros, {} iconos".format(path, n, icons))


def _fecha(ts):
    """Timestamp del registro → fecha local legible ('' si no es numérico)."""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return ""


def _plano(texto, ancho):
    """Una sola línea, sin saltos ni tabs, recortada a `ancho`."""
    t = " ".join(str(texto or "").split())
    return t if len(t) <= ancho else t[:ancho - 1] + "…"
