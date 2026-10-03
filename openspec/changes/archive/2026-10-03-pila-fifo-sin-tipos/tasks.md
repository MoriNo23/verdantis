# Tasks

## 1. Rama y tests rojos (TDD, worktree de testing)

- [x] 1.1 En `../verdantis-testing`, crear la rama `testing/pila-fifo` desde `main` (NO desde `testing/layout-imagen-izquierda`: esa rama está roja por diseño y esta tiene que poder mergearse a main sola) — verificación: `git branch --show-current` y `git diff main --stat` con sólo los archivos de este change.
- [x] 1.2 Tests del contrato nuevo en `tests/test_notify_batching.py`: burst de tipos mezclados sale en orden de llegada; un `critical` tardío no adelanta a los que ya están en cola; un `low` no se rezaqa al final; cerrar una activa hace entrar la siguiente por orden de llegada (sin reordenar). Actualizar `test_critical_priority_shown_before_low` al contrato nuevo (no se borra: pasa a ser "orden de llegada con tipos mezclados") y el docstring del módulo, que hoy anuncia "respetando prioridad (urgency)" — verificación: cada test FALLA hoy y el assert nombra el requisito (`toast-orden-llegada` / "La pila se ordena por llegada"); la falla real es el orden, no un error de colección.

## 2. Inventario del rojo y entrega

- [x] 2.1 Inventario del rojo documentado en esta task: qué tests fallan y por qué (mapeados al requisito que codifican), confirmando que no hay falsos positivos (imports/colección) — verificación: corrida completa de la suite con los fallos listados uno por uno.
- [x] 2.2 Commit `test:` en español en `testing/pila-fifo` declarando que la rama está ROJA por diseño hasta que este change la vuelva verde — verificación: `git log -1` en la rama.

---

# Inventario del rojo (task 2.1)

Rama `testing/pila-fifo` desde `main` (332e2c0). La rama sólo toca
`tests/test_notify_batching.py`:

```
.venv/bin/python -m pytest tests/ -q   →  4 failed, 230 passed (234 recogidos), 0 errores
```

**Sin falsos positivos**: los 4 fallos son asserts que nombran el requisito; no
hay errores de colección ni `ImportError`. Los 4 son el mismo defecto: la cola
se reordena por `urgency` (`_sort_pending`).

| Test | Requirement | Razón medida |
| --- | --- | --- |
| `test_burst_de_tipos_mezclados_sale_en_orden_de_llegada` | "Burst de tipos mezclados sale en orden de llegada" | la pila sale `[B critical, A normal, D normal, C low]` en vez de `[A, B, C, D]` |
| `test_un_critical_tardio_no_adelanta_a_la_cola` | "Un critical tardío no adelanta a la cola" | el primer pump muestra el `critical` (llegó tercero) en vez del primero |
| `test_un_low_no_se_rezaqa_al_final` | "Un low no se rezaqa al final" | pila `[critical, normal, low]`: el `low` que llegó segundo quedó último |
| `test_cerrar_una_activa_drana_por_llegada` | "Cerrar una activa no reordena el resto" | al cerrar entra la `critical` (nid 6) en vez de la siguiente por llegada (nid 7) |

## Tests verdes que también tienen que seguir verdes (contraparte)

- `test_la_urgencia_sigue_definiendo_la_vida_del_toast` (nuevo): la `urgency`
  sigue mandando en la duración (0.7×/1×/1.5×) y la opacidad (0.55/0.85/1.0) por
  toast. Asserta **por toast**, no por posición, así que es verde antes y
  después del fix: es lo que impide que "se apilen por llegada" termine en "la
  urgencia no significa nada".
- `test_burst_not_shown_all_at_once`: el reveal de a uno (`STAGGER_MS`) no se
  toca.
- `test_burst_order_preserves_fifo_for_same_urgency`,
  `test_closing_frees_slot_and_drains_queue` y
  `test_close_all_clears_pending_and_pump`: ya eran neutrales respecto del tipo.

## Cambio en tests existentes (no se borra nada)

`test_critical_priority_shown_before_low` fijaba el comportamiento viejo
("critical sale primero aunque llegue último"). Pasa a ser
`test_burst_de_tipos_mezclados_sale_en_orden_de_llegada`: el escenario sigue
vivo, con la expectativa nueva. El docstring del módulo también, que anunciaba
"respetando prioridad (urgency)".

## 3. Implementación en main

- [x] 3.1 Mergear `testing/pila-fifo` a main (la suite queda roja sólo por estos tests) y eliminar el reordenamiento por tipo: borrar `_sort_pending` y sus dos llamadas (`notify` y el drenado de `_close_id`) — verificación: `.venv/bin/python -m pytest tests/ -q` con 0 failed y los tests de orden verdes.
- [x] 3.2 Bump PATCH de `VERSION` en el mismo commit `fix:` (es un fix de comportamiento, no una feature) y verificación en vivo: secuencia `low → normal → critical` con `notify` y un burst mezclado; la pila debe verse en orden de llegada y las duraciones/opacidades distintas — verificación: `busctl --user call ... GetServerInformation` con la versión nueva y orden de pila observado sin reordenamientos.
- [x] 3.3 Archivar este change y devolver la rama `testing/pila-fifo` a un estado disposable — verificación: `openspec list` sin `pila-fifo-sin-tipos` y `git worktree list` con las 3 entradas.