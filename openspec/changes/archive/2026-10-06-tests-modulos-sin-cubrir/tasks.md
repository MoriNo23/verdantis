# Tasks

## 1. `verdantis.py` (el entry point)

- [x] 1.1 `tests/test_entrada.py`: `--daemon` delega a `verdantis_daemon.main`
  con el argv reescrito a solo el corner, y no carga PyQt6.
- [x] 1.2 La decisión de backend: con `WAYLAND_DISPLAY` toma el camino
  Wayland; `--force-qt` lo salta incluso con Wayland disponible.
- [x] 1.3 La caída al fallback: si `WaylandPopup` falla, se baja al branch Qt
  (el mensaje a stderr y el import perezoso).
- [x] 1.4 La garantía del import perezoso: importar el entry y correr el path
  daemon/wayland deja `"PyQt6" not in sys.modules`; el path Qt sí lo carga.

## 2. `dashboard.py`

- [x] 2.1 `tests/test_dashboard.py`: index sirve HTML con el nombre de la
  app; `/api/history` devuelve newest-first desde disco.
- [x] 2.2 El fallback a memoria: sin archivo de historial, la lista sale del
  manager (daemon recién arrancado).
- [x] 2.3 Replay: sin daemon → 500; con daemon, id inexistente → 404.
- [x] 2.4 Replay "tal cual": el manager recibe los campos del registro con
  `sender="dashboard-replay"` y `replaces_id=0`, y el avatar persistido se
  reinyecta como `image-path` cuando el archivo existe.
- [x] 2.5 Stats: total, activos, en cola y el conteo por app (con el app_name
  vacío agrupado como "(unknown)").
- [x] 2.6 `_deserialise_hints`: urgency a int, "True"/"False" a bool, los
  escalares pasan y lo demás se descarta.

## 3. Verificación

- [x] 3.1 Suite completa verde (`.venv/bin/python -m pytest tests/ -q`).
- [x] 3.2 Cobertura: `verdantis.py` y `dashboard.py` salen del 0% (coverage
  report). *(Hecho: `verdantis.py` 0% → 98%, `dashboard.py` 0% → 92%; el total
  del repo subió de 73% a 83%. `qt_fallback.py` quedó al 12% por el import
  incidental de los tests de entrada — documentado en el design y en el
  docstring del test: testearlo headless sería coverage de mentira.)*
- [x] 3.3 `qt_fallback.py` queda documentado fuera, con la razón en el
  docstring del test de entrada. *(Hecho: la razón vive en el docstring de
  `tests/test_entrada.py` y en la tabla de Decisiones del design.md.)*
