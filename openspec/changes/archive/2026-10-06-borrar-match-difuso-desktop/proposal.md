# Proposal — Borrar el match difuso de `.desktop` (código muerto)

## Why

Una corrida de [crapper](https://github.com/unclebob/crapper) (CRAP =
`CC² × (1 − cobertura)³ + CC`) marcó `_find_desktop_file` con **CRAP 121, el
pior puntaje del repo**: CC 15 con 22% de cobertura. La lectura obvia —"está
complejo y poco testeado, hay que testearlo"— era la respuesta de manual.

Al auditar los callers, el diagnóstico real es otro: **`_find_desktop_file` no
lo llama nadie**. En todo el repo su único caller es
`tests/test_icon_resolution.py::test_find_desktop_file_by_app_name`, un test que
existe solo para testearlo. Los dos resolutores reales usan la vía exacta:

| Caller | Qué usa |
|---|---|
| `_get_app_icon_from_desktop` (línea 135) | `_exact_desktop_file` |
| `_get_app_display_name` (línea 178) | `_exact_desktop_file` |

Y el test tampoco ejercita el camino difuso: crea un `.desktop` con nombre
exacto, así que pasa por la estrategia 1, que es exactamente lo que
`_exact_desktop_file` ya resuelve.

O sea: 38 líneas y 15 branches en el archivo más tocado del repo, que
`AGENTS.md` ya prohíbe en otro lugar ("Resolución de `.desktop`: SOLO match
exacto; el match difuso rompe con PWAs de Brave") y que sobrevivió como código
muerto con un test que lo mantiene con vida artificial.

## What Changes

- **BREAKING**: ninguno. Ningún camino de producción llama a la función, así que
  borrarla no cambia un solo píxel del render.
- Se borran `_find_desktop_file` (38 líneas) y su test.
- Los dos docstrings que la citan como referencia histórica pasan a apuntar a la
  regla (`_exact_desktop_file`) en vez de a código muerto.
- Un metatest nuevo exige que el módulo **no** tenga match difuso, para que
  nadie lo vuelva a agregar.

## Capabilities

### Modified Capabilities

Ninguna: la resolución de `.desktop` ya está especificada como match exacto en
`toast-iconos-app`, y el código muerto no participaba de ella. No hay delta que
sincronizar — el código es lo que se estaba atrasando con la spec.

## Impact

- `src/wayland_popup.py`: −38 líneas (CC −15).
- `tests/test_icon_resolution.py`: −1 test.
- `tests/test_tests_icon_resolution.py`: +1 metatest.
- Sin cambios de API DBus, daemon, render ni specs.