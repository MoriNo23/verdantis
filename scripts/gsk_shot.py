#!/usr/bin/env python3
"""Captura offscreen del render (sin KWin, sin pantalla desbloqueada).

El reftest de `visual_check.sh` depende de que KWin entregue la captura: con la
sesión bloqueada, `org.kde.KWin.ScreenShot2` responde `NoAuthorized` y spectacle
no obtiene nada. Este script dibuja el MISMO widget con `do_snapshot` + el
mismo pipeline GSK y lo rasteriza a PNG, así el render se puede verificar
siempre.

Uso:
  scripts/gsk_shot.py --toast -o /tmp/toast.png
  scripts/gsk_shot.py --center -o /tmp/centro.png

El PNG del toast NO es comparable 1:1 contra la golden del desktop: acá la card
translúcida se compone sobre un fondo fijo (`--bg`), no sobre el wallpaper. Por
eso tiene su propia golden (`tests/golden/toast-offscreen.png`).
"""
import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
os.environ.setdefault("GDK_BACKEND", "wayland")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

import wayland_popup as wp


def _pump(n=30):
    ctx = GLib.MainContext.default()
    for _ in range(n):
        while ctx.pending():
            ctx.iteration(False)


def _raster(node, ancho, alto, fondo, salida):
    import cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
    cr = cairo.Context(surf)
    cr.set_source_rgb(*fondo)
    cr.paint()
    node.draw(cr)
    surf.write_to_png(salida)


def _fondo(hex_color):
    return tuple(int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))


def shot_toast(salida, fondo):
    """Misma data que la notificación de `visual_check.sh`."""
    w = wp.NotificationWidget(
        app_name="verdantis-visual", app_icon="mail",
        titulo="Código de verificación",
        cuerpo="Tu código de verificación es 482193. No lo compartas.",
        icon_path=None, image_path=None, accent=wp.DEFAULT_ACCENT,
        persistent=True,
    )
    alto = w.desired_height()
    w.allocate(wp._CARD_WIDTH, alto, -1, None)
    snap = Gtk.Snapshot.new()
    w.do_snapshot(snap)
    _raster(snap.to_node(), wp._CARD_WIDTH, alto, fondo, salida)
    return wp._CARD_WIDTH, alto


def shot_center(salida, fondo, limite):
    import notification_center as nc
    win = nc.CenterWindow(limit=limite)
    win._win.present()
    _pump()
    ancho = win._win.get_width() or 420
    alto = win._win.get_height() or 620
    paintable = Gtk.WidgetPaintable.new(win._win)
    snap = Gtk.Snapshot.new()
    paintable.snapshot(snap, ancho, alto)
    _raster(snap.to_node(), ancho, alto, fondo, salida)
    return ancho, alto


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    que = ap.add_mutually_exclusive_group(required=True)
    que.add_argument("--toast", action="store_true")
    que.add_argument("--center", action="store_true")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--bg", default="#101014",
                    help="fondo opaco para la card translúcida (por defecto #101014)")
    ap.add_argument("--limit", type=int, default=8,
                    help="registros del centro (solo --center)")
    args = ap.parse_args()

    if Gtk.init_check() is False:
        print("ERROR: no hay display GTK para dibujar", file=sys.stderr)
        return 1
    fondo = _fondo(args.bg)
    if args.toast:
        ancho, alto = shot_toast(args.out, fondo)
    else:
        ancho, alto = shot_center(args.out, fondo, args.limit)
    print("%dx%d -> %s" % (ancho, alto, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
