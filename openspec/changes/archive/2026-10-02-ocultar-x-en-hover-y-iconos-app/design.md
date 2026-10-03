# Design

## Context

Ver `proposal.md` (Why) y los specs de `toast-franja-descarte` y `toast-iconos-app` (requisitos). Estado actual relevante, verificado en código:

- **Franja/X**: el gate de dibujado ya es hover-dependiente (`if self._persistent and self._hover` en `_draw`, desde el commit 772cf00) — sin hover no se dibuja tinte ni X. Lo que queda del pedido es el **espacio**: `_eff_text_width()` resta los 44 px para persistentes *siempre*, `calc_card_height(..., persistent=True)` vuelve a restarlos internamente, y `_draw` calcula `strip_w` con `self._persistent` (sin hover). Resultado: columna 288 px permanente para persistentes (196 con avatar).
- **Eventos**: `enter-notify`/`leave-notify`/`motion-notify` ya están conectados (`ENTER_NOTIFY_MASK`/`LEAVE_NOTIFY_MASK`/`POINTER_MOTION_MASK`); `_hover` y `_hover_close` ya existen y `_on_leave` resetea ambos.
- **Altura/resize**: `toggle_expanded` ya redimensiona por la vía `on_resize → WaylandPopup._resize_card` (layer-shell, `try_force_commit`). El stack solo hace reflow cuando un toast se cierra (`_close_id` → `set_stack_margin` por índice); **expandir un toast apilado hoy tampoco reflowea la pila** (solapa al de abajo) — limitación preexistente.
- **Iconos 16 px**: la cadena en `NotificationWidget.__init__` es archivo (`os.path.exists`) → `.desktop` exacto → tema por `app_icon` → tema por `app_name`. El daemon construye `app_icon_file = _local_path(app_icon) if app_icon and os.path.exists(_local_path(app_icon)) else ""` y crea el popup con `kwargs["app_icon"] = app_icon_file`: los **nombres de tema pelados mueren acá** (llegan como `""` al widget y su `_icon_from_theme(app_icon)` es código muerto en la práctica). `_resample` hace center-crop del cuadrado central cuando `w != h` (los iconos no cuadrados se cortan) con HYPER. La fila dibuja el texto con offset `+20` solo si hay logo.
- **Tests que fijan el comportamiento actual**: `test_persistent_reserves_strip_in_text_width`, `test_eff_text_width_shrinks_for_persistent`, `test_expand_strip_reserves_close_strip` (action zones), `test_hover_close`, `test_icon_resolution`, `test_layout_consistency`, y metatests `test_tests_*.py`.
- **Tablero DISEÑO-DEMOS**: `validar_geometria_tablero.py` deriva las columnas (332/240/288) de las constantes de `wayland_popup` — la constante `_CLOSE_STRIP_W = 44` sigue existiendo (en estado hover), así que el validador no cambia.

## Goals / Non-Goals

**Goals:**

- Mantener la fuente única de métricas de layout (regla de AGENTS.md): el ancho hover-dependiente vive en `_eff_text_width`/`_draw`, no se recomputa a mano.
- Transiciones de hover sin bucles de eventos ni solapes internos del card.
- Una sola autoridad de resolución de iconos (el widget); el daemon solo pasa los datos crudos.
- Suite verde + metatests de sensibilidad que detecten las regresiones específicas (franja dibujada sin hover; icono cortado; nombre pelado perdido).

**Non-Goals:**

- Reflow de la pila al redimensionar por hover/expand (limitación preexistente compartida con expandir; el solape es transitorio).
- Cambios en el avatar de 80 px (cover-crop circular), en la barra "Ver más"/chevrón, en el tablero Lunacy, o en el formato del historial/dashboard.
- Reintroducir match difuso de `.desktop` o cambiar la interpolación HYPER.

## Decisions

### D1 — El ancho hover-dependiente vive en la métrica, no en el dibujado

`_eff_text_width()` resta `_CLOSE_STRIP_W` solo cuando `self._persistent and self._hover`; `_draw` calcula `strip_w = _CLOSE_STRIP_W if (persistent and hover) else 0`. `calc_card_height` **deja de restar internamente** (se elimina el `if persistent: text_width -= ...` y el parámetro): el caller ya pasa el ancho efectivo (`desired_height` pasa `self._eff_text_width()`), con lo que la altura y el wrap nunca divergen. `_apply_margins` (offset del stack sin card aún) usa el ancho **sin hover** — un card sin renderizar nunca está hovered y los márgenes quedan estables. *Alternativa rechazada*: subtract en dos lugares (estado actual) — es exactamente la divergencia altura/wrap que el docstring de `calc_card_height` prohíbe.

### D2 — Transición de altura: reflow honesto con resize por la vía existente

Al entrar/salir el hover de un persistente, se recomputa `desired_height()`; si cambió, se llama `self._on_resize(nuevo_h)` (la misma vía de `toggle_expanded`). Solo se dispara si el alto realmente cambió (un body de 1-2 líneas no cambia líneas al pasar de 332→288 y no genera resize).

*Alternativas consideradas*: (a) overlay sin re-wrap (texto siempre 332, franja encima) — rechazada por el usuario, pidió wrap; (b) congelar la altura al máximo de ambos estados — deja slack vertical variable, que es el "espacio ocupado" en otro eje; (c) ellipsize del re-wrap sin resize — esconde contenido real mientras haces hover, justo cuando estás leyendo.

Contención de riesgos (ver Riesgos): el card está anclado arriba/derecha y crece hacia abajo, así que un puntero en el centro del card queda dentro tras el resize (sin leave espurio). Si la verificación en vivo detecta oscilación enter/leave en el borde inferior, el fallback ya diseñado es **congelar el tamaño de la window mientras dure el hover** (el card interno re-wrappea igual; solo no se toca la ventana) — nunca un loop.

### D3 — Reset del hover: verificación dirigida, no plomería especulativa

Los masks y handlers ya existen y Wayland entrega `pointer.leave` cuando la superficie se aparta del puntero. No se agrega plomería de eventos a ciegas; en su lugar: (1) test pixel-level que renderiza sin hover y afirma cero píxeles de franja/X, y con hover y afirma presencia; (2) verificación en vivo con el daemon real (hover → mover fuera → X invisible; cerrar un toast vecino con el puntero quieto → sin X pegada). Si la verificación muestra estados pegados, ahí sí se agrega el endurecimiento puntual (re-chequeo por motion, `grab-broken`) — con el repro en la mano.

### D4 — Adquisición de iconos: el daemon deja de descartar el `app_icon` crudo

`kwargs["app_icon"] = app_icon_file or app_icon` — si hay archivo normalizado se pasa el path (igual que hoy); si no, se pasa el string **crudo** del sender. La cadena del widget ya sabe qué hacer con un nombre pelado: falla `os.path.exists`, pasa por el `.desktop` exacto y cae al `_icon_from_theme(app_icon)` que hoy estaba muerto. Brave (que manda `file:///tmp/...`) no cambia: su path existe y sigue ganando. El replay del dashboard guarda el `app_icon` crudo en historial, así que también se beneficia. *Alternativa rechazada*: kwarg nuevo (`app_icon_name`) — toca la firma de `WaylandPopup`/`NotificationWidget` y reparte la autoridad de resolución entre daemon y widget.

### D5 — Render 16 px: modo `contain` con letterbox

`_resample` gana un parámetro `mode`: `"cover"` (center-crop actual, default — avatars) y `"contain"` (escalar preservando aspect y compositar centrado sobre un pixbuf transparente de `size×size`). El modo se hilvana por `_get_app_icon_from_desktop(app_name, size, mode)`; **solo la cadena del logo de 16 px usa contain** — el avatar y su fallback siguen en cover (el clip circular es por diseño). *Alternativa rechazada*: cambiar `_resample` globalmente a contain — deformaría/afectaría el slot circular del avatar.

### D6 — Placeholder del logo: slot sintetizado al final de la cadena

Si la cadena entera falla, se sintetiza un pixbuf 16×16: cuadrado redondeado `#313244` (surface de la paleta Catppuccin del toast) con la inicial del nombre de app en Manrope Bold ~9 px en `#A6ADC8`. Se materializa en `__init__` (no en `_draw`), así que fluye por el mismo camino de dibujado y el offset `+20` del texto pasa a ser **siempre constante** (layout de fila estable, como pide el spec). *Alternativas rechazadas*: dejarlo vacío (es la queja original); reusar el avatar (semántica distinta: es icono de pestaña, no de app); glifo genérico (menos informativo que la inicial).

### D7 — Tablero DISEÑO-DEMOS: sin ediciones, validador como gate

`_CLOSE_STRIP_W = 44` sigue existiendo como constante (se usa en hover), así que el validador del tablero sigue derivando 332/240/288 en verde. El mock "05 · Persistente + franja" y el callout 8 pasan a representar el **estado con hover** (nota semántica, sin tocar Lunacy). El `--self-test` del validador se agrega como verificación de la tarea.

## Risks / Trade-offs

- [El resize por hover puede solapar transitoriamente al toast de abajo] → Limitación preexistente (expandir ya lo hace); solo persistentes cuyo re-wrap cambia líneas y solo mientras dura el hover. Si en la verificación viva molesta, fallback de D2 (window congelada durante hover).
- [Oscilación enter/leave si el borde del card pasa por debajo del puntero en el resize] → Resize solo cuando cambia el alto real; card anclado arriba (crece hacia abajo, el puntero del centro no sale); fallback D2 documentado. Se verifica en vivo con el daemon corriendo antes de cerrar el cambio.
- [Salto visual del texto al re-wrappear en hover] → Trade-off aceptado explícitamente por el usuario (pidió wrap dinámico, no overlay).
- [Nombre pelado que coincide con un archivo relativo del CWD] → `os.path.exists` sobre un nombre de tema es un falso positivo ínfimo; el perdedor sigue al tema/desktop por app_name. No vale plomería extra.
- [El offset `+20` pasa a ser siempre constante → textos de fila se corren 20 px vs. hoy sin logo] → Comportamiento buscado (fila estable); los tests de layout que fijan el offset se actualizan en el mismo commit.
- [Tests actuales fijan el comportamiento viejo] → TDD del repo: primero se actualizan/escriben los tests al contrato nuevo (rojo), luego el fix mínimo, luego suite verde.

## Migration Plan

1. Implementar (tests primero), suite completa verde sin `test_uv_migration.py`.
2. Bump `VERSION` → 0.7.0 en `src/verdantis_daemon.py` (mismo commit `feat:`, reportado al usuario).
3. `systemctl --user restart verdantis.service` y verificar con `busctl --user call ... GetServerInformation`.
4. Verificación visual en vivo: hover en persistente (wrap + X), salida del puntero (X invisible, ancho 332), iconos con senders reales (Brave, una app de sistema, una app desconocida → placeholder).
5. Rollback: revert del commit; no hay cambios de formato de datos ni de API.

## Open Questions

- Forma final del placeholder (inicial vs. glifo neutro, radio exacto): cerrable en implementación con un screenshot, sin tocar los specs.
- Si la verificación en vivo detecta estados de hover pegados (D3), el endurecimiento se decide con el repro concreto; hoy no hay evidencia de que exista.
