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
| `--icon` | `None` | Ruta del icono (40×40) |
| `--image` | `None` | Ruta de la imagen grande |
| `--duration` | `8000` | Duración en ms |

## Requisitos del sistema (para notificaciones nativas)

Si quieres integrar con el sistema de notificaciones de KDE/Debian (opcional):

```bash
# Debían/Ubuntu
sudo apt install python3-gi libnotify4 libnotify-dev gir1.2-notify-0.7

# Arch/Manjaro
sudo pacman -S python-gobject libnotify
```

> PyQt6 se instala en el venv (no en el sistema). No necesitas `--break-system-packages`.
