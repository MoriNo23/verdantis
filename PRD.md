# PRD — Verdantis

Producto: daemon de notificaciones de escritorio para Wayland (KDE Plasma 6).
Versión del documento: 1.1 (ciclo 0.13.0). Fuente de verdad del *comportamiento*:
`openspec/specs/` — este PRD es el mapa de producto; si algo difiere, manda el spec.

## 1. Resumen

Verdantis es el dueño de `org.freedesktop.Notifications` en el bus de sesión y dibuja
los toasts con GTK4 + GSK + gtk4-layer-shell (sin cairo en el pipeline de dibujo), sin
depender de Plasma. Reemplaza a mako/deadd. Corre como servicio de usuario
(`systemd --user`) desde el mismo repo.

## 2. Problema

- Los daemons genéricos no respetan el stack en Wayland/KWin ni el look propio.
- Con ráfagas (reconexión de red, VPN, pestañas del navegador) los toasts aparecen
  todos juntos, se tapan entre sí y expiran en bloque.
- El texto sobre fondos translúcidos se destiñe cuando el fontconfig del usuario usa
  antialiasing subpixel (issue conocido de pangocairo).

## 3. Usuario

Usuario único: MoriNo23 (autor). Sin telemetría ni multiusuario. El **verificador
visual** del producto es el agente (spec `verificacion-visual`): manda notificaciones
de prueba, toma capturas e inspecciona la pantalla por su cuenta; el usuario puede
aportar su percepción pero no es la fuente exclusiva.

## 4. Objetivos

1. Cumplir el contrato freedesktop 1.2 (Notify, CloseNotification, ActionInvoked,
   NotificationClosed, capabilities honestas).
2. Pila predecible: nada se tapa, nada salta la fila, el orden es el de llegada.
3. Render legible y estable en cualquier equipo (texto nítido, sin franjas de color).
4. Diagnosticable: historial en disco + replay y lista por CLI (`verdantis replay`
   / `verdantis list`).

## 5. Requisitos funcionales

### R1 — Pila acotada y fila FIFO

- Máximo **2 toasts simultáneos** (`MAX_VISIBLE`); los demás esperan en `_pending`.
- **Un toast no se crea hasta que hay hueco visual**: las que esperan son datos,
  sin popup, sin ventana y sin timer.
- El hueco se libera cuando el toast **vence por timer** o el usuario lo **cierra**
  (click en la franja/X, `CloseNotification`, `replaces_id`, dedup); entonces entra
  **la primera de la fila**.
- La `urgency` NO influye en la posición ni en la capacidad: solo duración y estilo.
- El timeout de cada toast arranca **cuando se muestra**, no cuando llega.

### R2 — La pila nunca solapa

- Gap de 12 px entre cards; offsets acumulados con las alturas REALES de cada card.
- Reflow al expandir/contraer ("Ver más"), al re-wrappear por hover y al entrar/salir
  cualquier toast.
- El toast que entra reserva su hueco **antes** de mapear su superficie: su primer
  frame ya está debajo del de arriba; nunca se lo ve tapando a otro.

### R3 — Texto nítido en cualquier equipo

- Todo el texto del card (app, título, body con markup, labels de acciones) se
  rasteriza con GSK (`append_layout`), que resuelve el antialiasing en el
  renderer; ya no se fija `_FONT_OPTIONS` ni se usa `_create_layout(cr)`.
  El cambio no altera métricas (alto del card, wrap, cap de líneas) ni paleta.

### R4 — Interacción

- Click emite `ActionInvoked` con la key real del sender y/o abre la URL con
  `xdg-open`. **Nunca** lanza la app (abría ventanas duplicadas del navegador).
- Franja de descarte + X solo cierran ese toast; el resto queda como está.
- `expire_timeout`: `0` = persistente (no vence), `>0` = ese valor, `<0` = default
  del server (6000 ms).

### R5 — Contenido del toast

- Slot de imagen izquierda de 80 px en TODOS los toasts: imagen de la notificación
  → icono de la app (`.desktop` exacto) → placeholder con la inicial. Nunca `None`.
- Body sanitizado (`_strip_urls`): el URL del sitio que inyectan los navegadores no
  colapsa el texto; el click sigue usando la URL extraída.
- Navegadores: la línea de app muestra "Brave - <título>" sin duplicar el título.

### R6 — Persistencia y replay

- Cada `Notify` **no `transient`** se archiva en
  `$XDG_DATA_HOME/verdantis/history.jsonl` (+ copia de los bytes del icono) para que
  `verdantis replay` vuelva a mostrar "cómo se veía X app tal cual" **en producción**.
  Tope de 1000 registros (rotación, borrando también sus iconos) y 256 KB por icono.
- El replay **no pasa por el bus**: reconstruye el toast con el render real
  (`WaylandPopup` o el fallback X11, misma elección de rama que el one-shot). Por eso
  no re-archiva, no lo filtra la dedup y funciona aunque el daemon no sea el dueño de
  `org.freedesktop.Notifications`. A cambio no hay sender: click = `xdg-open` de la
  URL archivada, sin `ActionInvoked`.
- `verdantis list [--last N] [--app X]` lista el historial; `verdantis replay
  [--last N] [--app X] [--id N] [--duration MS]` los muestra uno por uno;
  `verdantis clear --yes` borra historial e iconos (irreversible, sin `--yes` no toca
  nada). `--id` toma el match más reciente: los ids se repiten entre reinicios del
  daemon y el JSONL acumula hasta 1000 registros.

### R7 — Verificación visual por el agente

- La confirmación de cómo se ven los toasts la da el agente: puede sacar capturas
  e inspeccionar la pantalla (spec `verificacion-visual`).

## 6. Fuera de alcance

- **Dashboard web** (Flask/`127.0.0.1:8777`): retirado en v0.12.0; el replay es por CLI
  y no vuelve (YAGNI: nadie lo consumía).
- Capacidad configurable por CLI/esquina (nadie la pidió; YAGNI).
- Reordenar la fila por urgencia o "importancia": viola la regla de llegada.
- Sonidos (`sound-name`/`suppress-sound` se ignoran; no se anuncia "sound").
- `_bg_alpha` por urgency: código muerto (se asigna, `_draw` no lo lee) — deuda
  documentada, fuera de este ciclo.
- PyGObject 3.58 (solo sdist; el venv vive de la .so de girepository del sistema).
- X11 como target primario: el fallback es GTK4 (`x11_popup`, sin layer-shell,
  anclaje reposicionado con Xlib/EWMH); no hay Qt en el proyecto.
- Replay por bus (re-emitir `Notify`): se vería el stack real pero re-archivaría el
  historial y la dedup se tragaría los repetidos.

## 7. Verificación

| Requisito | Cómo se comprueba |
|---|---|
| R1, R4 | `tests/test_contrato_dbus.py` (razones de cierre, replaces/dedup sin emisión, caps, `spec_version`) + `tests/test_auditoria_fixes.py` (tope de cola, hueco liberado, margins) |
| R3 | spec `toast-texto-nitido` + verificación visual del agente |
| R6 | `tests/test_replay_cli.py` (store, selección, mapeo registro→toast, archivo/transient del daemon) + `tests/test_tests_replay_cli.py` (metatests que inyectan el bug y exigen que el test lo detecte) |
| R7 | verificación visual del agente (spec `verificacion-visual`) |
| Regresión global | suite completa verde (101 tests, <2 s), en local y en CI (`.github/workflows/ci.yml`) |

## 8. Dependencias y plataforma

- Python 3.13 en `.venv/` (venv clásico; la migración a uv está bloqueada).
- apt: GTK 4.18.6 (`libgtk-4-1` / dev), `gtk4-layer-shell` 1.0.4
  (`libgtk4-layer-shell-dev`), `python3-gi` (girepository).
- pip (`requirements.txt`): PyGObject, pycairo (solo para el font map de Pango), pytest.
  Sin Qt ni Flask; cairo NO participa en el pipeline de dibujo (render GSK puro).
- systemd: `verdantis.service` (Type=dbus, dueño del nombre del bus).

## 9. Estado y pendientes del ciclo

- Hecho (0.15.1): migración GTK4 + GSK con vibrancia oscura (gradiente, hairline,
  sombra, botones con pressed que hunde), botón Copiar código de verificación,
  contraste AA corregido sobre wallpaper claro, dependencias auditadas (pip 26.3).
  Historial/replay por CLI, rama de backend unificada y metatests de sensibilidad.
- Hecho: verificación visual del replay por el agente (captura real de un registro
  con actions, imagen circular y app-label compuesto, v0.15.4).
- Hecho (0.15.6): tests de funcionamiento y visuales en vivo
  (`scripts/dbus_check.py`, `scripts/visual_check.sh` + golden). Dos bugs
  encontrados y corregidos: `CloseNotification` de una notificación todavía en
  cola no emitía `NotificationClosed` (la app quedaba esperando), y el alto del
  card no reservaba la fila del botón Copiar (se dibujaba fuera del card y era
  invisible en el desktop).
- Hecho (0.15.7): botones neutros (blanco 7 % / 11 % / 4 %): el acento como fill
  salía gris verdoso (`#41575F`) sobre la card. Etiquetas semibold y sombra
  interior de 2 px al presionar (cierra el hueco con `toast-vibrancia`).
  Specs y tokens del mockup actualizados.
- Pendiente: push a `origin/main`.
- Límite conocido del replay: lo archivado por `image-data` **sin** path de archivo no
  guarda bytes (los 28 registros viejos sí tienen PNG); esos caen al icono de app.
- Riesgo abierto: el usuario vio una vez un "toast de más" en la transición de
  cierre→entrada. Por código no puede existir un tercero (la creación está guardada
  en los dos únicos call sites de `_show_popup`); hipótesis restante: la superficie
  cerrada tarda un frame en desmapearse en el compositor. Fix contingente (crear el
  entrante un frame después del cierre) solo si vuelve a verse.
