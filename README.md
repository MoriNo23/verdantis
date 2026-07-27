# NotifyApp

Notificaciones personalizadas con **layout libre**: icono + imagen grande + texto + barra animada de tiempo.

## Layout

```
┌─────────────────────────────────────────┐
│ [ICONO]  TÍTULO                        │
│         Cuerpo línea 1                  │
│         Cuerpo línea 2                  │
│                                         │
│ ┌───────────────────────────────────┐   │
│ │        IMAGEN GRANDE              │   │
│ └───────────────────────────────────┘   │
│                                         │
│ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░ │  ← barra animada
└─────────────────────────────────────────┘
```

## Requisitos

- Python 3.11+
- PyQt6 (en entorno virtual)

## Instalación rápida

```bash
./install.sh
source .venv/bin/activate
```

## Uso

```bash
python src/notify_app.py \
  --title "Nuevo correo" \
  --body "De: ana@empresa.com" \
  --icon /ruta/icono.png \
  --image /ruta/foto.jpg \
  --duration 8000
```

## Parámetros

| Flag | Default | Descripción |
|---|---|---|
| `--title` | `Notificación` | Título de la notificación |
| `--body` | `""` | Cuerpo de texto |
| `--icon` | `None` | Ruta del icono (32×32) |
| `--image` | `None` | Ruta de la imagen grande |
| `--duration` | `8000` | Duración en ms |
| `--margin` | `16` | Margen desde el borde de la pantalla |
| `--corner` | `top-right` | Esquina: `top-right`, `top-left`, `bottom-right`, `bottom-left` |

## Soporte Wayland

En sesiones Wayland, NotifyApp puede usar el protocolo `wlr_layer_shell_unstable_v1` para posicionar notificaciones con anclaje preciso a esquinas de la pantalla.

```python
from src.wayland_integration import WaylandLayerShell, is_wayland_session, get_anchor_for_corner

if is_wayland_session():
    wl = WaylandLayerShell()
    if wl.connect() and wl.is_available():
        # Crear una superficie de capa en la esquina superior derecha
        anchor = get_anchor_for_corner("top-right")
        layer_surface = wl.create_layer_surface(
            surface=wl_surface,
            layer=Layer.OVERLAY,
            anchor=anchor,
            width=320,
            height=200,
            margin=16,
            namespace="notify-app"
        )
        wl.disconnect()
```

## Requisitos del sistema (para notificaciones nativas)

Si quieres integrar con el sistema de notificaciones de KDE/Debian (opcional):

```bash
# Debían/Ubuntu
sudo apt install python3-gi libnotify4 libnotify-dev gir1.2-notify-0.7

# Arch/Manjaro
sudo pacman -S python-gobject libnotify
```

> PyQt6 se instala en el venv (no en el sistema). No necesitas `--break-system-packages`.
