# Proposal — Layout unificado con imagen izquierda + pila sin solapes

## Why

Cuatro problemas observados en el toast, todos verificados en código: (1) los toasts **se solapan** cuando uno cambia de alto — la pila solo se reposiciona al crear o cerrar un popup, así que expandir "Ver más" o el re-wrap por hover deja a los de abajo con el margen viejo; (2) la fila de app y el título quedan **hundidos** ~10 px por debajo del borde superior de la imagen izquierda (el bloque de texto se centra verticalmente y el piso de 80 px del slot lo empuja abajo); (3) el slot izquierdo **desaparece** cuando ninguna fuente resuelve y, con él, la coherencia: la variante sin-imagen (columna 332, fuentes 12/13, gap de 18 px) hace que la barra "Ver más" aterrice en otro lugar; (4) el nombre "avatar" confunde — no es un avatar de usuario ni de mensaje.

## What Changes

- **Pila sin solapes**: todo cambio de alto de un toast (expandir/contraer, re-wrap por hover) SHALL re-flowear las posiciones de toda la pila, respetando siempre el gap entre cards. El restack reutiliza el loop existente y compone con la re-sincronización de hover de 0.7.0.
- **Imagen izquierda siempre presente**: el slot de 80 px existe en todos los toasts. Cadena de contenido: imagen de la notificación (icono del tab / image-path / archivo) → icono de la app (`.desktop` exacto → tema) → placeholder con la inicial. La variante sin slot desaparece.
- **Columna única**: al estar el slot siempre, la columna de texto pasa a 240 px para todos (196 px en persistentes con hover). Muere la variante ancha de 332/288: fuentes unificadas de título 11 / body 11, el gap de 18 px del HR desaparece, la barra "Ver más" aterrizan igual en todos los toasts.
- **Texto alineado al top**: la fila de app y el título arrancan a la altura del borde superior del slot (el slot sigue centrado verticalmente en su fila); sin hundimiento.
- **Rename**: "avatar" → **imagen izquierda** en todo el código (`_avatar_pb`→`_image_left_pb`, `_AVATAR_W`→`_IMAGE_LEFT_W`, `_AVATAR_GAP`→`_IMAGE_LEFT_GAP`), comentarios, AGENTS.md y terminología de specs.
- Sin cambios: franja de descarte y X (hover-only), logo de 16 px de la fila de app y su placeholder, API DBus, resolución `.desktop` exacta.
- Versionado: bump MINOR → **0.8.0** (`feat:`).
- **TDD por worktrees** (regla del usuario): los tests de este contrato los escribe primero el change `tests-layout-imagen-izquierda` en el worktree de testing (rama que se mergea acá); este change implementa en **main**. Después, el change `actualizar-tablero-imagen-izquierda` lleva el demo de Lunacy a la geometría nueva en el worktree de diseño.

## Capabilities

### New Capabilities
- `toast-imagen-izquierda`: presencia y contenido del slot de imagen izquierda (cadena imagen de notificación → icono de app → placeholder), alineación del bloque de texto y columna única.
- `toast-stack`: posicionamiento de la pila de toasts — nunca solapes, gap respetado ante cualquier cambio de alto.

### Modified Capabilities
- `toast-iconos-app`: el requisito "Los iconos no cuadrados no se cortan" actualiza su terminología (el "avatar de 80 px" pasa a ser la "imagen izquierda de 80 px").
- `toast-franja-descarte`: las columnas del contrato de hover cambian con la imagen izquierda siempre presente (288/196 → 196 único; el ancho completo pasa de 332/240 a 240 único).

## Impact

- `src/wayland_popup.py`: `_draw` (alineación del texto, columna), `_eff_text_width` (columna única), `_rows_above_body` (gap del HR fuera), cadena del slot en `__init__` (placeholder 80 como último eslabón), rename en ~30 referencias.
- `src/verdantis_daemon.py`: wiring del restack on-resize; `VERSION` → 0.8.0.
- `AGENTS.md`: terminología imagen izquierda.
- Tests: llegan del change B (rama del worktree de testing) — este change los vuelve verdes.
- Tablero de diseño: las alturas y columnas documentadas cambian → el change A lo actualiza después de que esto esté verificado.
- **BREAKING**: ninguno externo (API DBus intacta); el layout interno unifica variantes.
