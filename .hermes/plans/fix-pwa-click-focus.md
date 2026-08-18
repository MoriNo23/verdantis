# Plan: Fix de enfoque PWA en click (daemon + tester)

Repositorio: `/home/extra/repositorios/verdantis`
Entorno: local (fullmetal), Python 3.13 en `.venv/`
Convenciones (AGENTS.md): código/commits en español, TDD (test rojo → fix → verde),
tests headless con `GDK_BACKEND=offscreen` seteado ANTES de importar.

## Contexto (por qué se hace)

Al clickear el toast de una notificación PWA, Verdantis NO re-enfoca la ventana de la
PWA. En cambio, con dropdown "vacío" o "navegador" sí abre pestaña (via `xdg-open`).

Causas (diagnosticadas en `src/verdantis_daemon.py` y `tests/fixtures/notify-tester/server.js`):

1. **Daemon no guarda el `sender`** de la notificación. En
   `_handle_method_call` (linea ~387) el param `sender` se recibe y se descarta; no se
   guarda en `self._notifications[nid]`.
2. **Daemon emite `ActionInvoked` como broadcast** (`emit_signal(None, ...)`, linea ~307)
   en vez de dirigido al emisor. La spec freedesktop manda dirigirlo al sender que emitió
   `Notify`. Chromium re-enfoca la PWA solo si recibe `ActionInvoked` dirigido a su conexión.
3. **El tester es emisor efímero**: `server.js`/`notify.js` manda con `spawn("gdbus", ...)`
   que muere al salir. Aun si el daemon emitiera dirigido, no hay quien escuche.

El filtro de URLs locales/privadas (`_is_local_url`, ya mergeado en este branch) sigue
aplicando: en caso PWA nunca se hace `xdg-open`, asi que el tester con url
`http://localhost:8766/...` no abre nada. No tocar ese filtro.

## Decisiones tomadas (defaults recomendados)

- **Fix A**: daemon guarda `sender` en `notify()` y emite `ActionInvoked` DIRIGIDO al
  sender SIEMPRE (no solo PWA) — es lo correcto por spec y no cambia el caso navegador
  (ahi igual se hace `xdg-open`).
- **Fix B**: tester mantiene conexion DBus viva que escucha `ActionInvoked` y re-enfoca la
  ventana de Brave con `xdotool` (B1, mas simple y observable). Ademas loguea el evento.

## Pasos (TDD)

### Paso 1 — Test unitario del daemon (rojo primero)
Archivo: `tests/test_click_pwa.py` (agregar al final, seguir estilo existente).

Nuevo test `test_on_action_invoked_emits_actioninvoked_to_sender`:
- Armar un `NotificationManager` y un mock de bus.
- Stub de `notify()` no es necesario: inyectar directo en
  `mgr._notifications[nid] = {..., "sender": ":1.42", "desktop_entry": PWA_DESKTOP}`.
- Llamar `mgr._on_action_invoked(nid)`.
- Afirmar `bus.emit_signal` fue llamado con `dest=":1.42"` (primer arg positional de
  `emit_signal`). Hoy se llama con `None` → el test FALLA (rojo).

Nuevo test `test_notify_stores_sender`:
- Llamar `mgr.notify(app_name=..., hints={...})` con un `sender` inyectado. PERO
  `notify()` no recibe sender hoy. Para testear sin acoplar al bus, se puede llamar
  `_handle_method_call` con `sender=":1.99"` y un `invocation` mock, y luego chequear
  `mgr._notifications[nid]["sender"] == ":1.99"`. Si eso es muy acoplado, alcanza con el
  test de `emit_signal` dirigido del punto anterior + un assert de que `notify` guarda
  sender cuando se le pase. Resolucion a criterio del ejecutor: lo importante es cubrir
  que el destino del emit sea el sender, no None.

### Paso 2 — Fix A1: guardar sender en `notify()` / `_handle_method_call`
En `src/verdantis_daemon.py`:
- `_handle_method_call` (linea ~387) recibe `sender` como 2do param. Pasarlo a
  `self._manager.notify(..., sender=sender)`.
- `notify()` (linea ~206) acepta `sender=""` y lo guarda en
  `self._notifications[nid]["sender"] = sender`.

### Paso 3 — Fix A2: emitir dirigido al sender
En `_on_action_invoked` (linea ~305-313): cambiar
`self._dbus_bus.emit_signal(None, "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "ActionInvoked", GLib.Variant("(us)", (nid, action_key)))`
por
`self._dbus_bus.emit_signal(info.get("sender") or None, <mismos args>)`.
(O `or None` para no romper notificaciones sin sender conocido.)

### Paso 4 — Metatest de sensibilidad
En `tests/test_click_pwa_metatest.py`: inyectar version bugueada de `_on_action_invoked`
que emita con `dest=None` y verificar que el test del Paso 1 la detecta (falla). Esto
garantiza que el fix no es un false-positive. Seguir el patron ya existente en ese archivo
(`_buggy_on_action_invoked` + `test_sensitivity_pwa_bug_detected`).

### Paso 5 — Fix B: tester escucha ActionInvoked y re-enfoca Brave
En `tests/fixtures/notify-tester/notify.js` (o `server.js`): reemplazar el `spawn("gdbus")`
efimero por una conexion Gio persistente (p.ej. `Gio.bus_get_sync(Gio.BusType.SESSION)` +
`conn.signal_subscribe(...)` sobre `org.freedesktop.Notifications` / `ActionInvoked`) que:
- al recibir `ActionInvoked` para el nid que mandó, ejecute
  `xdotool search --class brave windowactivate` (o `wmctrl -a brave`) para re-enfocar,
  Y loguee `"ActionInvoked recibido: nid=X key=Y"` a stdout para debug.
- mantenga el proceso node vivo mientras el server corre (no hacer `wait` que cuelga;
  el server ya corre en background por `serve-tester.sh`).

Nota: si `xdotool`/`wmctrl` no estan instalados, el paso de re-enfoque es best-effort
(try/except) y el logueo es lo obligatorio. Verificar con `command -v xdotool`.

### Paso 6 — Verificacion
- `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_uv_migration.py`
  → debe dar todo verde (hoy 90 passed + los nuevos).
- Prueba manual: `sh tests/fixtures/serve-tester.sh`, elegir dropdown PWA en el GUI,
  "Enviar notificacion", clickear el toast → debe verse el log
  `"ActionInvoked recibido"` en la terminal del server y la ventana de Brave re-enfocar
  (no abrir duplicada). Confirmar tambien que "vacío"/"navegador" siguen abriendo pestaña
  y que localhost NO abre nada (filtro existente).

### Paso 7 — Commit
- `git add` de los archivos tocados.
- Commit conventional: `fix: click PWA re-enfoca emisor via ActionInvoked dirigido`.

## Archivos a tocar
- `src/verdantis_daemon.py` (guardar sender en notify/_handle_method_call; emitir dirigido)
- `tests/test_click_pwa.py` (test rojo de emit dirigido)
- `tests/test_click_pwa_metatest.py` (metatest sensibilidad broadcast)
- `tests/fixtures/notify-tester/notify.js` o `server.js` (conexion persistente + xdotool/log)

## Riesgos
- El `dest` del `emit_signal` en Gio es el 1er arg positional (`destination_bus_name`).
  Confirmar firma antes de editar: `emit_signal(destination, object_path, interface_name,
  signal_name, parameters, ...)`.
- No romper `test_click_no_pwa.py` (caso navegador sigue haciendo xdg-open).
- `test_uv_migration.py` se excluye siempre (necesita red).
