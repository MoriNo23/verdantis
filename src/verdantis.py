"""Entry point de verdantis.

`--daemon` delega al daemon DBus (GTK + layer-shell). Los subcomandos
`list` / `replay` / `clear` operan sobre el historial archivado
(`history_store` + `replay`). El one-shot elige backend por sesión:

- `WAYLAND_DISPLAY` → WaylandPopup (GTK3 + layer-shell).
- solo X11 (o `--force-fallback`) → `x11_popup` (Gtk.Window posicionable,
  mismo render cairo/Pango, sin layer-shell).
- Wayland SIN layer-shell → error por stderr y exit ≠ 0: no hay fallback
  mal posicionado (spec `entrada-fallback`).

La elección de rama vive en `replay.mostrar_toast` (única copia, compartida
con el replay). Los imports son perezosos: ni el daemon ni el path Wayland
cargan el fallback, y `list`/`clear` no cargan gi. Qt no existe en el proyecto.
"""
import sys
import os

from app_info import DEFAULT_ACCENT


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Notificación")
    parser.add_argument("--body", default="")
    parser.add_argument("--icon", default=None)
    parser.add_argument("--app-icon", default=None, help="Icono pequeño de la app (16x16)")
    parser.add_argument("--image", default=None)
    parser.add_argument("--duration", type=int, default=6000)
    parser.add_argument("--margin", type=int, default=16)
    parser.add_argument("--corner", default="top-right",
                        choices=["top-right", "top-left", "bottom-right", "bottom-left"])
    parser.add_argument("--accent", default=DEFAULT_ACCENT)
    parser.add_argument("--app-name", default="", help="Nombre de app (Telegram, Firefox...)")
    parser.add_argument("--force-wayland", action="store_true")
    parser.add_argument("--force-fallback", action="store_true",
                        help="Forzar el branch X11 de fallback (pruebas)")
    parser.add_argument("--daemon", action="store_true",
                        help="Iniciar como daemon DBus (org.freedesktop.Notifications)")

    sub = parser.add_subparsers(dest="cmd")
    p_list = sub.add_parser("list", help="Listar el historial archivado")
    p_list.add_argument("--last", type=int, default=20,
                        help="N más recientes, en orden de llegada "
                             "(más viejo primero); 0 = sin límite")
    p_list.add_argument("--app", default=None, help="Filtrar por app")
    p_replay = sub.add_parser(
        "replay", help="Volver a mostrar notificaciones archivadas")
    p_replay.add_argument("--last", type=int, default=5,
                          help="N más recientes, en orden de llegada "
                               "(más viejo primero); 0 = sin límite")
    p_replay.add_argument("--app", default=None, help="Filtrar por app")
    p_replay.add_argument(
        "--id", type=int, default=None,
        help="El registro MÁS RECIENTE con ese id (los ids se repiten: cada "
             "reinicio del daemon resetea el contador); gana sobre --last")
    p_replay.add_argument("--duration", type=int, default=None,
                          help="Pisa la duración archivada (ms); util con persistentes")
    p_replay.add_argument("--force-fallback", action="store_true",
                          help="Forzar el branch X11 de fallback (pruebas)")
    p_clear = sub.add_parser("clear", help="Borrar el historial y los iconos archivados")
    p_clear.add_argument("--yes", action="store_true", help="Confirmar el borrado")
    args = parser.parse_args()

    if args.cmd:
        import replay
        {"list": replay.cmd_list,
         "replay": replay.cmd_replay,
         "clear": replay.cmd_clear}[args.cmd](args)
        return

    if args.daemon:
        from verdantis_daemon import NotificationDaemon
        NotificationDaemon(corner=args.corner).run()
        return

    from replay import mostrar_toast
    mostrar_toast({
        "titulo": args.title, "cuerpo": args.body,
        "icon_path": args.icon, "image_path": args.image,
        "duration": args.duration, "margin": args.margin,
        "corner": args.corner, "accent": args.accent,
        "app_name": args.app_name, "app_icon": args.app_icon,
    }, force_wayland=args.force_wayland, force_fallback=args.force_fallback)


if __name__ == "__main__":
    main()
