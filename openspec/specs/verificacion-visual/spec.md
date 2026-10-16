# verificacion-visual Specification

## Purpose

Fija quién valida la apariencia de los toasts: el reporte visual del humano, no la auto-inspección del agente.

## Requirements

### Requirement: La confirmación visual de los toasts la da el humano

El agente SHALL NOT verificar visualmente los toasts: no toma capturas de pantalla
(`spectacle`, `grim`, `import`), no lee imágenes de la pila ni inspecciona la
pantalla por su cuenta. La fuente de verdad de cómo se ven los toasts SHALL ser el
reporte visual del usuario. El agente SÍ puede mandar notificaciones de prueba para
que el usuario las mire.

#### Scenario: El usuario reporta un toast mal puesto
- **WHEN** el usuario reporta cómo ve un toast (posicionado, tapado, colgado, un render de más)
- **THEN** el agente corrige el código a partir de ese reporte
- **AND** no pide ni toma una captura para confirmarlo

#### Scenario: El agente cambia el render
- **WHEN** el agente cambia cómo se dibuja o se posiciona un toast
- **THEN** manda una notificación de prueba para que el usuario la mire
- **AND** espera el veredicto del usuario en vez de auto-verificarse
