# Verdantis

Daemon de notificaciones de escritorio para Wayland (KDE Plasma 6). Es el owner de
`org.freedesktop.Notifications` en el bus de sesión y dibuja toasts con GTK3 +
gtk-layer-shell (cairo/Pango), sin depender de Plasma. Reemplaza a mako/deadd.

## Skills — stack GTK3/Wayland (CARGA OBLIGATORIA)

Estas skills viven en `.opencode/skills/<name>/SKILL.md` y son NECESARIAS para
cualquier tarea que toque el stack de render/interacción. Cargalas con la
herramienta `skill` ANTES de editar código de `src/wayland_popup.py`
(o cualquier trabajo de ventanas layer-shell, dibujo cairo, tipografía, assets
o runtime). Cada una incluye blueprints, pitfalls conocidos y helpers de prueba
que coinciden con los patrones reales del repo:

- `py-313-pygobject-runtime` — runtime Python 3.13/.venv, gi typelibs, threading
  y ciclo de vida GLib sin leaks. Usar para import/venv/threads/memoria.
- `gtk3-wayland-transparency` — pipeline RGBA de GTK3 y alpha compositing en KWin
  (evita cajas negras y artifacts de tema). Usar al tocar el fondo/alpha del card.
- `gtk-layer-shell-plasma6` — integración gtk-layer-shell 0.1 / zwlr_layer_shell_v1
  en Plasma 6: anclas, exclusive zone, input masking, crash al realizar.
- `pycairo-vector-rendering` — render vectorial cairo: rounded cards, close pills,
  wipe V-Sync con Gdk.FrameClock, clipping de imágenes/avatares, alineación subpixel
  (+0.5). USAR SIEMPRE al tocar `_draw`/cairo en `wayland_popup.py`.
- `pangocairo-bundled-typography` — Pango/PangoCairo con Manrope bundled (FontConfig
  ctypes), wrap multi-línea y ellipsis de precisión. Usar para textos/medición.
- `gdk3-pixbuf-cursor-input` — Gdk 3.0: carga de assets con fallback a memoria,
  cursors nativos Wayland y routing de eventos pointer/click en DrawingArea.
- `wayland-hud-fullstack` — blueprint end-to-end que integra TODO el stack
  (Python 3.13 + GTK3 + LayerShell + Cairo + Pango + Gdk) en una HUD flotante.
  Es la única que además trae una app de referencia completa.

Regla: si una skill coincide con la tarea, cargarla vía `skill <name>` y seguir
sus constraints; no improvisar patrones del stack a mano.

## Dev environment

- Python 3.13 en `.venv/` (venv clásico; la migración a uv está BLOQUEADA, ver
  `tests/test_uv_migration.py`). Instalación: `./install.sh` (apt: libgtk-layer-shell-dev,
  python3-gi, python3-gi-cairo; pip: PyQt6) y copia `verdantis.service` a
  `~/.config/systemd/user/`.
- 6 módulos en `src/`:
  - `verdantis.py` — entry point; `--daemon` delega al daemon; one-shot elige backend
    Wayland (GTK layer-shell) o fallback PyQt6 (import perezoso, sin Qt al arrancar).
  - `verdantis_daemon.py` — dueño del bus DBus (`Notify`, `CloseNotification`,
    `GetCapabilities`, `GetServerInformation`, signals), cola de toasts, click→action.
  - `wayland_popup.py` — render del toast: `NotificationWidget` (Gtk.DrawingArea con
    cairo), layout (avatar 80px opcional / texto a ancho completo), wrap Pango,
    franja vertical de descarte + barra expandir full-width, wipe de tiempo.
  - `app_info.py` — fuente única de `APP_NAME`/`APP_ID`/`VENDOR` (nada de literales
    "Verdantis" inline; el vendor de GetServerInformation es MoriNo23, no el nombre).
  - `dashboard.py` — Flask dashboard de historial + replay (thread dentro del daemon).
  - `qt_fallback.py` — notificación one-shot PyQt6; solo se importa en ese branch.
- Métricas de layout: fuente única en `wayland_popup` (`_PAD`/`_rows_above_body`/...),
  consumidas por `_draw`, `calc_card_height` y `_eff_text_width`. No recomputar el
  stack a mano o divergen (ver `tests/test_layout_consistency.py`).

## Build & test

- Tests: `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_uv_migration.py`
  (~10s, 180 passed). La suite entera con el test uv tarda 30-50s y NECESITA red a PyPI.
- Los tests son headless: importan módulos con `os.environ.setdefault("GDK_BACKEND","offscreen")`
  ANTES de importar. `wayland_popup` forza `GDK_BACKEND=wayland` al importarse, así que
  el test debe pisarlo antes o no arranca display.
- Convención de tests: unit + metatests de sensibilidad (test_tests_*.py que inyectan
  la versión bugueada y verifican que la suite la detecta).
- Sin linter/type-check configurado. No correr `mypy`/`ruff` de memoria.

## Conventions

- Código y commits en español. Commits conventional: `feat:`, `fix:`, `test:`, `chore:`.
- Versionado: semver (`MAJOR.MINOR.PATCH`) con fuente única en la constante `VERSION`
  de `src/verdantis_daemon.py` (la usa `GetServerInformation`). Bump MINOR en el primer
  commit `feat:` de cada ciclo; PATCH en `fix:`; MAJOR solo en breaking. `test:`/`chore:`
  NO bumpan. Un commit que bumea actualiza `VERSION` en el mismo commit y lo reporta al
  usuario; verificar el bump con `busctl --user call ... GetServerInformation` tras
  reiniciar el servicio. Sin tags de git: el número vive solo en el código.
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
