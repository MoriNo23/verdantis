"""Self-check de `scripts/gsk_shot.py` (captura offscreen del render).

El reftest visual depende de que el script dibuje el widget real sin KWin. Sin
display GTK no se puede, así que el test se saltea en CI; en la sesión verifica
que el PNG se produce y no está vacío.
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "gsk_shot.py"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not os.environ.get("WAYLAND_DISPLAY"),
                    reason="gsk_shot necesita un display GTK")
def test_renderiza_el_toast_a_png(tmp_path):
    salida = tmp_path / "toast.png"
    env = dict(os.environ, GDK_BACKEND="wayland")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--toast", "-o", str(salida)],
        env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    datos = salida.read_bytes()
    assert datos.startswith(PNG_MAGIC)
    assert len(datos) > 5000, "PNG sospechosamente chico (render vacío)"
