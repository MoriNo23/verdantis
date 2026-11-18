# verificacion-visual Specification

## Purpose

Fija quién valida la apariencia de los toasts: el agente, con inspección visual propia.

## Requirements

### Requirement: La confirmación visual de los toasts la da el agente

El agente SHALL verificar visualmente los toasts: puede tomar capturas de pantalla
(`spectacle`, `grim`, `import`), leer imágenes de la pila e inspeccionar la pantalla
por su cuenta. El agente SÍ puede mandar notificaciones de prueba. El reporte del
usuario es opcional y NO excluyente: aporta percepción humana, pero el agente no
espera por él para dictaminar.

#### Scenario: El agente cambia el render

- **WHEN** el agente cambia cómo se dibuja o se posiciona un toast
- **THEN** manda una notificación de prueba, toma una captura e inspecciona el resultado
- **AND** dictamina y corrige por su cuenta, sin esperar el reporte del usuario

#### Scenario: El usuario reporta un toast mal puesto

- **WHEN** el usuario reporta cómo ve un toast (posicionado, tapado, colgado, un render de más)
- **THEN** el agente corrige el código a partir de ese reporte
- **AND** puede contrastarlo con su propia captura antes de cerrar el cambio
