# Verdantis

Daemon de notificaciones de escritorio para Wayland (KDE Plasma 6). Es el owner de
`org.freedesktop.Notifications` en el bus de sesión y dibuja toasts con GTK3 +
gtk-layer-shell (cairo/Pango), sin depender de Plasma. Reemplaza a mako/deadd.

## Dev environment

- Python 3.13 en `.venv/` (venv clásico; la migración a uv está BLOQUEADA, ver
  `tests/test_uv_migration.py`). Instalación: `./install.sh` (apt: libgtk-layer-shell-dev,
  python3-gi, python3-gi-cairo; pip: PyQt6) y copia `verdantis.service` a
  `~/.config/systemd/user/`.
- 3 módulos en `src/`:
  - `verdantis.py` — entry point; `--daemon` delega al daemon; one-shot elige backend
    Wayland (GTK layer-shell) o fallback PyQt6.
  - `verdantis_daemon.py` — dueño del bus DBus (`Notify`, `CloseNotification`,
    `GetCapabilities`, `GetServerInformation`, signals), cola de toasts, click→action.
  - `wayland_popup.py` — render del toast: `NotificationWidget` (Gtk.DrawingArea con
    cairo), layout (avatar 80px opcional / texto a ancho completo), wrap Pango,
    botón "Ver más/Ver menos", wipe de tiempo.

## Build & test

- Tests: `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_uv_migration.py`
  (~2s, 81 passed). La suite entera con el test uv tarda 30-50s y NECESITA red a PyPI.
- Los tests son headless: importan módulos con `os.environ.setdefault("GDK_BACKEND","offscreen")`
  ANTES de importar. `wayland_popup` forza `GDK_BACKEND=wayland` al importarse, así que
  el test debe pisarlo antes o no arranca display.
- Convención de tests: unit + metatests de sensibilidad (test_tests_*.py que inyectan
  la versión bugueada y verifican que la suite la detecta).
- Sin linter/type-check configurado. No correr `mypy`/`ruff` de memoria.

## Conventions

- Código y commits en español. Commits conventional: `feat:`, `fix:`, `test:`, `chore:`.
- TDD: test que falla primero (documenta el bug), luego fix mínimo, luego suite verde.
- Resolución de .desktop: SOLO match exacto (`_exact_desktop_file`). El match difuso
  (`_find_desktop_file`) rompe con PWAs de Brave (`brave-<appid>.desktop`) — un
  "brave" genérico cae en el PWA y muestra su icono/nombre.
- Click en toast: emite `ActionInvoked` con la key real del sender (`_pick_action_key`)
  y/o `xdg-open` si hay URL. NUNCA lanzar la app (`Gio.DesktopAppInfo.launch`/`gtk-launch`)
  — abría ventanas de navegador duplicadas.
- Body visible: se sanitiza con `_strip_urls` (quita http(s)://, hosts desnudos tipo
  `xat.com`/`127.0.0.1:8766`, y colapsa `\n\n+`). Los navegadores inyectan el URL del
  sitio como primer link; además el `set_height`+ellipsize de Pango colapsa TODO el
  body a esa línea si no se saca. El click sigue usando la URL extraída del body/hints.
- Navegador (detección por `desktop-entry`/app_name con `_is_browser`): la línea de app
  muestra "Brave - <título>" con ellipsis Pango y el título no se duplica (hide_title).
- Iconos del tab: Brave manda `app_icon` como `file:///tmp/...` (usar `_local_path`) e
  `image-path` plano (va al avatar). `image-data` = icono del tab → avatar; NO al banner.

## Pitfalls

- `/tmp` es tmpfs de 1.9G: las corridas de pytest acumulan basura en
  `/tmp/pytest-of-fullmetal` y lo llenan (`Errno 28`). Limpiar con `rm -rf /tmp/pytest-of-fullmetal`.
- `test_uv_migration.py` instala PyQt6 por `uv` y falla sin red/registry — excluirlo.
- El daemon compite por `org.freedesktop.Notifications` con el daemon de notificaciones
  de Plasma. Si plasmashell lo reclama, verdantis pierde el nombre y queda idle
  (NameLost). Verificar owner con `busctl --user list | grep Notifications`.
- Reinicio: `systemctl --user restart verdantis.service` (Type=dbus, BusName=...).
- Import de gi: `import wayland_popup` PRIMERO fija Gdk 3.0; importar `gi.repository.Gdk`
  suelto carga Gdk 4.0 y crashea (`Requiring namespace 'Gdk' version '3.0', but '4.0'...`).
- Página de test de notificaciones: servida por `python3 -m http.server 8766 --directory ~/Descargas`
  (puerto 8765 lo ocupa un server stale). Vive mientras la sesión que la lanzó esté viva.
- `read_file` trunca outputs grandes en este repo a ~5.5K chars por llamada; usar
  `sed -n 'a,bp'` por terminal para rangos largos.
