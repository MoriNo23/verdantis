# body-hyperlinks Specification

## Purpose

Fija la postura del daemon frente a los hyperlinks del body: no implementa links clickeables ni los anuncia. Registra el contrato restaurado para que la promesa de `GetCapabilities` vuelva a ser verdad.

## Requirements

### Requirement: GetCapabilities no anuncia body-hyperlinks

`GetCapabilities` SHALL listar solo caps que el daemon sirve de verdad. `body-hyperlinks` SHALL estar ausente de la respuesta mientras los links del body no sean interactivos. Las caps servidas (`body`, `body-markup`, `actions`, `action-icons`, `icon-static`, `persistence`) SHALL permanecer.

#### Scenario: Respuesta sin body-hyperlinks
- **WHEN** un cliente consulta `GetCapabilities`
- **THEN** la lista no incluye `body-hyperlinks` e incluye `body` y `body-markup`

#### Scenario: El markup de link se aplanan
- **WHEN** llega una notificación con `<a href="URL">label</a>` en el body
- **THEN** el body visible muestra el label plano, sin estilo de link ni zonas de click diferenciadas

### Requirement: El click del cuerpo usa la URL única extraída

El click del cuerpo SHALL mantener el comportamiento vigente: la default action si el sender la registró y, si no, la URL única extraída del body/hints. La presencia de múltiples `<a href>` en el body no SHALL crear zonas de click diferenciadas.

#### Scenario: Body con dos links, click del cuerpo
- **WHEN** el body trae dos `<a href>` y el usuario clickea el cuerpo
- **THEN** se aplica la default action (o la URL única extraída como hoy) — nunca "la url del sector clickeado"
