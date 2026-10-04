# Design

## Context

Ver `proposal.md` (Why) y el delta `toast-acciones`. Estado verificado que condiciona el diseño:

- **El click actual**: `_on_button_press` prioriza franja → barra "Ver más" → `on_click`; `on_click` lleva a `_on_action_invoked(nid)` que elige la key con `_pick_action_key` (default o la primera). No hay forma hoy de decirle al daemon QUÉ botón se clickeó — el callback no lleva key.
- **El patrón de hitboxes ya existe**: `_draw` publica rects que `_on_button_press` consulta (`_expand_rect`, `_close_rect`, `_image_left_rect`). La fila de botones es una extensión natural: una lista `_action_rects` de (rect, key).
- **El patrón de fila ya existe**: la barra "Ver más" (28 px, fondo accent al 22%, contenido centrado, hover 0.18→0.32) es el precedente visual exacto para una fila de botones al mismo lenguaje.
- **Métricas de fuente única**: la altura de la fila tiene que sumarse en el MISMO lugar que `_BTN_H`/`_BTN_GAP` (consumido por `_draw` y `calc_card_height` por igual) o altura y wrap divergen (regla de AGENTS).
- **Telegram portable verificado en source** (`notifications_manager_linux.cpp`): con cap `actions` manda `default`/"Abrir" + `mail-mark-read`/"Marcar como leída"; con cap `action-icons` y sin custom actions manda el hint; el key `mail-mark-read` es un icono del icon-naming-spec. Consume `ActivationToken` y las señales estándar.
- **El dataset y su misterio**: 12 notis de Telegram con `actions: []` pese a que el source dice que debería mandar botones (verdantis anuncia `actions` desde 0.4). La verificación en vivo del apply lo resuelve.
- **La señal `ActionInvoked` ya existe** con la firma correcta `(id, action_key)` — no hay cambio de protocolo, solo pasar la key correcta.

## Goals / Non-Goals

**Goals:**

- Botones visibles, clickeables y honestos: cada click emite SU key; caps que se cumplen.
- Fila integrada al layout con la fuente única de métricas — sin divergencia altura/dibujado ni solapes (spec `toast-stack` intacto).
- action-icons "attempt" con fallback a texto: nada se rompe si el icono no existe.

**Non-Goals:**

- `inline-reply` (cap + campo de texto + `NotificationReplied` + keyboard layer-shell): fase 2, change propio.
- `sound`, `inhibitions`, `ActivationToken` (emitir el token): fuera de scope.
- Estilos por acción (colors por button, urgency): no.
- Render de botones en el dashboard/history replay.

## Decisions

### D1 — Fila de botones: segmentos tipo "Ver más", no píldoras sueltas

Una única banda bajo el body, dividida en hasta 3 segmentos iguales (o ancho proporcional al texto, con mínimo): fondo accent al 22% como la barra "Ver más", separaciones de 8 px entre segmentos, texto Manrope `_APP_FS`, hover por segmento (0.22→0.38 como feedback, análogo al tinte de franja). Antecedente del repo: la barra "Ver más" demostró que la banda funciona anti-misclick y visualmente; píldoras sueltas agregarían una forma nueva sin ganancia. *Alternativa rechazada*: botones flotantes estilo pill — rompe el lenguaje de bandas del toast.

### D2 — `_action_rects`: la lista de hitboxes, mismo patrón que `_expand_rect`

`_draw` publica `[(rect, key, label, icono?)]` por botón; `_on_button_press` las consulta ANTES del click del cuerpo (después de franja y barra — un click en botón nunca es franja por geometría, pero el orden explícito evita fall-through). `on_click` gana parámetro: `on_click(action_key=None)` — `None` = click del cuerpo (default, igual que hoy); con key = botón. El daemon: `_on_action_invoked(nid, action_key=None)` → si hay key, la usa directa; si no, `_pick_action_key` como hoy. *Alternativa rechazada*: un callback nuevo `on_action` — dos caminos para lo mismo; uno con parámetro default es menos superficie.

### D3 — `default` y dedup de acciones: filtrado al parsear

El widget recibe la lista de actions ya parseada (pares), filtra `default`, deduplica keys (la primera gana — un sender que repite key es bug suyo) y corta en 3. El label con ellipsis Pango si no cabe su segmento. El parseo vive en el daemon o en el widget — decisión: en el WIDGET (`__init__`), porque el render es del widget y el daemon ya guarda la lista cruda para el history (no se pierde nada en disco).

### D4 — action-icons: icono 16 px + label (no icon-only)

Con el hint: se resuelve el key como icono del tema a 16 px (`_icon_from_theme`, la cadena existente) y se dibuja icono + label. La spec pide "attempt to interpret as icon"; el icon-only puro (label solo como accesibilidad) queda descartado por legibilidad — el VDG de KDE desaconseja iconos solos y un botón "✉" sin texto es peor que "✉ Marcar como leída". Fallback: icono no resuelve → solo label, mismo slot sin hueco. *Alternativa rechazada*: icon-only — legibilidad y el HIG en contra.

### D5 — Métrica de la fila en la fuente única

Constante nueva `_ACTIONS_ROW_H` (28 px, alto de la barra "Ver más") + `_ACTIONS_GAP` (8 px) consumidas por `_draw` Y `calc_card_height`/`_rows_above_body` donde hoy se suma `_BTN_H + _BTN_GAP`. La fila se dibuja entre el body y la barra "Ver más"; con ambos presentes el orden es body → botones → barra. Regla: la altura de card de un toast con N botones y overflow es inequívoca de derivar — un test de consistencia lo fija (mismo invariante que `test_layout_consistency`).

### D6 — Caps y spec_version

`GetCapabilities` suma `"action-icons"`; `GetServerInformation` reporta spec `"1.3"`. `sound` NO se anuncia (no se reproduce nada — el hint `sound-file` se sigue ignorando como hoy, sin mentir). `actions` sigue anunciado — ahora rendido.

### D7 — Verificación en vivo con clientes reales (el "tener cuidado" del usuario)

Tasks de verificación en vivo post-implementación, con tres clientes distintos: (a) `notify-send --action` (path directo, libnotify ≥0.8 — verificable con `notify-send -A settings=Ajustes`), (b) el **Telegram portable** del usuario (mandar un mensaje y documentar qué actions llegan al history — resuelve el misterio del dataset `[]`), (c) una noti de navegador (regresión: default + label compuesto intactos). El dataset (`history.jsonl`) es el artefacto de evidencia.

## Risks / Trade-offs

- [Alturas de card cambian para toasts con actions] → intencional; knock-on del tablero como task (mocks + cotas re-derivadas, worktree on-demand).
- [Labels largos rompen la fila] → ellipsis Pango por segmento (ya existe el patrón del label de app).
- [Senders que mandan keys duplicadas o actions impares (lista corrupta)] → dedup al parsear + tolerancia a lista impar (el último suelto se ignora) — robustez defensiva, no spec.
- [El misterio del dataset revela que el Telegram portable NO manda botones aunque el source lo diga] → la verificación en vivo lo documenta; el feature sigue valiendo para notify-send, KNotifications y el 17.3% del dataset con actions; si Telegram no reacciona, se investiga su versión específica (task condicional).
- [El click del cuerpo con botones cambia el área útil] → no: los botones consumen solo su rect; el resto del cuerpo mantiene el behavior default.

## Migration Plan

1. Tests rojos (render de fila, key por botón, default invisible, action-icons + fallback, layout sin solapes).
2. Implementación D1-D6, suite verde.
3. Metatest de sensibilidad (bug inyectado: click de botón → key default).
4. Verificación en vivo con los 3 clientes (D7) + documentación del hallazgo Telegram.
5. Tablero: mock con botones y alturas re-derivadas, `--comparar` verde.
6. Bump MINOR → 0.9.0 en el commit `feat:`, restart, `busctl` verificación.
7. Rollback: `git revert`; sin datos ni protocolo involucrados.

## Open Questions

- Ninguna que bloquee. Ancho de segmentos (iguales vs. proporcionales al texto) se cierra en implementación con screenshot — ambos cumplen el spec. El follow-up `inline-reply` queda fuera de este change y documentado en la proposal.
