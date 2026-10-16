"""Entry point de verdantis.

`--daemon` delega al daemon DBus (GTK + layer-shell). El one-shot elige
backend por sesión:

- `WAYLAND_DISPLAY` → WaylandPopup (GTK3 + layer-shell).
- solo X11 (o `--force-fallback`) → `x11_popup` (Gtk.Window posicionable,
  mismo render cairo/Pango, sin layer-shell).
- Wayland SIN layer-shell → error por stderr y exit ≠ 0: no hay fallback
  mal posicionado (spec `entrada-fallback`).

Los imports del one-shot son perezosos: ni el daemon ni el path Wayland
cargan el fallback. Qt no existe en el proyecto.
"""
import sys
import os


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Notificación")
    parser.add_argument("--body", default="")
    parser.add_argument("--icon", default=None)
    parser.add_argument("--app-icon", default=None, help="Icono pequeño de la app (16x16)")
    parser.add_argument("--image", default=None)
    parser.add_argument("--duration", type=int, default=8000)
    parser.add_argument("--margin", type=int, default=16)
    parser.add_argument("--corner", default="top-right",
                        choices=["top-right", "top-left", "bottom-right", "bottom-left"])
    parser.add_argument("--accent", default="#89b4fa")
    parser.add_argument("--app-name", default="", help="Nombre de app (Telegram, Firefox...)")
    parser.add_argument("--force-wayland", action="store_true")
    parser.add_argument("--force-fallback", action="store_true",
                        help="Forzar el branch X11 de fallback (pruebas)")
    parser.add_argument("--daemon", action="store_true",
                        help="Iniciar como daemon DBus (org.freedesktop.Notifications)")
    args = parser.parse_args()

    if args.daemon:
        from verdantis_daemon import main as daemon_main
        import sys as _sys
        _sys.argv = [_sys.argv[0], "--corner", args.corner]
        daemon_main()
        return

    is_wayland = (
        args.force_wayland
        or (not args.force_fallback and os.environ.get("WAYLAND_DISPLAY"))
    )

    if is_wayland:
        try:
            from wayland_popup import WaylandPopup
            popup = WaylandPopup(
                titulo=args.title, cuerpo=args.body,
                icon_path=args.icon, image_path=args.image,
                duration=args.duration, margin=args.margin,
                corner=args.corner, accent=args.accent,
                app_name=args.app_name, app_icon=args.app_icon,
            )
            popup.show()
            return
        except Exception as e:
            # En Wayland SIN layer-shell NO hay fallback: una ventana toplevel
            # sin anclaje sale donde quiere el compositor — peor que ningún
            # toast (spec `entrada-fallback`, "falla limpio").
            print(f"[notify] Wayland sin layer-shell ({e}); no hay fallback "
                  f"en sesión Wayland", file=sys.stderr)
            sys.exit(1)

    # Import perezoso del fallback X11: el daemon y el path Wayland no lo cargan.
    from x11_popup import NotificacionX11
    n = NotificacionX11(
        titulo=args.title, cuerpo=args.body,
        icon_path=args.icon, image_path=args.image,
        duration=args.duration, margin=args.margin,
        corner=args.corner, accent=args.accent,
    )
    n.show()


if __name__ == "__main__":
    main()
