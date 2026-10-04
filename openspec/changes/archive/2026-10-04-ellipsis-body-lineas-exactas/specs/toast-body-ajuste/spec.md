# Spec Delta

## Purpose

Define cómo se ajusta el texto del body dentro de la columna: el renglón debe
llegar al margen sin cortar palabras.

## ADDED Requirements

### Requirement: El body llena el margen de la columna

Los renglones del body SHALL estirar sus espacios inter-palabra hasta el margen
derecho de la columna de texto, de modo que el texto termine en el borde en vez
de dejar el hueco del corte de palabra. El ajuste SHALL ser por justificación:
el wrap sigue siendo por palabra y ninguna palabra SHALL quedar partida.

La justificación SHALL aplicarse en la medición y en el dibujado por igual (el
wrap del body es una fuente única).

#### Scenario: El renglón que corta antes de la palabra siguiente

- **WHEN** un renglón no alcanza a la palabra siguiente porque no entra entera
- **THEN** sus espacios se estiran hasta el margen y el texto llega al borde,
  sin quedar un hueco visible al final

#### Scenario: Ninguna palabra queda partida

- **WHEN** el body se ajusta para llenar el margen
- **THEN** los cortes de línea siguen cayendo entre palabras (el modo de wrap es
  por palabra), nunca dentro de una palabra

#### Scenario: El ajuste no parte el "..." del cap

- **WHEN** el body se colapsa a las líneas del cap y el último renglón lleva el
  marcador de texto oculto
- **THEN** el marcador queda al final del renglón y el renglón sigue llegando al
  margen

#### Scenario: Medición y dibujado ajustan igual

- **WHEN** el body se dibuja colapsado
- **THEN** la medición de la altura y el dibujado usan el mismo ajuste, así el
  texto no se desborda ni deja la barra "Ver más" desalineada
