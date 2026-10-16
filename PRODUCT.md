# Product

## Register

product

## Users

Usuario único: MoriNo23 (autor del proyecto). Desarrollador técnico en KDE Plasma 6 sobre Wayland, que quiere notificaciones con look propio sin depender de plasmashell. Las dos caras del uso:

1. **Consumidor diario**: ve los toasts mientras trabaja (Brave, Telegram, red/VPN). Quiere que la pila sea predecible, el texto legible y que nada le tape lo que está haciendo.
2. **Verificador/diagnosticador**: depura el render por CLI (`verdantis list/replay/clear`) y confirma visualmente los cambios (spec `verificacion-visual`: el usuario reporta, el agente no saca capturas).

## Product Purpose

Ser el dueño de `org.freedesktop.Notifications` en la sesión Wayland/KDE6 y dibujar los toasts con GTK3 + gtk-layer-shell, reemplazando a mako/deadd y al daemon de Plasma. Éxito se ve así: la pila FIFO nunca se tapa ni salta, el texto queda nítido en cualquier equipo (AA en grises fijado por código), cada `Notify` queda archivado y es reproducible con `verdantis replay`, y el contrato freedesktop 1.2 se cumple con capabilities honestas.

## Brand Personality

**Con carácter visible** (decisión explícita del usuario): los toasts deben reconocerse a primera vista como "de Verdantis" — acento propio, medidas y ritmo identificables — sin caer en decoración. Voz: directa, técnica, seca; sin humor ni relleno. La identidad vive en el detalle gráfico (acento, franja de tiempo, slot de imagen de 80 px, wipe), no en adornos.

## Anti-references

- **El look de Plasma/KDE por defecto**: no clonar el toast de plasmashell — Verdantis existe justamente para escapar de ese look.
- **Toast genérico tipo Windows/Android**: card plana blanca/grisa, tipografía de sistema sin jerarquía, cero personalidad.
- **Estilo hacker/neón terminal**: verde neón, fuentes monoespaciadas en la UI, glow/borders brillantes en la superficie del toast.

## Design Principles

- **La pila es una cola, no un desfile**: determinismo FIFO visible; nada se tapa, nada salta la fila, el orden es el de llegada.
- **Legibilidad fijada por código**: el render no hereda sorpresas del entorno (antialiasing en grises, contraste AA sobre fondos translúcidos).
- **Carácter en el detalle, no en el ruido**: identidad por acento, medidas propias y micro-interacción; nunca por clutter ni motion decorativa.
- **El usuario ve, el código obedece**: la verdad visual la da el reporte humano (spec `verificacion-visual`); los specs de `openspec/specs/` son la verdad del comportamiento.
- **Honesta**: capabilities y estados reales; sin features fantasma (los hints que se ignoran no se anuncian).

## Accessibility & Inclusion

- Contraste AA: 4.5:1 en texto de cuerpo/títulos/labels de acciones, 3:1 en texto grande, medido contra el fondo translúcido real del toast (no contra negro puro).
- Estados interactivos visibles (hover/active) en la franja de descarte, la X y las acciones; targets de click cómodos (franja de 80 px de ancho, X de ~24 px). Focus queda fuera a propósito: una surface layer-shell solo tiene foco con keyboard interactivity, que le roba el tipeo a la app activa.
- Un solo usuario, sin uso conocido de screen reader; no se añaden bloqueos de teclado artificiales. Accesibilidad = contraste + claridad de estados, no infraestructura ARIA completa.
