# Design

## Context

`crapper` (CRAP = `CC² × (1 − cobertura)³ + CC`) marqueó `_find_desktop_file`
con CRAP 121 —el peor del repo—: CC 15, 22% de cobertura. La hipótesis
inicial era "complejidad sin testear, hay que testearla". La auditoría de
callers la desmintió: **nadie la llama**.

Evidencia (medida, no inferida):

```
$ grep -rn "_find_desktop_file" --include="*.py" .
src/wayland_popup.py:85          ← la definición
src/wayland_popup.py:128         ← comentario que la menciona
src/wayland_popup.py:171         ← comentario que la menciona
tests/test_icon_resolution.py:42 ← test que existe solo para testearla
tests/test_icon_resolution.py:45
```

Los dos resolutores reales (`_get_app_icon_from_desktop:135` y
`_get_app_display_name:178`) llaman a `_exact_desktop_file`. El test que la
mantiene viva crea un `.desktop` con nombre exacto (`_make_desktop(tmpdir,
"ZuluBrowser", "zulubrowser", ...)`) y consulta `"ZuluBrowser"`, así que resuelve
por la estrategia 1 (exacta) — ni siquiera entra al difuso que.funcionalmente
nunca ejercitó.

## Goals / Non-Goals

**Goals:**
- Que el archivo más tocado del repo no lleve 15 branches muertos.
- Que la regla de "solo match exacto" quede vigilada por un test, no por un
  comentario.

**Non-Goals:**
- No se rediseña la resolución de iconos ni `_get_app_icon_from_desktop`.
- No se cambia `_exact_desktop_file`, que es el camino vivo.
- No se reescribe `_rebuild_desktop_cache` (aunque también aparece en la tabla
  de crapper con CC 9: esa sí es código vivo que merece otro día).

## Decisions

### D1 — Borrar, no testear ni deprecar

Un match difuso vivo con 22% de cobertura es una trampa: la spec dice que está
prohibido, pero el código lo ofrece. La tentación-era "marcarlo como deprecated
y testearlo para que quede documentado el riesgo"; se descarta porque mantiene
viva una superficie que la spec prohíbe y que ningún caller quiere.
*Alternativa descartada*: reducirlo a la estrategia exacta y renombrarlo — eso
sería re-implementar `_exact_desktop_file`, que ya existe.

### D2 — El metatest es el RED de este change

Este es el único de los tres changes con RED real: el test nuevo falla hoy
(`_find_desktop_file` existe) y pasa después de borrarlo. Sigue la convención
`test_tests_*.py` del repo. Su assert es sobre la ausencia del símbolo, que es lo
que la spec quiere, y no sobre el comportamiento de una función que ya no está.

### D3 — Los comentarios que la citan se apuntan a la regla

Las líneas 128 y 172 la nombran como el "arma de doble filo" que motivó la regla
de match exacto. Ese valor histórico se conserva, pero sin apuntar a código
muerto: pasan a decir que la regla existe *porque* el difuso rompía con PWAs de
Brave, y a nombrar a `_exact_desktop_file` como la única vía.

## Risks / Trade-offs

- [Que algo lo llame dinámicamente] → imposible: no hay `getattr` con ese
  nombre, ni string del nombre, ni plugin que lo importe (`verdantis_daemon`
  importa `_get_app_icon_from_desktop`, `_icon_from_theme` y
  `_extract_markup_url`, no la función difusa).
- [Perder el historial de por qué existe la regla] → mitigado por D3.

## Migration Plan

1. Metatest rojo: `_find_desktop_file` no debe existir en el módulo.
2. Borrar la función y su test.
3. Actualizar los dos comentarios.
4. Suite completa verde + grep sin referencias.
5. Re-correr crapper y confirmar que CRAP 121 desapareció.

Sin rollback necesario: si algo falla, `git revert` del commit.

## Open Questions

- Ninguna bloqueante.