#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Creando entorno virtual..."
python3 -m venv "$SCRIPT_DIR/.venv"
source "$SCRIPT_DIR/.venv/bin/activate"

echo "==> Instalando PyQt6..."
pip install PyQt6 2>&1 | tail -3

echo ""
echo "Done. Para activar el entorno:"
echo "  source .venv/bin/activate"
echo ""
echo "Para probar:"
echo "  python src/notify_app.py --title 'Hola' --body 'Esto funciona'"
