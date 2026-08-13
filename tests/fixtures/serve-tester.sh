#!/bin/sh
# Sirve el tester de notificaciones en el puerto que ya usa el repo (8766).
# Abrir en Brave/Firefox: http://localhost:8766/notify-tester.html
# Dispara notificaciones reales por D-Bus que Verdantis dibuja como toasts.
cd "$(dirname "$0")/fixtures" || exit 1
exec python3 -m http.server 8766
