#!/usr/bin/env bash
# Verificación visual + de funcionamiento de Verdantis.
#
# El render se compara SIEMPRE contra una golden offscreen: el mismo
# `NotificationWidget` se dibuja con `do_snapshot` y se rasteriza a PNG
# (`scripts/gsk_shot.py`), sin KWin, sin wallpaper, sin panel y sin depender de
# que la sesión esté destrabada. La card translúcida se compone sobre un fondo
# fijo, así que esa golden es la única comparable: la captura del desktop cambia
# con el wallpaper, el panel y el estado de auto-ocultado.
#
# Con `--live` además se comprueba que el toast realmente aparezca en pantalla
# (captura KWin + sanity de colores en la esquina). Esa captura no se compara
# píxel a píxel: el panel mueve la card.
#
# Uso:
#   bash scripts/visual_check.sh           # Notify real + reftest offscreen
#   bash scripts/visual_check.sh --live    # además, smoke en pantalla
#   bash scripts/visual_check.sh --update  # regenera la golden offscreen
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="/tmp/opencode/verdantis-visual"
GOLDEN="$REPO/tests/golden/toast-offscreen.png"
UPDATE=0
LIVE=0
for arg in "$@"; do
  case "$arg" in
    --update) UPDATE=1 ;;
    --live) LIVE=1 ;;
    *) echo "uso: $0 [--live] [--update]" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT" "$(dirname "$GOLDEN")"

# -- 1. Funcionamiento: Notify con código de verificación ------------------
notify() {
  gdbus call --session \
    --dest org.freedesktop.Notifications \
    --object-path /org/freedesktop/Notifications \
    --method org.freedesktop.Notifications.Notify \
    'verdantis-visual' 0 'mail' "$1" "$2" '[]' '{}' 0 2>/dev/null
}

echo "==> Enviando notificación de prueba (persistente)..."
R=$(notify 'Código de verificación' 'Tu código de verificación es 482193. No lo compartas.')
# OJO: no usar grep -o '[0-9]*' sobre "(uint32 1,)": devuelve 32 (de "uint32").
ID=$(echo "$R" | sed 's/.*uint32 \([0-9]*\).*/\1/')
echo "    Notify -> $R (id=$ID)"
sleep 1

# -- 2. Reftest del render (offscreen, determinista) -----------------------
OFF="$OUT/toast-offscreen.png"
"$REPO/.venv/bin/python" "$REPO/scripts/gsk_shot.py" --toast -o "$OFF"
if [ ! -f "$GOLDEN" ] || [ "$UPDATE" = 1 ]; then
  cp "$OFF" "$GOLDEN"
  echo "==> Golden creada: $GOLDEN"
elif compare -metric AE "$OFF" "$GOLDEN" null: 2>"$OUT/diff.txt"; then
  echo "==> Reftest: IDENTICA a la golden"
else
  echo "==> Reftest: DIFIERE (píxeles distintos: $(cat "$OUT/diff.txt"))"
  echo "    Revisar $OFF contra $GOLDEN"
  exit 1
fi
COLORES=$(identify -format %k "$OFF")
echo "==> Colores distintos en el render: $COLORES"
if [ "$COLORES" -lt 20 ]; then
  echo "ERROR: el render parece vacío" >&2
  exit 1
fi

# -- 3. Smoke en vivo (opcional): el toast aparece en pantalla ------------
if [ "$LIVE" = 1 ]; then
  POS=""
  if command -v kdotool >/dev/null && command -v ydotool >/dev/null; then
    POS=$(kdotool getmouselocation 2>/dev/null | sed -n 's/^x:\([0-9]*\) y:\([0-9]*\).*/\1 \2/p')
    if [ -n "$POS" ]; then
      ydotool mousemove -- -4000 -4000 >/dev/null 2>&1 || true
      sleep 0.4
    fi
  fi
  SHOT="$OUT/captura.png"
  ok=0
  for i in 1 2 3 4 5; do
    QT_QPA_PLATFORM=wayland spectacle -i -b -n -o "$SHOT" >/dev/null 2>&1 && ok=1 && break
    sleep 1
  done
  if [ -n "$POS" ]; then
    read -r PX PY <<< "$POS"
    ydotool mousemove -- "$PX" "$PY" >/dev/null 2>&1 || true
    sleep 0.2
  fi
  if [ "$ok" = 0 ]; then
    echo "AVISO: KWin no entregó captura (¿sesión bloqueada?); smoke omitido." >&2
  else
    # Región amplia de la esquina: el panel puede empujar la card unos px.
    convert "$SHOT" -crop 400x260+940+0 +repage "$OUT/toast-live.png"
    COLORES=$(identify -format %k "$OUT/toast-live.png")
    echo "==> Colores distintos en pantalla: $COLORES"
    if [ "$COLORES" -lt 20 ]; then
      echo "ERROR: no se ve nada en la esquina (¿toast no mapeado?)" >&2
      exit 1
    fi
  fi
fi

# -- 4. Cerrar el toast de prueba por D-Bus --------------------------------
gdbus call --session \
  --dest org.freedesktop.Notifications \
  --object-path /org/freedesktop/Notifications \
  --method org.freedesktop.Notifications.CloseNotification "$ID" >/dev/null 2>&1 || true
echo "==> OK: funcionamiento + visual verificados"
