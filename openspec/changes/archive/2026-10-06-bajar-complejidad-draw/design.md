# Design

## Context

Medido con crapper (CRAP = `CC² × (1 − cobertura)³ + CC`):

```
__init__  NotificationWidget   CC 34   84.0%   38.7
notify    NotificationManager  CC 35   89.8%   36.3
_draw     NotificationWidget   CC 30   89.8%   31.0
```

Con 90% de cobertura, el CRAP de `_draw` no señala tests faltantes: señala
complejidad. `_draw` ocupa las líneas 1093-1430 (338) y mezcla ocho
responsabilidades. Es el punto de mayor tensión del repo: este ciclo lo tocó
tres veces.

## Goals / Non-Goals

**Goals:**
- `_draw` legible como una lista de pasos, con un helper por responsabilidad.
- La métrica de layout testeable sin cairo.

**Non-Goals:**
- **No** reconectar `calc_card_height` a `_layout_metrics`. Sería tentador
  (haría desaparecer de raíz la clase de bug que `test_layout_consistency.py`
  vigila) pero su radio de impacto es `desired_height` + el stack manager + el
  dashboard + todos los tests de altura. Queda como non-goal explícito, con un
  test nuevo que asserta que ambos coinciden en una matriz de cuerpos.
- No se cambia el orden de dibujo, ni las constantes, ni el contenido de un
  comentario que explica un porqué.
- No se toca `_draw_actions_row` (ya está separada, CC 12).

## Decisions

### D1 — Un helper por responsabilidad, en el orden de dibujo de hoy

El orden NO es el del código: el closure `draw_text_pass` se **define** en 1201
pero se **invoca** en 1347/1354, después de la fila de botones (1269) y de la
barra (1278). O sea el texto se pinta el último de los contenidos del card. Un
refactor que moviera el bloque de texto junto a su definición cambiaría el
z-order. La partición lo declara explícito en el orquestador.

### D2 — `_layout_metrics` puro y sin cairo

Devuelve un namedtuple/tuple con todo lo que hoy se calcula en el medio de
`_draw`: `total_lines`, `cap`, `body_h`, `has_more`, `content_h`, `bands_h`,
`piso`, `text_h`, `row_h`. No recibe `cr` ni toca el widget más que para leer
`self._cuerpo`/`self._actions`/`self._expanded`. Eso lo hace testeable en un
proceso sin display, que es justo lo que hoy no se puede.

### D3 — La red es la fixture de píxeles, no una suite nueva

`tests/test_draw_golden.py` fija el hash SHA-256 de 16 configuraciones (app_name
sí/no × título plegado × expandido × corto/2 líneas/overflow × actions × franja
con y sin hover × banner) más el hash de los cuatro rects publicados. Los
hashes se generaron **antes** de tocar `_draw`. Tras el refactor, el test
afirma identidad byte a byte: eso convierte "no rompí nada" en una medición, no
en una opinión. Un refactor cuyo único riesgo es la regresión se verifica
contra el output previo, no contra la intención del autor.

### D4 — Los helpers devuelven, no publican

Cada helper publica lo que le corresponde vía `self` (el que dibuja el slot
publica `_image_left_rect`, el de la barra publica `_expand_rect`, etc.),
igual que hoy. No se inventa un objeto de resultado ni un paso de
"recolectar rects": los tests y el click routing leen esos atributos después
del draw.

## Risks / Trade-offs

- [Que el z-order cambie por una reordenación] → D1 lo declara y la fixture lo
  detecta (los píxeles del texto sobre la barra se ven).
- [Que la métrica se desincronice de `calc_card_height`] → es el status quo;
  por eso el non-goal de reconectarla viene con un test de coincidencia que
  cubre la matriz de cuerpos.
- [Más superficie (9 métodos en vez de 1)] → se acepta: son métodos privados,
  cada uno con una responsabilidad, y el orquestador queda como índice legible.

## Migration Plan

1. `_layout_metrics` puro + su test (sin display).
2. Fixture de píxeles con los hashes del render actual (ANTES de tocar `_draw`).
3. Extraer los helpers en el orden de D1, un paso por paso, con la suite verde
   entre cada paso.
4. Suite completa + fixture de píxeles verde.
5. Re-correr crapper: el CC de `_draw` tiene que bajar de 30.

## Open Questions

- Ninguna bloqueante.
