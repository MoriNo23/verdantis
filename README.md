# NotifyApp

```
┌─────────────────────────────────────────┐
│ [ICONO]  TÍTULO                        │
│         Cuerpo                          │
│                                         │
│ [IMAGEN]                                │
│ ████████████░░░░░░░░░░░░  ← barra tiempo│
└─────────────────────────────────────────┘
```

## Instalación

```bash
./install.sh
source .venv/bin/activate
```

## Uso

```bash
python src/notify_app.py --title "Hola" --body "Mundo" --icon icon.png --image foto.jpg --corner top-right
```

| Flag | Default | Descripción |
|---|---|---|
| `--title` | `Notificación` | Título |
| `--body` | `""` | Cuerpo |
| `--icon` | `None` | Ruta icono (32×32) |
| `--image` | `None` | Ruta imagen grande |
| `--duration` | `8000` | Duración ms |
| `--corner` | `top-right` | `top-right`, `top-left`, `bottom-right`, `bottom-left` |
| `--accent` | `#89b4fa` | Color acento hex |
| `--force-wayland` | | Forzar backend GTK+layer-shell |
| `--force-qt` | | Forzar backend PyQt6 |

## Backends

- **Wayland**: GTK3 + gtk-layer-shell (anclaje preciso a esquinas)
- **X11/fallback**: PyQt6 (posicionamiento via `move()`)
