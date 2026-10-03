# Design

## Context

Ver `proposal.md` (Why) y los deltas (`toast-imagen-izquierda`, `toast-stack`, `toast-iconos-app`, `toast-franja-descarte`). Estado actual verificado en código:

- **Pila**: `set_stack_margin` se llama solo al crear (`_show_popup`) y al cerrar (`_close_id`); el camino `on_resize → _resize_card` (expandir, re-wrap por hover) redimensiona la propia ventana sin reposicionar a los demás → solape.
- **Texto hundido**: `ty = pad + (row_h - text_h) / 2` centra el bloque de texto; con el piso de 80 px del slot y contenido corto, app+título arrancan ~10 px bajo el top de la imagen.
- **Slot**: la cadena ya cae al icono de la app (`.desktop` exacto → tema, a 80 px); solo queda `None` cuando nada resuelve → sin slot → se activa la variante ancha (columna 332/288, fuentes 12/13, gap de 18 px del HR).
- **Placeholder 16 px existente**: `_make_placeholder_icon` (square redondeado + inicial centrada por caja de tinta) — lenguaje visual ya establecido para "app sin icono".
- La re-sincronización de hover tras mover ventanas (`_sincronizar_hover_tras_desplazar` dentro de `_apply_margins`, 0.7.0) compone con cualquier reposicionamiento futuro de la pila.

## Goals / Non-Goals

**Goals:**

- Gap constante entre cards ante cualquier cambio de alto, con el mismo loop de restack que ya existe al cerrar.
- Slot siempre presente con cadena completa (imagen → icono app → placeholder) y texto al top del slot.
- Una sola variante de layout (columna 240/196, fuentes 11/11): menos ramas, menos divergencia altura/wrap.
- TDD por worktrees: los tests de B (rojos, verificados) se mergean primero y este change los vuelve verdes en main.

**Non-Goals:**

- No se toca la franja de descarte/X (hover-only, spec vigente), el logo de 16 px de la fila de app, la API DBus ni la resolución `.desktop` exacta.
- No se actualiza el tablero de Lunacy (eso es el change A, después de que esto esté verificado).
- No se rediseña el placeholder 16 px: se reusa su lenguaje visual, escalado al slot.

## Decisions

### D1 — Restack on-resize: el manager envuelve el callback existente

El popup ya reporta sus resizes (`on_resize=self._resize_card` en `_build_ui`). El manager pasa un `on_resize` que primero redimensiona (la vía `_resize_card` actual) y después ejecuta el restack: el mismo loop `set_stack_margin(i)` que `_close_id` ya hace. Sin señales GLib ni observers: es un callback directo que ya existe. El hover-stale tras mover queda cubierto por `_sincronizar_hover_tras_desplazar` (que cuelga de `_apply_margins`). *Alternativa rechazada*: recalcular posiciones en el daemon por polling de `desired_height()` — reinvención del loop que ya existe.

### D2 — Placeholder 80 px como último eslabón de la cadena del slot

La cadena del slot gana un final: si imagen de notificación → icono de app → *placeholder con la inicial*. Se reutiliza `_make_placeholder_icon` (mismo square/inicial/centrado por caja de tinta) y se lo pasa por el clip circular del slot (`_make_circular`), igual que cualquier otro contenido del slot. El slot deja de poder quedar `None`: la rama `icon_size = 0` de `_draw` y la variante ancha mueren.

### D3 — Texto al top: `ty = pad`, fuera el centrado del bloque

El centrado vertical del bloque de texto (`(row_h - text_h) / 2`) se elimina; app y título arrancan en `pad`, al top del slot (que conserva su centrado `cy` en la fila). El piso `row_h = max(text_h, _ROW_MIN_H)` se mantiene — el slot sigue respirando con contenido corto; el espacio sobrante queda bajo el body, como hoy en el caso con imagen.

### D4 — Una sola variante: muere la rama sin-imagen

Con el slot siempre presente, todas las ramas `has_avatar` colapsan al caso con slot: `_eff_text_width` devuelve 240 siempre (196 con franja en hover persistente), `_rows_above_body` pierde el `_HR_GAP` condicional, y las fuentes se unifican en las de slot (título 11 / body 11). La fuente única de métricas se conserva: los mismos helpers alimentan `_draw`, `calc_card_height` y `_eff_text_width`.

### D5 — Rename "avatar" → "imagen izquierda"

Mapa: `_avatar_pb`→`_image_left_pb`, `_AVATAR_W`→`_IMAGE_LEFT_W`, `_AVATAR_GAP`→`_IMAGE_LEFT_GAP`; comentarios y docstrings de src; AGENTS.md (terminología). `_make_circular` y `_make_placeholder_icon` conservan su nombre (genéricos). Los tests los renombra B en su rama. El término "avatar" desaparece de src y docs. *Nombre elegido*: el usuario pidió "image left o algo más acorde" — en español del repo: **imagen izquierda**; identificadores en código `_image_left_*`.

### D6 — Orden de ejecución (regla del usuario, tres worktrees)

1. **B** (worktree testing, rama `testing/layout-imagen-izquierda`): tests rojos + renames, inventario del rojo verificado.
2. **C** (main, este change): merge de la rama de B como primer paso ("luego de la verificación" — se verifica el inventario rojo antes de tocar src), implementación hasta suite verde, bump 0.8.0, commit `feat:`.
3. **A** (worktree diseno): merge main, board a la geometría nueva, validador verde.

## Risks / Trade-offs

- [Columna 240 para todos = menos texto por línea en toasts sin imagen] → Trade-off explícito del usuario: coherencia visual > densidad de texto.
- [Alturas documentadas cambian] → cubierto por el change A con medidas re-derivadas; no se hardcodean números nuevos acá.
- [Restack mueve toasts bajo un puntero quieto] → ya cubierto por la re-sincronización de hover de 0.7.0 (spec `toast-franja-descarte`: "El estado de hover se resetea de forma confiable").
- [Resize frecuente por hover re-flowea la pila seguido] → el resize solo dispara cuando el alto realmente cambió (puerta de 0.7.0); el restack hereda esa puerta.
- [Rename rompe tests existentes] → B los renombra primero en su rama; este change los recibe ya actualizados por el merge.

## Migration Plan

1. Merge de la rama de B (suite roja por diseño).
2. Implementar D1-D5 en src; suite completa verde en main.
3. Bump `VERSION` → 0.8.0 en el commit `feat:`; `systemctl --user restart verdantis.service`; verificar con `busctl ... GetServerInformation`.
4. Verificación en vivo: pila de toasts, expandir el de arriba (los de abajo mantienen gap), hover en persistente (re-flow + X), toast de app sin icono (placeholder con inicial).
5. Rollback: `git revert` del commit feat; sin cambios de datos ni API.

## Open Questions

- Ninguna que bloquee. Decisiones cerradas con el usuario: división por worktrees (B→C→A), imagen izquierda siempre, rename a "imagen izquierda". Asunciones registradas (vetables al revisar los artifacts): placeholder del slot con inicial reutilizando el lenguaje del de 16 px, fuentes unificadas en las del slot.
