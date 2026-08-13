#!/bin/sh
# Sirve el tester de notificaciones reales de Verdantis en el puerto 8766.
# Node app: GUI web en http://localhost:8766/notify-tester.html + backend que
# dispara Notify por gdbus con hints completos (desktop-entry/url/actions).
# Reemplaza al viejo HTML estático (que usaba la API Notification del navegador y
# no podía mandar hints de DBus, por eso no reproducía el bug del click en PWA).
cd "$(dirname "$0")/notify-tester" || exit 1
exec node server.js
