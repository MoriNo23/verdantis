#!/bin/sh
# Sirve el tester de notificaciones reales de Verdantis en el puerto 8766 y abre
# el navegador automaticamente (Brave nightly preferencia, fallback xdg-open).
# No bloquea el terminal: lanza server + navegador en background y sale.
cd "$(dirname "$0")/notify-tester" || exit 1

URL="http://localhost:8766/notify-tester.html"

# Si ya hay un server sirviendo en 8766, no arrancar otro (evita EADDRINUSE).
if curl -s -o /dev/null "$URL"; then
  echo "Server ya corriendo en 8766 (reusando)."
else
  echo "Arrancando server node en 8766 (background)..."
  nohup node server.js >/tmp/verdantis-tester.log 2>&1 &
  # Espera a que escuche antes de abrir el navegador.
  ok=0
  for i in $(seq 1 20); do
    curl -s -o /dev/null "$URL" && { ok=1; break; }
    sleep 0.3
  done
  [ "$ok" = "1" ] || { echo "ERROR: el server no prendio. Log en /tmp/verdantis-tester.log"; exit 1; }
fi

# Abre el navegador (Brave nightly preferencia; fallback xdg-open).
if command -v brave-browser-nightly >/dev/null 2>&1; then
  brave-browser-nightly --new-window "$URL" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
fi

echo
echo "  ✅ Tester listo."
echo "  URL : $URL"
echo "  Si no se abrio solo, pega la URL en Brave."
echo "  Detener el server : pkill -f 'node server.js'"