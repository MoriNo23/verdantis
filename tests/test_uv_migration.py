"""
Test unitario: viabilidad de reemplazar `python3 -m venv` por `uv`.

DECISIÓN A VALIDAR: ¿uv puede reemplazar el venv clásico del daemon Verdantis?

EVIDENCIA EMPÍRICA RECOLECTADA POR ESTE TEST (host actual):
- uv 0.5.9 está instalado y crea venvs aislados OK (usa python 3.12 del sistema).
- PyQt6 (única dep pip pura) se instala/importa desde uv sin problema.
- BLOCKER 1 (versión): el proyecto corre en Python 3.13.5, pero uv solo
  ve Python 3.12 del sistema. `uv venv --python 3.13` falla porque 3.13
  no está en el registry de uv (solo existe dentro del venv del proyecto).
  -> uv no puede recrear el entorno en 3.13 sin instalar python3.13 en sistema.
- BLOCKER 2 (gi): PyGObject/GTK3 no compila desde pip/uv (falta cairo.h).
  `gi` está empaquetado en el venv de 3.13 del proyecto, no disponible
  para uv (que usa 3.12).

CONCLUSIÓN: uv NO es drop-in replacement hoy. Requiere:
  (a) python3.13 en el sistema (no solo en venv), o
  (b) migrar el daemon a python 3.12 (el que uv ve), o
  (c) mantener gi vía apt + --system-site-packages con python correcto.

Este test documenta ambos blockers de forma determinística.
"""
import shutil
import subprocess
import tempfile

import pytest


def _run(cmd):
    r = subprocess.run(cmd, shell=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return r.returncode, r.stdout, r.stderr


def test_uv_available():
    assert shutil.which("uv") is not None
    rc, out, _ = _run("uv --version")
    assert rc == 0 and "uv" in out.lower()


def test_uv_venv_creates_isolated_env(tmp_path):
    """uv venv (python 3.12 del sistema) crea entorno aislado."""
    venv_dir = tmp_path / "uvvenv"
    rc, out, err = _run(f"uv venv {venv_dir}")
    assert rc == 0, f"uv venv falló: {err}"
    py = venv_dir / "bin" / "python"
    assert py.exists()
    rc, out, _ = _run(f"{py} -c \"import sys; print(sys.prefix)\"")
    assert str(venv_dir) in out


def test_uv_pip_install_pyqt6(tmp_path):
    """PyQt6 se instala e importa desde venv uv (py3.12 sistema)."""
    venv_dir = tmp_path / "uvvenv"
    _run(f"uv venv {venv_dir}")
    rc, _, err = _run(f"uv pip install PyQt6 --python {venv_dir}/bin/python")
    assert rc == 0, f"uv pip install PyQt6 falló: {err}"
    py = venv_dir / "bin" / "python"
    rc, out, err = _run(f"{py} -c \"import PyQt6; print('OK')\"")
    assert rc == 0 and "OK" in out, f"PyQt6 no importó: {err}"


@pytest.mark.xfail(
    reason="BLOCKER: uv solo ve Python 3.12 del sistema; el proyecto usa 3.13 "
           "que vive dentro del venv actual. uv no recrea el entorno sin "
           "python3.13 en el sistema.",
    strict=False,
)
def test_uv_sees_python_313():
    """
    BLOCKER DOCUMENTADO: uv debe poder usar Python 3.13 (versión del proyecto).
    En este host uv solo ve 3.12 del sistema. Si esto falla, uv no puede
    recrear el entorno del daemon sin instalar python3.13 en el sistema.
    """
    rc, out, _ = _run("uv python list 2>/dev/null | grep -E '^3\\.13'")
    assert rc == 0 and "3.13" in out, (
        "uv no ve Python 3.13 en el sistema. El proyecto corre en 3.13. "
        "uv no puede recrear el entorno sin python3.13 instalado en sistema."
    )


@pytest.mark.xfail(
    reason="BLOCKER: gi/PyGObject no disponible para uv (usa py3.12; "
           "pygobject no compila sin cairo.h del sistema).",
    strict=False,
)
def test_uv_venv_imports_gi(tmp_path):
    venv_dir = tmp_path / "uvvenv"
    _run(f"uv venv {venv_dir}")
    _run(f"uv pip install PyQt6 pygobject --python {venv_dir}/bin/python")
    py = venv_dir / "bin" / "python"
    rc, out, err = _run(
        f"{py} -c \"import gi; gi.require_version('Gtk','3.0'); "
        f"from gi.repository import Gtk; print('GI_OK')\""
    )
    assert rc == 0 and "GI_OK" in out, f"gi no resolvió en uv venv: {err}"


def test_uv_pip_install_idempotent(tmp_path):
    """uv pip install es idempotente (a diferencia del bug de venv clásico)."""
    venv_dir = tmp_path / "uvvenv"
    _run(f"uv venv {venv_dir}")
    py = f"{venv_dir}/bin/python"
    rc1, _, e1 = _run(f"uv pip install PyQt6 --python {py}")
    rc2, _, e2 = _run(f"uv pip install PyQt6 --python {py}")
    assert rc1 == 0 and rc2 == 0, f"no idempotente: {e1} | {e2}"
