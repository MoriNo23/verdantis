# Design

> **Alcance ampliado durante la aplicación (2026-10-04).** El change nació para
> el cap del "..." (spec `toast-body-colapso`). Al verificar en vivo, el usuario
> señaló que el renglón dejaba hueco al final; se añadió la spec
> `toast-body-ajuste` (justificar) y se acuerdo aplicar el wrap ANTES de
> re-derivar el tablero (D4), para que las alturas se deriven una sola vez.

## Context

Ver `proposal.md` (Why) y el delta `toast-body-colapso`. Estado verificado empíricamente durante la exploración (repro headless con el font map y Manrope de producción):

- **La heurística**: `_draw_text` (l.901) y `_body_metrics` (l.385) presupuestan el cap como `max_lines × int(font_size × 1.6) × PANGO_SCALE` — con la body font 11 son 17.6 px/línea, pero **la línea lógica real de Manrope 11 mide 21.00 px** (medida del logical rect de la línea 0; consistente: 6 líneas naturales = 126 px = 6×21).
- **El síntoma**: presupuesto cap=3 (52.8 px) → caben 2 líneas; cap=2 (35.2 px) → cabe 1 — y un body de exactamente 2 líneas no tiene overflow (cap=2, sin botón "Ver más"), así que el "..." tras 1 línea deja texto ilegible.
- **Modo negativo de `set_height` descartado por evidencia**: en este binding/font map los valores negativos se comportaron errático (-N pelado → 2N líneas; -N×SCALE → sin límite) — semántica poco fiable, no se usa.
- **Modo positivo validado**: `set_height(N × altura_real_de_línea × PANGO_SCALE)` corta exacto en N para caps 1/2/3/5, **sin necesidad de slack** (el borde exacto 3×21=63 px mantiene las 3 líneas). Tabla de la exploración: cap=1→1, cap=2→2, cap=3→3, cap=5→5, h = N×21 exacto en todos.
- La altura de línea puede variar por escala de resolución (`font_scale` 0.85/0.92) o por markup con spans — por eso la medida se toma **del propio layout ya configurado** (línea 0), no de una constante global.
- `calc_card_height` no se toca: hereda vía `_body_metrics` (fuente única de la métrica, regla de AGENTS).

## Goals / Non-Goals

**Goals:**

- El "..." cae al final de la línea exacta del cap (3 con overflow; nada en bodies de ≤2 líneas).
- Los renglones del body llegan al margen de la columna, justificados y sin
  cortar palabras (alcance ampliado, D4bis).
- Medición y dibujado comparten literalmente la misma fórmula de presupuesto — cero posibilidad de divergencia altura/wrap.
- Fix mínimo: solo la línea del presupuesto en dos funciones gemelas.

**Non-Goals:**

- No se cambia `_MAX_VISIBLE_LINES` (sigue en 3) ni la lógica de `has_more`/botón "Ver más".
- No se cambia el modo de wrap (WORD_CHAR se conserva) ni el sanitizado de markup;
  el ajuste al margen es con `set_justify`, no reenvolviendo (D4bis).
- No se toca el título ni el label de app (ellos ya son 1 línea + ellipsis por diseño propio).

## Decisions

### D1 — Presupuesto medido, no estimado

`line_h = layout.get_line_readonly(0).get_pixel_extents()[1].height` sobre el layout YA configurado (font + text + width + wrap) y el cap pasa a ser `set_height(int(max_lines * line_h) * PANGO_SCALE)`. La consulta fuerza el shaping del layout, así que la medida es de la línea real que se va a dibujar — con la escala, el font y el markup que apliquen a ESE layout. *Alternativa rechazada*: seguir con heurística calibrada (p. ej. `fs × 1.9`) — recalibrar una constante mágica repite el bug con la próxima fuente/escala.

### D2 — Misma fórmula en las dos gemelas, sin tercer helper

`_body_metrics` y `_draw_text` hacen la misma secuencia (crear layout → font → text → width → wrap) y solo difieren en el uso (medir vs. pintar); ambas reemplazan su línea de `set_height` por la fórmula de D1. *Alternativa rechazada*: extraer un helper compartido — son 2 líneas idénticas en 2 funciones que ya son gemelas por diseño; un helper agrega indirección sin proteger nada nuevo (el metatest de sensibilidad es el que realmente vigila que no diverjan).

### D3 — Sin slack en el presupuesto

El borde exacto (presupuesto = N × line_h) mantiene la línea N — validado empíricamente. Un slack (+1 px) no cambia el resultado y añade un número mágico nuevo; se prefiere el presupuesto exacto. Si una fuente futura exigiera slack, el test del contrato lo dirá con el nombre del caso.

### D4bis — Justificar en vez de `CHAR` para llenar el margen

Al verificar en vivo, el renglón 1 del body dejaba 23-43 px de hueco: con
`WORD_CHAR` Pango corta en palabra y deja el espacio del corte al final. Se
eligió `Pango.Layout.set_justify(True)` (Pango ≥1.50: booleano, no el enum;
estira los espacios inter-palabra de los renglones parciales). *Alternativas
descartadas*: `WrapMode.CHAR` llena el margen pero parte palabras ("amistos/o") —
inaceptable en prosa corta; `CHAR` + guionado no existe en Pango (no hyphenate);
`set_justify_last_line` no se toca: la última línea del párrafo queda a la
izquierda, que es lo correcto. El wrap sigue siendo `WORD_CHAR` (justificar
mueve los espacios, no los cortes) y la misma línea va en las dos gemelas.

### D4 — Knock-on del tablero como tarea del propio change

Con el fix, un body con overflow reserva 3×21 = 63 px (antes 42 px) → la altura del mock "body largo" del tablero cambia (148 px → lo que `calc_card_height` derive). La tarea recrea el worktree de diseño on-demand (como quedó documentado en AGENTS tras remover los worktrees): `git worktree add ../verdantis-diseno diseno-demos` → merge main → `--self-test` re-deriva el esperado → actualizar el mock en Lunacy + re-exportar manifiesto real → `--comparar` verde → commit → `git worktree remove`. *Alternativa rechazada*: change separado para el tablero — la actualización es un único mock y ya hay precedente de task de tablero dentro de un change de layout (el change de imagen izquierda).

## Risks / Trade-offs

- [Alturas de card cambian para bodies con overflow] → intencional: es la corrección (63 px reales en vez de 42 px truncados); el validador del tablero es el detector, la tarea lo cubre.
- [La medida por layout agrega una consulta de extents por body] → coste despreciable (un shaping que Pango haría igual al pintar; la medición ya ocurre hoy con `get_pixel_extents`).
- [Line height distinto dentro del mismo layout por spans de markup (bold agranda la run)] → el cap usa la altura de la línea 0; si un span intermedio crece su línea, el presupuesto sigue siendo N×line0 y Pango puede cortar en el borde con una línea más alta — caso degenerado, el texto igual muestra N líneas completas (el corte es por cantidad, no por px sobrantes).
- [Bodies con `\n` explícitos] → sin cambio de comportamiento respecto del fix (el cap por presupuesto mide igual); el histórico pitfall de `\n`+set_height que colapsaba todo a una línea fue del URL inyectado (resuelto por `_strip_urls`) — este fix no lo reintroduce porque el presupuesto ahora ES la altura real de las líneas.

## Migration Plan

1. Tests rojos primero: 2 líneas completas / 3 + "..." al final de la tercera / coherencia de altura reservada (miden el estado actual y fallan por el colapso).
2. Fix mínimo (D1/D2 en las dos funciones), suite completa verde.
3. Metatest de sensibilidad: inyectar la heurística `fs×1.6` y verificar que el contrato la detecta.
4. Tablero: re-derivar (D4), `--self-test` + `--comparar` verde.
5. Bump PATCH → 0.8.1 en el commit `fix:`, restart del servicio, `busctl` → "0.8.1", verificación en vivo (noti de 2 líneas → completa; noti larga → 3 líneas + "..." al final de la tercera).
6. Rollback: `git revert` del fix; sin datos ni API involucrados.

## Open Questions

- Ninguna que bloquee: la interpretación del pedido ("salto de líneas exacto para que quepa bien") quedó confirmada por el usuario — el ellipsis cae tras las líneas que corresponden, nunca tras una de menos.
