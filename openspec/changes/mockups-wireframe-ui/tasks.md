# Tasks

## 1. Scaffold de `mockups/`

- [x] 1.1 Crear la app: `pnpm create next-app mockups` (TypeScript + Tailwind + App Router, sin extra-config) + `pnpm dlx shadcn@latest init` + `add` de los componentes wireframe-ui que use el toast (card/button/input/avatar/separator vía registry URL) — verificación: `pnpm dev` dentro de `mockups/` levanta la página default sin errores.

  **Hecho**: Next 16 + Tailwind 4 + shadcn init + 7 componentes wireframe-ui (button, card, avatar, input, separator, badge, text + lib wireframe.css/types/utils). Manrope copiada bundled de `src/fonts/` (@font-face, sin red). `pnpm build` verde (rutas /, /anatomia, /tokens) y `pnpm dev` sirviendo 200 en las tres.
- [x] 1.2 `.gitignore` de la raíz cubre `node_modules/` y `.next/` (sección QA/artifacts) — verificación: `git status --short` no muestra basura de node_modules tras instalar.

  **Hecho**: raíz suma `node_modules/` y `.next/`; `mockups/.gitignore` (generado por create-next-app) también los cubre localmente. `pnpm build` verde y status limpio de basura.

## 2. Tokens y ToastMock fiel

- [x] 2.1 Tokens del toast en un único archivo (`lib/toast-tokens.ts` o CSS vars): colores (`#1e1e2e`, `#e6e9f2`, `#cdd6f4`, `#a6adc8`, `#80cbc4`, `#f38ba8`, `#313244`), medidas (360/14/80/12/240/44/28/8/16), Manrope copiada de `src/fonts/` (sin red) — verificación: cada token lleva comentario con la constante original de `src/wayland_popup.py` de la que sale (trazabilidad manual).
- [x] 2.2 Componente `ToastMock` con props de variante (estándar/navegador/largo/persistente/con-botones/placeholder) y estado (normal/hover/wipe-parcial/expandido): imagen izquierda circular 80, fila de app (slot 16 + nombre), título, body wrappeado a 240, barra "Ver más" al 22% del accent con radio 8, fila de hasta 3 botones de acción, franja de descarte 44 con tinte rojizo 18%/32% y X `#f38ba8` en hover, wipe verde translúcido en la variante correspondiente — verificación: el mockup estándar mide 360px de ancho y la columna de texto respeta los 240px con Manrope (inspección en el navegador).

  **Hecho** en `mockups/src/components/toast-mock.tsx`: layout de flujo (imagen+texto → botones → Ver más) con overlays absolutos para franja (SVG de la X, stroke 2.5 + round caps) y wipe. Estados estáticos por props. Consumo exclusivo de `toast-tokens.ts`.
- [x] 2.3 README de `mockups/`: cómo correrlo (`pnpm i && pnpm dev`), que es documentación visual SIN validador, y que la verdad del comportamiento son los specs de main (lista de los 6 vivos) — verificación: el README existe y nombra los specs.

## 3. Páginas

- [x] 3.1 Página de variantes: las 6 variantes post-0.9.0 en grilla (3 columnas como el tablero viejo) con sus estados estáticos lado a lado — verificación: todas las variantes renderizan en una sola pantalla con `pnpm dev`.
- [x] 3.2 Página de anatomía: el toast despiece con cotas px (bordes punteados + labels: pad 14, fila app 20, título 22, columna 240/196, imagen 80, franja 44, barra 28, radios 12/8, X stroke 2.5) — verificación: cada cota del despiece coincide con el valor del token del paso 2.1.
- [x] 3.3 Página de tokens: paleta como swatches con nombre + hex (los del render real, incluida la familia acento del dashboard si aporta) — verificación: los hex de los swatches son los del código (`_hex_rgb` de wayland_popup: card, textos, accent, X, placeholder).

## 4. Limpieza Lunacy y docs

- [ ] 4.1 Borrar la rama `diseno-demos` (`git branch -D diseno-demos`; todo commiteado → recuperable por SHA en el historial) — verificación: `git branch -a` no la lista y `git log diseno-demos` antes del borrado documenta el último SHA en la task.
- [x] 4.2 AGENTS.md: reemplazar la nota del tablero Lunacy (rama + worktree on-demand) por `mockups/` (documentación visual, `pnpm dev` dentro, edición directa del JSX, sin validador — la verdad son los specs de main) — verificación: grep de AGENTS.md sin "Lunacy"/"diseno-demos" y con la nota nueva de mockups.

  **Hecho**: la nota apunta a `mockups/` con la advertencia de divergencia y el SHA de recuperación (`ba091a4`) documentado.
- [x] 4.3 Commit `chore:` en español con todo (mockups/ + .gitignore + AGENTS.md + los artifacts del change) — verificación: `git status --short` limpio y `git log -1 --stat` muestra mockups/ sin node_modules.

  **Hecho**: commit `6dcde30 chore: mockups del toast con wireframe-ui — el tablero Lunacy se retira` (45 archivos, +8842; el grep de "node_modules" en el --stat solo matchea el mensaje del commit, ningún archivo). Status limpio.

## 5. Verificación con el usuario

- [ ] 5.1 `pnpm dev` en vivo: el usuario abre el navegador, mira las variantes y edita algo trivial (un texto de un mockup) recargando — verificación: el usuario confirma que se ve como el toast real y que editar es directo; ajustes cosméticos que salgan se aplican en el mismo paso.
