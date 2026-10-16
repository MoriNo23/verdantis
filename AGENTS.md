# Verdantis

Daemon de notificaciones de escritorio para Wayland (KDE Plasma 6). Es el owner de
`org.freedesktop.Notifications` en el bus de sesión y dibuja toasts con GTK3 +
gtk-layer-shell (cairo/Pango), sin depender de Plasma. Reemplaza a mako/deadd.

## Skill — input (fuera del stack de render)

- `ydotool-uinput` — ydotool 1.0.4 (Debian trixie) por `/dev/uinput` en Wayland/KWin:
  mover cursor, clicks, wheel y tipeo para pruebas manuales. Cargarla cuando haya
  que interactuar con el desktop sin X11. OJO: `--absolute` está roto (KWin clava
  el cursor en 1,1) y la posición se verifica con `kdotool getmouselocation`, nunca
  con `xdotool` (Xwayland devuelve posiciones viejas).

## Dev environment

- Python 3.13 en `.venv/` (venv clásico; la migración a uv quedó bloqueada — uv solo
  ve python 3.12 del sistema y `gi` no compila desde pip). Instalación: `./install.sh` (apt: libgtk-layer-shell-dev,
  python3-gi, python3-gi-cairo; cero deps pip) y copia `verdantis.service` a
  `~/.config/systemd/user/`.
- 7 módulos en `src/`:
  - `verdantis.py` — entry point; `--daemon` delega al daemon; one-shot elige backend
    por sesión: Wayland (GTK layer-shell) → X11 (`x11_popup`); Wayland SIN layer-shell
    → error por stderr + exit ≠ 0 (sin fallback). Import perezoso en ambos branches.
  - `verdantis_daemon.py` — dueño del bus DBus (`Notify`, `CloseNotification`,
    `GetCapabilities`, `GetServerInformation`, signals), cola de toasts, click→action.
  - `wayland_popup.py` — render del toast: `NotificationWidget` (Gtk.DrawingArea con
    cairo), layout (imagen izquierda de 80px siempre / columna de texto única), wrap Pango,
    franja vertical de descarte + barra expandir full-width, wipe de tiempo.
  - `app_info.py` — fuente única de `APP_NAME`/`APP_ID`/`VENDOR` (nada de literales
    "Verdantis" inline; el vendor de GetServerInformation es MoriNo23, no el nombre).
  - `dashboard.py` — Flask dashboard de historial + replay (thread dentro del daemon).
  - `history_store.py` — persistencia del historial JSONL
    (`$XDG_DATA_HOME/verdantis/history.jsonl`) + bytes de iconos/imagen para que el
    replay del dashboard reproduzca "cómo se veía" cada notificación (las claves
    `avatar_source`/`avatar_file` son esquema de disco, no vocabulario de layout).
  - `x11_popup.py` — fallback X11 (Gtk.Window posicionable, sin layer-shell) que
    reutiliza `NotificationWidget`; solo se importa en ese branch. Qt no existe.
- Métricas de layout: fuente única en `wayland_popup` (`_PAD`/`_rows_above_body`/...),
  consumidas por `_draw`, `calc_card_height` y `_eff_text_width`. No recomputar el
  stack a mano o divergen.

## Build & test

- Tests: `.venv/bin/python -m pytest tests/ -q` (suite mínima viva: contrato
  D-Bus de cierre + hyperlinks del body + metatests de sensibilidad, <5s).
  La suite de render completa fue eliminada a pedido del usuario
  (recuperable por historia de git).
- Mockups del toast: viven en `mockups/` (app Next.js + wireframe-ui, parte
  de main). Correr con `pnpm dev` dentro de la carpeta y editar el JSX
  directamente — tokens en `mockups/src/lib/toast-tokens.ts` con la constante
  original de `wayland_popup.py` comentada en cada valor. Sin validador: los
  mockups son documentación visual y PUEDEN divergir; la verdad del
  comportamiento son los specs de `openspec/specs/` y el código. (El tablero
  anterior se retiró con este cambio; recuperable por `ba091a4` en git.)
- Los tests son headless: `tests/conftest.py` es el dueño del `GDK_BACKEND` (wayland
  si hay `WAYLAND_DISPLAY`, offscreen si no) y del path hacia `src/` — corre antes que
  cualquier módulo de test, así que los archivos no repiten ese preámbulo.
  `wayland_popup` forza `GDK_BACKEND=wayland` al importarse, por eso el env debe
  fijarse antes de importarlo. El orden "wayland_popup
  primero entre los imports gi" se mantiene DENTRO de cada módulo (fija Gdk 3.0).
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
  `image-path` plano (va a la imagen izquierda). `image-data` = icono del tab → imagen
  izquierda; NO al banner.
- Imagen izquierda: el slot de 80 px (`_IMAGE_LEFT_W`) está en TODOS los toasts. Cadena:
  imagen de la notificación (image-path / image-data del tab) → icono de la app (`.desktop`
  exacto → tema) → placeholder con la inicial (`_make_placeholder_icon` + clip circular).
  Nunca queda `None`: no existe la variante sin imagen (columna ancha, fuentes 12/13, gap
  del HR). La columna de texto es una sola, 240 px (196 con la franja de descarte en hover
  de un persistente), y el texto arranca al top del slot (`ty = pad`, sin centrado del
  bloque). `_eff_text_width` y `_rows_above_body` no tienen ramas por variante.
- Verificación visual de los toasts: la da el USUARIO. El agente no saca capturas ni
  inspecciona la pantalla por su cuenta (nada de `spectacle`/`grim`/`import` ni leer
  imágenes de la pila): manda notificaciones de prueba y espera el reporte visual del
  usuario, que es la fuente de verdad. Spec: `openspec/specs/verificacion-visual/spec.md`.
- Antialiasing del texto: se fija por CÓDIGO (helper `_create_layout` con `_FONT_OPTIONS`
  = `ANTIALIAS_GRAY`), NO se hereda del fontconfig del usuario. El subpixel del fontconfig
  destiñe el texto sobre las superficies transparentes del toast (issue conocido de
  pangocairo); por eso todo layout del card se crea con el helper y no con
  `PangoCairo.create_layout` suelto.

## Pitfalls

- `/tmp` es tmpfs de 1.9G: las corridas de pytest acumulan basura en
  `/tmp/pytest-of-fullmetal` y lo llenan (`Errno 28`). Limpiar con `rm -rf /tmp/pytest-of-fullmetal`.
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
