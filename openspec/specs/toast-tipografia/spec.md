# toast-tipografia Specification

## Purpose

Fijar la escala tipográfica del toast para que la jerarquía se lea sin depender
solo del peso de la fuente, y que un body largo no empuje el contenido fuera de
la superficie de 360 px.

## Requirements

### Requirement: Jerarquía title > body > app

El toast SHALL usar una escala con título 13 px, body 10 px y label de app 10 px
en resolución de referencia (`font_scale=1.0`). Los tres tamaños SHALL bajar
solo por `font_scale` y SHALL conservar el orden `title >= body >= app` en toda
escala soportada (0.85 a 1.15), sin aplanarse a un mismo valor.

#### Scenario: Escala de referencia

- **WHEN** se dibuja un toast con `font_scale=1.0`
- **THEN** `_TITLE_FS` es 13, `_BODY_FS` es 10 y `_APP_FS` es 11

#### Scenario: Monitor chico

- **WHEN** el toast se dibuja con `font_scale=0.85`
- **THEN** los tres tamaños escalan pero el título sigue siendo ≥ al body y el body ≥ al de la app

### Requirement: El alto acompaña a la escala sin romper el cap

`calc_card_height` SHALL derivar el alto del body del mismo `_BODY_FS` que usa
el dibujo, de modo que al subir la escala el card crezca lo justo y el cap de 3
líneas siga vigente. Un body de más de 3 líneas SHALL NO producir un card de más
de 220 px de alto.

#### Scenario: Body largo

- **WHEN** el cuerpo tiene 120 palabras y hay botón Copiar
- **THEN** el alto calculado es ≤ 220 px y las líneas visibles siguen siendo 3 con ellipsis

#### Scenario: Fuente única

- **WHEN** cambia `_BODY_FS`
- **THEN** el cambio alcanza tanto al render (`do_snapshot`) como a las métricas (`calc_card_height`), sin constantes duplicadas de fuente en el widget
