# Design

## Context

Ver `proposal.md` (Why). Decisiones cerradas con el usuario: estética **fiel al toast real**, rama `diseno-demos` **borrada**, carpeta **`mockups/`** en main. `wireframe-ui` verificado: es un registry de shadcn/ui (React + Tailwind, MIT) — los componentes se COPIAN al proyecto con `pnpm dlx shadcn@latest add <url-del-registry>`, no es una dependencia runtime. Toolchain de la máquina verificado: Node v26.7 + pnpm 11.10 + bun.

## Goals / Non-Goals

**Goals:**

- Mockup del toast que se vea como el real (tokens exactos del render) y sea editable como texto plano.
- Un solo lugar para las medidas del mockup (tokens compartidos), con las páginas consumiéndolos.
- Matar toda la maquinaria Lunacy: rama, validador, manifiestos, patrón worktree.

**Non-Goals:**

- NO validación automática mockup↔código: sin derivar constantes de `src/`, sin comparaciones — los specs de main son la verdad, el mockup es una vista (trade-off explícito del usuario).
- NO interactividad real del toast (no simula hover con estado salvo que sea trivial en CSS): los estados (hover, wipe parcial, expandido) se muestran como VARIANTES estáticas lado a lado.
- NO tocar `src/`, `tests/` ni el daemon.

## Decisions

### D1 — Next.js mínimo con App Router, componentes vía registry

`mockups/` = `pnpm create next-app` (TypeScript + Tailwind + App Router, sin eslint-config extra), luego `pnpm dlx shadcn@latest init` y `add` de los componentes wireframe-ui que sirvan (button, card, input, avatar, separator — solo los que el toast use). *Alternativa rechazada*: Vite/React — wireframe-ui documenta flujo Next.js/shadcn y el usuario mirará con `pnpm dev` igual.

### D2 — Tokens del toast en un único archivo

`mockups/lib/toast-tokens.ts` (o CSS vars en `globals.css`): colores (`#1e1e2e` card, `#e6e9f2`/`#cdd6f4`/`#a6adc8` textos, `#80cbc4` accent, `#f38ba8` X, `#313244` placeholder), medidas (360 card, 14 pad, 80 imagen, 12 gap, 240 columna, 44 franja, 28 barra, 8 radios, 16 logo fila) y Manrope (vía `next/font/google` o copiada de `src/fonts/` — se copia la bundled para no depender de red). Una sola fuente para todas las páginas; comentarios con el nombre de la constante original de `src/wayland_popup.py` de cada valor para trazabilidad manual.

### D3 — Componente `ToastMock` + variantes estáticas

Un componente `ToastMock` con props (`variant`: estándar/navegador/largo/persistente/con-botones/placeholder; `estado`: normal/hover/wipe-parcial/expandido) que compone imagen izquierda (círculo 80), fila de app (slot 16 + nombre), título, body (wrap a 240 con `max-w`), barra "Ver más", fila de botones y franja. La página de variantes los muestra en la grilla del tablero viejo (3 columnas); la página de anatomía agrega cotas con bordes punteados y labels px; la página de tokens, la paleta como swatches. Los ESTADOS son variantes estáticas, no JS interactivo.

### D4 — Rama `diseno-demos` fuera

`git branch -D diseno-demos` — todo su contenido está commiteado en ella (verificado en el merge de botones-accion: `.free`, validador, manifiestos, openspec completo con 5 changes archivados y 2 specs), así que queda recuperable por SHA en el historial. Los specs `tablero-diseno`/`diseno-toast` (medidas 1:1 del tablero) mueren con la rama: quedan obsoletos — su rol lo cubren los specs de main + el mockup visual.

### D5 — AGENTS.md y .gitignore

La nota "Tablero de diseño (Lunacy): vive en la rama diseno-demos... recrear worktree..." se reemplaza por: `mockups/` — documentación visual del toast (wireframe-ui/Next.js); correr con `pnpm dev` dentro de la carpeta; editar el JSX directamente; sin validador (la verdad son los specs de main). `.gitignore` suma `node_modules/` y `.next/` (sección QA/artifacts).

## Risks / Trade-offs

- [El mockup diverge del toast real con el tiempo] → Aceptado por diseño: es documentación, el spec+codigo manda; el README de mockups/ lleva la advertencia y la lista de specs vivos.
- [node_modules pesa en disco] → Ignorado por git; solo se instala quien corre los mockups.
- [wireframe-ui es lo-fi y el usuario pidió fidelidad] → Los componentes son la base (estructura, radios), los tokens reales van por Tailwind/inline styles; si un componente wireframe no sirve para representar algo fiel (p. ej. la X), se dibuja directo.
- [Borrar la rama pierde los mocks 1:1] → Recuperable por SHA; y el propio usuario decidió borrarla.

## Migration Plan

1. Scaffold de `mockups/` (next-app + shadcn init + componentes wireframe-ui).
2. Tokens + `ToastMock` fiel + páginas (variantes, anatomía, tokens).
3. `pnpm dev` verificado en vivo con el usuario (mira y edita).
4. Borrar rama `diseno-demos`, actualizar AGENTS.md y .gitignore.
5. Commit `chore:` en español (no bumpea versión).

## Open Questions

- Ninguna que bloquee: las tres decisiones estructurales están cerradas por el usuario. Detalles cosméticos del mockup (espaciados de la página, modo oscuro del fondo de la página) se cierran viéndolo con `pnpm dev`.
