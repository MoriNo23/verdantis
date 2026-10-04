# Proposal — Botones de acción renderizados en el toast

## Why

Verdantis **anuncia `actions` en `GetCapabilities` pero no renderiza los botones** — la spec dice que quien anuncia esa capability "WILL PROVIDE the specified actions to the user". Hoy las actions solo alimentan el click del cuerpo (`_pick_action_key`), y el dataset lo demuestra: 173/1000 notificaciones traen actions; `open` (24) y `settings` (18) son botones que el usuario nunca ve. Verificado en el source de Telegram Desktop: con `actions` en las caps, el cliente portable manda `default`/"Abrir" + `mail-mark-read`/"Marcar como leída" (+ `inline-reply`/"Responder" si el server anuncia esa extensión — fase 2, fuera de este cambio), y con `action-icons` manda el hint para que sus botones estándar rendericen iconos del tema.

## What Changes

- **Render real de los botones**: cuando la notificación trae actions (pares key/label) además de `default`, el toast muestra hasta **3 botones** (excluyendo `default`, que sigue siendo el click del cuerpo) en una fila propia bajo el body — línea visual de la barra "Ver más" (precedente del repo) y del HIG de KDE (≤3 botones, texto legible).
- **Hitbox e invocación por botón**: cada botón tiene su rect clickeable (mismo patrón que `_expand_rect`/`_image_left_rect`), con hover; el click emite `ActionInvoked` con **la key de ese botón** — no la default — y consume el evento (sin fall-through al cuerpo ni a la franja).
- **action-icons**: capability nueva + hint — cuando el hint está, el key del botón se interpreta como nombre de icono del tema (`_icon_from_theme`), con el label como texto visible/fallback si el icono no resuelve (la spec pide "attempt"; el icono refuerza, el texto sigue legible — el VDG de KDE desaconseja icon-only).
- **spec_version "1.2" → "1.3"**: no cambia señales existentes; habilita que los clientes usen hints 1.3 (`resident`, `sound-*` quedan ignorados igual que hoy — sin mentir: `sound` NO se anuncia).
- **Caps honestas**: `actions` ahora se rinde de verdad; `action-icons` se anuncia cuando el render existe.
- **Knock-on del tablero**: la fila de botones suma altura a la card → mocks y cotas re-derivados (worktree de diseño on-demand).
- **Verificación en vivo del misterio del dataset**: el Telegram portable manda `actions: []` en las 12 notis registradas pese a que el source dice que debería mandar botones — primera task en vivo del apply: mandar un mensaje de Telegram tras el restart y documentar qué llega al history.
- **Follow-up documentado, fuera de scope**: `inline-reply` (cap "inline-reply" + campo de texto + señal `NotificationReplied` + keyboard layer-shell) — es lo que hace que Telegram adopte toasts nativos por defecto (`ByDefault()` del source), pero es un cambio de interacción que merece su propio change.
- Bump MINOR → **0.9.0** (`feat:`). TDD: tests rojos primero.

## Capabilities

### New Capabilities
- `toast-acciones`: render e interacción de los botones de acción del toast — fila de hasta 3 botones, hitboxes propias, `ActionInvoked` con la key del botón, `action-icons` con fallback a texto.

### Modified Capabilities

(ninguna — ninguna de las 5 capabilities existentes toca los botones; el click del cuerpo con `default` y la franja de descarte quedan exactamente como están)

## Impact

- `src/wayland_popup.py`: fila de botones en `_draw` + métricas en la fuente única (`calc_card_height`/`_rows_above_body` o su equivalente para la fila), hitboxes por botón, `on_click` gana el parámetro de la key (`on_click(action_key=None)`).
- `src/verdantis_daemon.py`: el popup recibe las actions para render; `_on_action_invoked` acepta la key del botón; caps +`action-icons`; `spec_version` "1.3".
- `AGENTS.md`: convención de actions/botones.
- Tablero de diseño (rama `diseno-demos`, worktree on-demand): mock con botones + alturas.
- Tests: nuevos del contrato + metatest de sensibilidad (click de botón ≠ default).
- Sin cambios de API DBus (las señales/métodos existentes se usan tal cual).
