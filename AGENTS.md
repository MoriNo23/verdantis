# Verdantis

Daemon de notificaciones de escritorio para Wayland (KDE Plasma 6). Es el owner de
`org.freedesktop.Notifications` en el bus de sesión y dibuja toasts con GTK4 +
GSK + gtk4-layer-shell, sin depender de Plasma. Reemplaza a mako/deadd.

## Skill — input (fuera del stack de render)

- `ydotool-uinput` — ydotool 1.0.4 (Debian trixie) por `/dev/uinput` en Wayland/KWin:
  mover cursor, clicks, wheel y tipeo para pruebas manuales. Cargarla cuando haya
  que interactuar con el desktop sin X11. OJO: `--absolute` está roto (KWin clava
  el cursor en 1,1) y la posición se verifica con `kdotool getmouselocation`, nunca
  con `xdotool` (Xwayland devuelve posiciones viejas).

## Dev environment

- Python 3.13 en `.venv/` (venv aislado). Deps pip **fijadas** en `requirements.txt`
  (PyGObject 3.56.3, pycairo 1.29.0, pytest 9.1.1); auditoría/REA en
  `requirements-audit.txt` (pip-audit, mutmut, pwntools — NO son runtime).
  `./install.sh` (apt: libgtk4-layer-shell0 + gir1.2-gtk4layershell-1.0; venv +
  pip install) y genera `~/.config/systemd/user/verdantis.service` desde
  `service.template` con el path real (`@DIR@`).
- Tests de render GSK (`tests/test_render_gsk.py`): serializan el `Gsk.RenderNode`
  de `do_snapshot` sin ventana. Si falta un nodo (gradiente, sombra, texto,
  clip), la suite falla — es la red de seguridad que faltaba antes de v0.15.2.
- Verificación visual: `scripts/visual_check.sh` dibuja el toast offscreen con
  `scripts/gsk_shot.py` (mismo `do_snapshot` GSK, sin KWin ni wallpaper) y lo
  compara contra `tests/golden/toast-offscreen.png`; `--update` regenera la
  golden. Con `--live` además verifica que el toast aparezca en pantalla
  (captura KWin + sanity de colores, SIN comparar píxeles: el panel mueve la
  card). `scripts/dbus_check.py` cubre el contrato D-Bus end-to-end (`Notify` →
  `NotificationClosed` razón 3, incluida una notificación todavía en cola).
  OJO al parsear ids: `grep -o '[0-9]*'` sobre `(uint32 1,)` devuelve `32`.
- CI en `.github/workflows/ci.yml`: corre los 180 tests + `pip-audit` + `pip check`
  (los self-checks `test_gsk_shot.py` y `test_el_badge_real_se_construye_y_se_actualiza`
  se saltean sin display, así que en CI pasan 178).
  El headless usaba `GDK_BACKEND=broadway` SIN servidor:GTK no inicializaba y los
  tests de widget crasheaban. Ahora el workflow levanta `gtk4-broadwayd` (paquete
  `libgtk-4-bin`) en `:5`; para reproducirlo en local, exportar
  `BROADWAY_DISPLAY=:9 GDK_BACKEND=broadway` y correr `gtk4-broadwayd :9` aparte
  (`broadwayd` suelto es el de GTK3 y no sirve).
- GTK4: cargar `libgtk4-layer-shell` con `ctypes.CDLL(..., RTLD_GLOBAL)` ANTES
  de `import gi` (en `toast_window.py` y `daemon.py`): si libwayland
  se carga primero, `is_supported()` da False. No hace falta `LD_PRELOAD`.
- 9 módulos en `src/`:
  - `verdantis.py` — entry point; `--daemon` delega al daemon; subcomandos
    `list`/`replay`/`clear` (historial) delegan a `replay`; el one-shot delega la rama
    de backend a `replay.mostrar_toast`. Import perezoso en todos los branches.
  - `daemon.py` — dueño del bus DBus (`Notify`, `CloseNotification`,
    `GetCapabilities`, `GetServerInformation`, signals), cola de toasts, click→action,
    archivo al historial (`_persist_to_disk`, salvo hints `transient`).
  - `toast_helpers.py` — iconos (.desktop exacto → tema), URLs, detección de
    código de verificación, portapapeles (`wl-copy`, sin robar foco).
  - `toast_core.py` — métricas de layout (fuente única) y primitivas GSK:
    gradientes, sombra, hairline, pixbufs. Incluye `surface_size`/`layer_margins`:
    la surface layer-shell es mayor que la card para que la sombra no se recorte.
  - `toast_window.py` — `ToastCard` (interacción + `do_snapshot`) y
    `ToastWindow` (layer-shell, timers, pila). Re-exporta los dos módulos de
    arriba para no romper imports históricos (`from toast_window import ...`).
  - `app_info.py` — fuente única de `APP_NAME`/`APP_ID`/`VENDOR` (nada de literales
    "Verdantis" inline; el vendor de GetServerInformation es MoriNo23, no el nombre).
  - `x11_window.py` — fallback X11 (Gtk.Window posicionable, sin layer-shell) que
    reutiliza `ToastCard`; solo se importa en ese branch. Qt no existe.
  - `history_store.py` — historial en `$XDG_DATA_HOME/verdantis/history.jsonl` +
    `icons/`: `append`/`read`/`copy_icon`/`icon_path`/`clear`, tope 1000 registros y
    rotación con borrado de iconos. Best-effort: NUNCA tumba un `Notify`.
  - `replay.py` — `list`/`replay`/`clear` del historial y `mostrar_toast` (la rama de
    backend, única copia para one-shot y replay). Sin gi al importar: `list` y `clear`
    no tocan display. `history_store` reapareció con este ciclo (v0.12.0 lo había
    eliminado junto al dashboard, que sigue muerto y recuperable por git).
- Métricas de layout: fuente única en `toast_window` (`_PAD`/`_rows_above_body`/...),
  consumidas por `_draw`, `calc_card_height` y `_eff_text_width`. No recomputar el
  stack a mano o divergen. Escala tipográfica: `_TITLE_FS`/`_BODY_FS`/`_APP_FS`
  = 13/12/11; `calc_card_height` deriva el alto del body de `_BODY_FS`, no de una
  constante propia (`toast-tipografia`). El CSS del centro vive en
  `notification_center._css()` (foco con `DEFAULT_ACCENT`, no azul Adwaita).
  Urgencia: `critical` (`urgency=2`) no expira — `_duration_for` en el daemon —
  y su acento propio (`app_info.accent_for`, `#ef9a9a`) dibuja un rail GSK en
  `ToastCard`. La cola pendiente se muestra en `_PendingBadge`
  (layer-shell, sin foco), sincronizada por `_sync_badge` en el daemon.

## Build & test

- Tests: `.venv/bin/python -m pytest tests/ -q` (suite mínima viva: contrato
  D-Bus de cierre + caps + auditoría + historial/replay + metatests de
  sensibilidad, <5s).
  La suite de render completa fue eliminada a pedido del usuario
  (recuperable por historia de git).
- Mockups del toast: viven en `mockups/` (app Next.js + wireframe-ui, parte
  de main). Correr con `pnpm dev` dentro de la carpeta y editar el JSX
  directamente — tokens en `mockups/src/lib/toast-tokens.ts` con la constante
  original de `toast_window.py` comentada en cada valor. Sin validador: los
  mockups son documentación visual y PUEDEN divergir; la verdad del
  comportamiento son los specs de `openspec/specs/` y el código. (El tablero
  anterior se retiró con este cambio; recuperable por `ba091a4` en git.)
- Los tests son headless: `tests/conftest.py` es el dueño del `GDK_BACKEND` (wayland
  si hay `WAYLAND_DISPLAY`, offscreen si no) y del path hacia `src/` — corre antes que
  cualquier módulo de test, así que los archivos no repiten ese preámbulo.
  `toast_window` forza `GDK_BACKEND=wayland` al importarse, por eso el env debe
  fijarse antes de importarlo. `toast_window` carga libgtk4-layer-shell con
  RTLD_GLOBAL antes de gi: importarlo primero es obligatorio en cada módulo.
- Convención de tests: unit + metatests de sensibilidad (test_tests_*.py que inyectan
  la versión bugueada y verifican que la suite la detecta).
- Sin linter/type-check configurado. No correr `mypy`/`ruff` de memoria.

## Conventions

- Código y commits en español. Commits conventional: `feat:`, `fix:`, `test:`, `chore:`.
- Versionado: semver (`MAJOR.MINOR.PATCH`) con fuente única en la constante `VERSION`
  de `src/daemon.py` (la usa `GetServerInformation`). Bump MINOR en el primer
  commit `feat:` de cada ciclo; PATCH en `fix:`; MAJOR solo en breaking. `test:`/`chore:`
  NO bumpan. Un commit que bumea actualiza `VERSION` en el mismo commit y lo reporta al
  usuario; verificar el bump con `busctl --user call ... GetServerInformation` tras
  reiniciar el servicio. Sin tags de git: el número vive solo en el código.
- `README.md` está en inglés (excepción deliberada: es la cara pública del repo en
  GitHub); specs, PRD, PRODUCT y AGENTS siguen en español.
- TDD: test que falla primero (documenta el bug), luego fix mínimo, luego suite verde.
- Resolución de .desktop: SOLO match exacto (`_exact_desktop_file`). El match difuso
  (`_find_desktop_file`) rompe con PWAs de Brave (`brave-<appid>.desktop`) — un
  "brave" genérico cae en el PWA y muestra su icono/nombre.
- Click en toast: emite `ActionInvoked` con la key real del sender (`_pick_action_key`)
  y/o `xdg-open` si hay URL. NUNCA lanzar la app (`Gio.DesktopAppInfo.launch`/`gtk-launch`)
  — abría ventanas de navegador duplicadas.
- Historial y replay: el daemon archiva cada `Notify` no-`transient` (`_debe_archivar`)
  en `history_store`, copiando los bytes del icono (los de `/tmp` son efímeros). El
  replay NO pasa por el bus: reconstruye el toast con `replay.record_a_kwargs` y lo
  muestra con `mostrar_toast` (rama de backend única, compartida con el one-shot), así
  no re-archiva, la dedup no lo filtra y anda sin daemon; click = `xdg-open` de la URL
  archivada, sin `ActionInvoked` (no hay sender). `--id` toma el último match (los ids
  se repiten entre reinicios del daemon). Registro sin `avatar_file` en disco →
  el popup resuelve icono de app/placeholder (nunca queda sin imagen). Claves del
  registro (`avatar_file`/`banner_file`): esquema ya escrito en disco, NO se renombran.
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
  del HR). La columna de texto es una sola, 212 px, constante en reposo y hover (los 28 px
  del rail de descarte `_CLOSE_RAIL_W` están descontados y reservados siempre: el hover
  solo tiñe el rail, nunca reacomoda la card), y el texto arranca al top del slot
  (`ty = pad`, sin centrado del bloque). El hover pausa el vencimiento (crédito por tick en `_update_progress`).
  `_eff_text_width` y `_rows_above_body` no tienen ramas por variante.
- Verificación visual de los toasts: la hace el AGENTE. Puede sacar capturas
  (`spectacle`/`grim`/`import`) y leer imágenes de la pila, y da el veredicto visual
  sin esperar reporte humano. El usuario igual puede aportar observaciones, pero ya
  no es la fuente exclusiva. Spec: `openspec/specs/verificacion-visual/spec.md`.
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
- Import de gi: `import toast_window` PRIMERO carga libgtk4-layer-shell con
  RTLD_GLOBAL antes que libwayland. Si otro módulo importa Gtk/Gdk antes,
  `Gtk4LayerShell.is_supported()` da False y el toast no se mapea (falla limpio).
  `Gtk.Window.set_size_request` NO funciona en GTK4: usar `set_default_size`.
  `Gtk4LayerShell.set_exclusive_zone(-1)` deja la surface invisible en KWin: no usar.
- Página de test de notificaciones: servida por `python3 -m http.server 8766 --directory ~/Descargas`
  (puerto 8765 lo ocupa un server stale). Vive mientras la sesión que la lanzó esté viva.
- `read_file` trunca outputs grandes en este repo a ~5.5K chars por llamada; usar
  `sed -n 'a,bp'` por terminal para rangos largos.
- `.pyc` rancio tras mutar y restaurar `src/*.py` (mtime con resolución de segundos):
  un test puede fallar contra código que ya no existe. Ante un fallo imposible,
  `rm -rf src/__pycache__` antes de dudar del test.
