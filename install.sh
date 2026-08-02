#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Dependencias del sistema..."
sudo apt install -y libgtk-layer-shell-dev python3-gi python3-gi-cairo 2>&1 | tail -2

echo "==> Entorno virtual..."
python3 -m venv "$SCRIPT_DIR/.venv"
source "$SCRIPT_DIR/.venv/bin/activate"

echo "==> Dependencias Python..."
pip install PyQt6 2>&1 | tail -1

echo ""
echo "==> Servicio systemd (user) para daemon DBus..."
mkdir -p "$HOME/.config/systemd/user/"
cp "$SCRIPT_DIR/verdantis.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
echo ""
echo "Done: source .venv/bin/activate"
echo ""
echo "Uso (one-shot): python src/verdantis.py --title 'Hola' --body 'Mundo'"
echo "Uso (daemon):   systemctl --user enable --now verdantis.service"
echo "                (reemplaza mako/deadd como daemon de notificaciones DBus)"