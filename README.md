# Verdantis

```
                     360 px
┌───────────────────────────────────────────────┐
│ ╭─────╮  [16px]  Brave - Título de la pestaña │
│ │ IMG │  Título del toast                     │
│ │ 80px│  Cuerpo sanitizado, con wrap…        │
│ ╰─────╯  [ Responder ]    [ Archivar ]        │
└───────────────────────────────────────────────┘
   │          │
   │          └─ línea de app + título + body ("Ver más") + acciones
   └─ imagen izquierda: SIEMPRE presente (80 px); cadena imagen de la
      notificación → icono .desktop exacto → placeholder con la inicial

Wipe de tiempo: tinte de alto completo que avanza de izquierda a derecha
(la porción ya recorrida queda teñida). Persistente + hover: franja de
descarte + X en el borde derecho.
```

Daemon de notificaciones de escritorio para **Wayland** (KDE Plasma 6): es el dueño de
`org.freedesktop.Notifications` en el bus de sesión y dibuja los toasts con GTK3 +
gtk-layer-shell (cairo/Pango), sin depender de Plasma. Reemplaza a mako/deadd.

## Instalación

```bash
./install.sh                                      # apt + venv .venv/
systemctl --user enable --now verdantis.service   # el daemon como servicio de usuario
```

## Daemon (uso normal)

Las apps mandan notificaciones por DBus y verdantis las dibuja:

```bash
systemctl --user status verdantis.service
busctl --user call org.freedesktop.Notifications \
  /org/freedesktop/Notifications org.freedesktop.Notifications GetServerInformation
# → ssss "Verdantis" "MoriNo23" "0.10.0" "1.3"
```

### Reglas de la pila

- Máximo **2 toasts simultáneos**; las demás esperan en una fila.
- La fila es **FIFO por llegada**: ningún tipo (low/normal/critical) gana un hueco ni
  salta la fila — la `urgency` solo cambia duración y estilo, nunca la posición.
- **Una toast no se crea hasta que hay hueco visual**: las que esperan son datos,
  sin ventana ni timer.
- El hueco se libera cuando el toast **vence** o el usuario lo **cierra**; en ese
  momento entra la primera de la fila.
- Un toast que entra **nunca tapa** al que ya estaba: su primer frame ya llega a su
  hueco (debajo del de arriba, con el gap de 12 px).
- El texto se rasteriza con antialiasing en grises fijado por código: nítido en
  cualquier equipo, sin heredar el subpixel del fontconfig.

### Dashboard e historial

`http://127.0.0.1:8777` — historial (`~/.local/share/verdantis/history.jsonl`) y
replay de notificaciones pasadas.

## One-shot (sin daemon)

```bash
.venv/bin/python src/verdantis.py --title "Hola" --body "Mundo" --icon icon.png --image foto.jpg --corner top-right
```

| Flag | Default | Descripción |
|---|---|---|
| `--title` | `Notificación` | Título |
| `--body` | `""` | Cuerpo |
| `--icon` | `None` | Imagen izquierda (slot de 80 px) |
| `--app-icon` | `None` | Logo 16 px de la línea de app |
| `--app-name` | `""` | Línea de app (Brave, Telegram…) |
| `--image` | `None` | Imagen grande (banner) |
| `--duration` | `8000` | Duración ms |
| `--margin` | `16` | Margen del borde (px) |
| `--corner` | `top-right` | `top-right`, `top-left`, `bottom-right`, `bottom-left` |
| `--accent` | `#89b4fa` | Color acento hex |
| `--force-wayland` | | Forzar backend GTK+layer-shell |
| `--force-qt` | | Forzar backend PyQt6 |
| `--daemon` | | Iniciar como daemon DBus |

## Backends

- **Wayland**: GTK3 + gtk-layer-shell (anclaje preciso a esquinas)
- **X11/fallback**: PyQt6 (posicionamiento via `move()`)

## Pruebas y herramientas

```bash
.venv/bin/python -m pytest tests/ -q        # suite completa (362, ~17 s)
.venv/bin/python tests/qa_sim_pila.py       # simulador de la pila en texto (reloj virtual)
sh tests/fixtures/serve-tester.sh           # tester real en el navegador (Enviar x5)
```

La verificación visual de los toasts la hace el usuario; el agente no saca capturas
(spec `verificacion-visual`).

- Producto y reglas: `PRD.md`.
- Verdad formal del comportamiento: `openspec/specs/`.
- Convenciones de desarrollo: `AGENTS.md`.
