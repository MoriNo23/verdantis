# Verdantis — mockups del toast

Documentación visual del toast con [wireframe-ui](https://github.com/aguiarsc/wireframe-ui)
(componentos shadcn/ui) sobre Next.js, **fiel al render real** del daemon.

## Correr

```bash
pnpm i
pnpm dev      # http://localhost:3000
```

Páginas: `/` (variantes) · `/anatomia` (cotas px) · `/tokens` (paleta y medidas).

## ⚠️ Advertencia: sin validador

Estos mockups son **documentación** — no hay validación automática contra
`src/wayland_popup.py` (la maquinaria de manifiestos del tablero Lunacy se
retiró con este change). La verdad del comportamiento son los specs de main:

- `toast-acciones` — botones de acción y action-icons
- `toast-imagen-izquierda` — slot siempre presente, columna única 240/196
- `toast-franja-descarte` — franja + X solo con hover en persistentes
- `toast-stack` — la pila nunca solapa (gap 12)
- `toast-orden-llegada` — FIFO
- `toast-body-colapso` — ellipsis tras la línea exacta del cap
- `toast-iconos-app` — resolución del logo 16px y placeholder

Si el daemon cambia y esto no se toca, **puede divergir** — se acepta como
trade-off a cambio de editarlo con el editor y verlo en el navegador.

## Editar

Todo el layout vive en `src/lib/toast-tokens.ts` (colores/medidas/tipografía,
con comentarios que nombran la constante original de `wayland_popup.py`) y
`src/components/toast-mock.tsx` (el componente del toast). Las páginas solo
componen variantes.
