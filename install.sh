#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Dependencias del sistema..."
sudo apt install -y libgtk4-layer-shell0 gir1.2-gtk4layershell-1.0 2>&1 | tail -1

echo "==> Entorno virtual (PyGObject/pycairo/pytest via pip)..."
python3 -m venv "$SCRIPT_DIR/.venv"
source "$SCRIPT_DIR/.venv/bin/activate"
python -m pip install -r "$SCRIPT_DIR/requirements.txt"

echo "==> Icono del tema (hicolor)..."
for size in 16 32 64 128 256; do
  sudo install -Dm644 "$SCRIPT_DIR/assets/verdantis-icon.png" \
    "/usr/share/icons/hicolor/${size}x${size}/apps/verdantis.png"
done
sudo install -Dm644 "$SCRIPT_DIR/assets/verdantis-icon.png" \
  /usr/share/icons/hicolor/scalable/apps/verdantis.png

echo "==> Servicio systemd (user) para daemon DBus..."
mkdir -p "$HOME/.config/systemd/user/"
# El template lleva @DIR@: el servicio queda atado al path REAL del repo,
# sobrevive moverlo si se reinstala (auditoría #18).
sed "s|@DIR@|$SCRIPT_DIR|g" "$SCRIPT_DIR/service.template" \
  > "$HOME/.config/systemd/user/verdantis.service"
systemctl --user daemon-reload

echo ""
echo "Done: source .venv/bin/activate"
echo ""
echo "Uso (one-shot): python src/verdantis.py --title 'Hola' --body 'Mundo'"
echo "Uso (daemon):   systemctl --user enable --now verdantis.service"
echo "                (reemplaza mako/deadd como daemon de notificaciones DBus)"
