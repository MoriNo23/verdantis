#!/usr/bin/env bash
set -euo pipefail
echo "Instalando dependencias..."
pip install PyQt5 2>&1 | tail -3
echo "Done."
