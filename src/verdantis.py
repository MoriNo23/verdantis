"""Entry point de verdantis.

`--daemon` delega al daemon DBus (GTK + layer-shell, SIN Qt). El one-shot
elige backend Wayland (WaylandPopup) o, si no hay layer-shell, el fallback
PyQt6 — que se importa recién en ese branch (qt_fallback), nunca al arrancar.
"""
import sys
import os

from app_info import APP_NAME


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
    parser.add_argument("--force-qt", action="store_true")
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
        or (not args.force_qt and os.environ.get("WAYLAND_DISPLAY"))
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
            print(f"[notify] Wayland falló ({e}); usando Qt", file=sys.stderr)

    # Import perezoso del fallback Qt: el daemon y el path GTK no cargan PyQt6.
    from qt_fallback import QApplication, NotificacionPersonalizada
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    n = NotificacionPersonalizada(
        titulo=args.title, cuerpo=args.body,
        icon_path=args.icon, image_path=args.image,
        duration=args.duration, margin=args.margin,
        corner=args.corner, accent=args.accent,
    )
    n.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
