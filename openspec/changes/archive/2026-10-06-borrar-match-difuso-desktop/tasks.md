# Tasks

## 1. RED — el metatest que falla hoy

- [x] 1.1 En `tests/test_tests_icon_resolution.py`: metatest que exige que el
  módulo NO exponga un match difuso de `.desktop`. Verificación: **falla ahora**
  (`hasattr(wp, "_find_desktop_file")` es True) y el mensaje nombra la regla de
  `AGENTS.md` y el bug de los PWA de Brave.

## 2. GREEN — el borrado

- [x] 2.1 Borrar `_find_desktop_file` de `src/wayland_popup.py` (38 líneas) y
  `test_find_desktop_file_by_app_name` de `tests/test_icon_resolution.py`.
  Verificación: el metatest de 1.1 pasa.
- [x] 2.2 Actualizar los dos docstrings que la citan (líneas ~128 y ~171) para
  que apunten a la regla y a `_exact_desktop_file`, sin perder el valor
  histórico del bug de los PWA. Verificación: el grep no encuentra ninguna
  referencia a la función borrada.

## 3. Verificación

- [x] 3.1 Suite completa verde con el comando documentado
  (`.venv/bin/python -m pytest tests/ -q`).
- [x] 3.2 Re-correr crapper con el LCOV de pytest y confirmar que el CRAP 121
  desapareció de la tabla. Verificación: el reporte ya no nombra
  `_find_desktop_file` y ningún otro score supera 60.
- [x] 3.3 Bump PATCH de `VERSION` en el mismo commit (`fix:`) y verificación en
  vivo con `busctl --user call … GetServerInformation`.