#!/usr/bin/env bash
# Verificación visual + de funcionamiento de Verdantis (enfoque reftest GTK).
#
# No usa herramientas Qt: captura la pantalla real con spectacle (KWin), recorta
# la esquina donde ancla el toast y compara contra una imagen dorada (golden).
# Si no existe la golden, la crea en el primer run.
#
# Uso:
#   bash scripts/visual_check.sh           # captura + compara
#   bash scripts/visual_check.sh --update  # regenera la golden
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="/tmp/opencode/verdantis-visual"
GOLDEN="$REPO/tests/golden/toast-vibrancia.png"
UPDATE=0
[ "${1:-}" = "--update" ] && UPDATE=1

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
sleep 2

# -- 2. Captura real (KWin screenshot, con reintentos) --------------------
# Un puntero encima del card activa hover (franja rosa + columna angosta) y el
# reftest compara contra un card sin hover: guardar la posición, apartar el
# cursor y devolverlo al terminar.
SHOT="$OUT/captura.png"
POS=""
if command -v kdotool >/dev/null && command -v ydotool >/dev/null; then
  POS=$(kdotool getmouselocation 2>/dev/null | sed -n 's/^x:\([0-9]*\) y:\([0-9]*\).*/\1 \2/p')
  if [ -n "$POS" ]; then
    ydotool mousemove -- -4000 -4000 >/dev/null 2>&1 || true
    sleep 0.4
  fi
fi
ok=0
for i in 1 2 3 4 5; do
  QT_QPA_PLATFORM=wayland spectacle -i -b -n -o "$SHOT" >/dev/null 2>&1 && ok=1 && break
  sleep 1
done
if [ "$ok" = 0 ]; then
  echo "ERROR: KWin no devolvió captura tras 5 intentos" >&2
  exit 1
fi

if [ -n "$POS" ]; then
  read -r PX PY <<< "$POS"
  ydotool mousemove -- "$PX" "$PY" >/dev/null 2>&1 || true
  sleep 0.2
fi

# -- 3. Recortar la esquina del toast (top-right) ---------------------------
CROP="$OUT/toast.png"
# Solo la card: 360px de ancho, debajo del panel superior (y≈40) y con el
# margen de 16px del layer-shell. Incluir el panel arruinaba el reftest porque
# el reloj y los iconos cambian entre capturas.
convert "$SHOT" -crop 360x165+990+10 +repage "$CROP"

# -- 4. Reftest contra golden -----------------------------------------------
if [ ! -f "$GOLDEN" ] || [ "$UPDATE" = 1 ]; then
  cp "$CROP" "$GOLDEN"
  echo "==> Golden creada: $GOLDEN"
else
  # Compare devuelve 0 si idénticas; el metrics da la diferencia normalizada.
  if compare -metric AE "$CROP" "$GOLDEN" null: 2>"$OUT/diff.txt"; then
    echo "==> Reftest: IDENTICA a la golden"
  else
    echo "==> Reftest: DIFIERE (píxeles distintos: $(cat "$OUT/diff.txt"))"
    echo "    Revisar $CROP contra $GOLDEN"
    exit 1
  fi
fi

# -- 5. Sanity: el toast no está vacío -------------------------------------
# Si el render fallara, la esquina sería solo el wallpaper (pocos colores).
COLORS=$(identify -format %k "$CROP")
echo "==> Colores distintos en la región: $COLORS"
if [ "$COLORS" -lt 20 ]; then
  echo "ERROR: la región parece vacía (¿render fallido?)" >&2
  exit 1
fi

# -- 6. Cerrar el toast de prueba por D-Bus --------------------------------
gdbus call --session \
  --dest org.freedesktop.Notifications \
  --object-path /org/freedesktop/Notifications \
  --method org.freedesktop.Notifications.CloseNotification "$ID" >/dev/null 2>&1 || true
echo "==> OK: funcionamiento + visual verificados"
