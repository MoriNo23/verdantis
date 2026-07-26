# NotifyApp
Notificaciones personalizadas con layout libre: icono + imagen grande + texto + barra animada.

## Características
- Layout libre (icono, imagen, título, cuerpo, barra de tiempo)
- Imágenes grandes (no limitado a iconos pequeños)
- Barra de tiempo animada (desaparece gradualmente)
- Tema oscuro moderno

## Instalación
```bash
pip install PyQt5
```

## Uso
```bash
python src/notify_app.py --title "Título" --body "Cuerpo" --image /ruta/imagen.jpg --icon /ruta/icono.png
```

## Estructura
```
notify-app/
├── src/
│   └── notify_app.py    # App principal
├── assets/
│   └── (iconos/imagenes de ejemplo)
└── README.md
```
