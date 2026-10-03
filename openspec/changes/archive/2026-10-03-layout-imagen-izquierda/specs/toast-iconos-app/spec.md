# Spec Delta

## MODIFIED Requirements

### Requirement: Los iconos no cuadrados no se cortan

El logo de 16 px SHALL renderizarse preservando el aspect ratio: el icono completo se escala dentro del slot 16×16 con bandas transparentes (letterbox), sin center-crop del cuadrado central. La imagen izquierda de 80 px conserva su cover-crop circular por diseño y queda fuera de este requisito.

#### Scenario: Icono panorámico
- **WHEN** el icono fuente es no cuadrado (p. ej. 32×16)
- **THEN** se dibuja completo dentro del slot 16×16, con bandas transparentes, sin perder los extremos laterales

#### Scenario: Icono cuadrado
- **WHEN** el icono fuente ya es cuadrado
- **THEN** ocupa el slot 16×16 completo, igual que antes del cambio
