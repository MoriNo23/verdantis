# Proposal — Tests para los módulos sin cubrir (`verdantis.py` y `dashboard.py`)

## Why

crapper (CRAP = `CC² × (1 − cobertura)³ + CC`) muestra tres módulos al 0% de
cobertura: `dashboard.py` (295 líneas), `qt_fallback.py` (148) y `verdantis.py`
(75). De los tres, el que más duele es `verdantis.py`: es el entry point y
contiene LA decisión de arquitectura del one-shot (backend Wayland vs fallback
PyQt6, con el import perezoso que AGENTS.md documenta como pitfall: "importar
PyQt6 al arrancar rompe"). `dashboard.py` duele menos (es un panel de apoyo)
 pero tiene lógica real: replay de notificaciones con reinyección de avatar,
 y estadísticas.

El 0% significa que cualquier cambio que rompa esa decisión o esas rutas se
entera en producción, no en la suite.

## What Changes

- **BREAKING**: ninguno. Cero cambios en `src/`: esto es una red de tests
  sobre comportamiento EXISTENTE (caracterización).
- `tests/test_entrada.py`: la delegación `--daemon` (argv reescrito), la
  decisión de backend (Wayland con `WAYLAND_DISPLAY`, forzado por flag, y la
  caída al fallback si Wayland falla), y la garantía del import perezoso
  (ni el entry ni el path daemon cargan PyQt6).
- `tests/test_dashboard.py`: las cuatro rutas de Flask con el test client
  (index, history con disco y fallback a memoria, replay con y sin daemon, con
  id inexistente y con avatar reinyectado, stats), y `_deserialise_hints`.
- `qt_fallback.py` queda AFUERA, documentado: su único camino es "no hay
  Wayland", y probarlo headless necesita un display de Qt. Testearlo con el
  import de PyQt6 y sin evento loop sería coverage de mentira — el mismo
  error que me dio crapper en su primera corrida (unittest en vez de pytest,
  0 tests, CRAP inventado).

## Capabilities

### Modified Capabilities

Ninguna: no cambia comportamiento. `skip_specs: true`.

## Impact

- Solo `tests/`: dos archivos nuevos.
- Cobertura esperada: `verdantis.py` 0% → ~85%, `dashboard.py` 0% → ~90%.
- Sin tocar `src/`, sin bump de versión.
