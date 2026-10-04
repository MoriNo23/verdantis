# Proposal — Mockups del toast con wireframe-ui (adiós Lunacy)

## Why

El tablero de diseño actual es maquinaria pesada para lo que necesita: un documento binario `.free` que solo se puede editar desde Lunacy (para mí, pelearme con el MCP; para vos, abrir una app aparte), un validador geométrico de 32 KB con 5 manifiestos JSON, su propio root de openspec y una rama separada con patrón worktree on-demand. `wireframe-ui` (registry MIT de componentes shadcn/ui, 206★) invierte la ecuación: los mockups son **código** — yo los escribo directo, vos los editás con tu editor y los mirás en el navegador con `pnpm dev`. Toolchain ya verificado en la máquina (Node v26 + pnpm 11).

## What Changes

- **`mockups/` en MAIN** (decisión del usuario: nombre `mockups/`, sin worktree ni rama separada): app mínima Next.js + Tailwind con los componentes de wireframe-ui, **estilada fiel al toast real** (decisión del usuario) — tokens reales: card `#1e1e2e` 360px, imagen izquierda 80px circular, columna de texto 240px, franja de descarte 44px con tinte y X `#f38ba8`, barra "Ver más" al 22% del accent `#80cbc4`, fila de botones de acción, wipe verde, fuente Manrope.
- **Contenido**: las variantes del toast post-0.9.0 (estándar, navegador con label compuesto, body largo + "Ver más", persistente con franja hover, con botones de acción, app sin icono con placeholder) + página de anatomía con cotas + página de tokens.
- **Sin validador** (trade-off aceptado): el mockup es documentación visual; la verdad del comportamiento son los specs de main (`toast-acciones`, `toast-imagen-izquierda`, `toast-franja-descarte`, `toast-stack`, `toast-orden-llegada`, `toast-body-colapso`) y el código. Puede divergir y no rompe nada — el README de `mockups/` lo aclara.
- **Rama `diseno-demos` BORRADA** (decisión del usuario): todo su contenido está commiteado ahí (el `.free`, el validador, los manifiestos, su openspec con las specs `tablero-diseno` y `diseno-toast`) y queda recuperable en el historial de git; los mocks 1:1 de Lunacy pasan a ser historia.
- **AGENTS.md**: la nota del tablero Lunacy (rama + recrear worktree on-demand) se reemplaza por `mockups/` (`pnpm dev`, edición directa del JSX).
- **.gitignore**: `node_modules/` y `.next/`.
- `skip_specs: true` — tooling/documentación sin cambio de comportamiento del daemon (la verdad en specs ya vive en main).
- Sin bump de versión (`chore:`).

## Capabilities

### New Capabilities

(ninguna — `skip_specs: true`: los mockups son documentación; el contrato de comportamiento son los specs existentes de main)

### Modified Capabilities

(ninguna)

## Impact

- **Nuevo**: `mockups/` (Next.js + pnpm, componentes wireframe-ui copiados al proyecto, tokens del toast, 2-3 páginas).
- **Borrado**: rama `diseno-demos` completa (git history la conserva).
- **Docs**: AGENTS.md (nota de mockups), .gitignore.
- **Sin tocar**: `src/`, `tests/`, daemon, API DBus — cero riesgo de runtime.
