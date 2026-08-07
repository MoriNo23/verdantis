# Investigación: raíz Wayland, pipeline de notificaciones y click→focus (Verdantis)

> **Para Hermes:** plan de INVESTIGACIÓN + instrumentación + fixes. No es implementación directa: cada fase termina con evidencia empírica verificable antes de seguir. Aplicar fases en orden; la Fase 1 y 3 requieren aprobación de Mori antes de tocar código productivo.

**Goal:** Determinar por qué "algunas cosas no funcionan como deberían" en Verdantis, en 3 frentes: (1) si está conectado a la raíz Wayland correcta, (2) cómo se manejan las notificaciones a nivel API (DBus + layer-shell), (3) por qué el click a un toast no hace focus/activación de la app (caso navegador).

**Architecture:** Verdantis es un daemon DBus (`org.freedesktop.Notifications`, spec 1.2) que renderiza popups como surfaces `wlr-layer-shell` (GTK3 3.24.49 + gtk-layer-shell). Wayland core NO tiene API de notificaciones: el pipeline es app → DBus → daemon → surface layer-shell → pointer input → `ActionInvoked`. El foco de ventanas en Wayland se resuelve con `zwp_xdg_activation_v1` (xdg-activation), que hoy el daemon NO usa.

**Tech Stack:** Python 3.13, PyGObject/GTK3 3.24.49, gtk-layer-shell, PyQt6 (fallback), DBus session bus, KWin/Plasma 6 (Wayland), kdotool (verificación de foco).

---

## Contexto actual (ya verificado, solo lectura)

- `verdantis.service` (systemd user, Type=dbus) corre `verdantis.py --daemon` → delega a `verdantis_daemon.main()`. GDK_BACKEND=wayland forzado en el service y en ambos módulos.
- **AHORA mismo** `org.freedesktop.Notifications` lo tiene verdantis (PID 3905) con plasmashell VIVO (PID 1748886). O sea: el plugin de notificaciones de Plasma NO está reclamando el nombre. Este es ya un dato de la Fase 0.
- Env actual: `WAYLAND_DISPLAY=wayland-0`, `XDG_RUNTIME_DIR=/run/user/1000`, `XDG_SESSION_TYPE=wayland`, socket existe, service `active`.
- GTK 3.24.49 → soporta `GdkAppLaunchContext.set_activation_token` (desde 3.24.20) y el backend Wayland pide token xdg-activation automáticamente al lanzar con un `GdkAppLaunchContext`.
- `kdotool` instalado (`/usr/local/bin/kdotool`) → verificación de foco en KWin/Wayland posible. `qdbus` ROTO (sin Qt para qdbus) → NO usar qdbus como vía de verificación.

### Pipeline actual (lectura de código)

```
app (Chrome/Firefox) --DBus Notify--> NotificationManager.notify()
  → WaylandPopup.prepare() → GtkLayerShell.init_for_window (TOP layer, exclusive-zone -1,
    anchors según corner, sin set_monitor → output por defecto)
  → click en card → NotificationWidget._on_button_press → _on_click
  → NotificationDaemon._on_action_invoked(nid):
      1. Emite ActionInvoked(nid, "default")  ← SIEMPRE "default", aunque el sender no la haya dado
      2. Si hay URL (hints x-kde-urls/url/data o <a href> del body) → xdg-open URL
      3. Si no → _focus_or_activate_app(desktop_entry, app_name)
         → Gio.DesktopAppInfo.launch()  ← Lanza NUEVO proceso, sin token de activación
         → fallback gtk-launch <id>
```

## Hallazgos / hipótesis de mecanismo (explicados ANTES de probar)

### Q1 — ¿Raíz Wayland correcta?

**Hipótesis:** la conexión es correcta hoy (socket wayland-0 existe, layer-shell soportado, verdantis renderiza), pero el código no lo VERIFICA ni lo reporta:

- `prepare()` solo chequea `os.environ.get("WAYLAND_DISPLAY")`. No valida `XDG_RUNTIME_DIR`, existencia del socket, compositor real, seat, ni outputs.
- `GtkLayerShell.set_monitor()` NUNCA se llama → usa el output por defecto del compositor. En multi-monitor el toast puede caer en la pantalla equivocada (o en una apagada).
- El service systemd puede heredar env stale si arrancó fuera de la sesión gráfica (`After=graphical-session.target` mitiga, pero no valida el socket).
- **Verificación empírica de la hipótesis:** Fase 1 (`--check`) + pregunta a Mori sobre si tiene multi-monitor y en cuál ve los toasts.

### Q2 — ¿Cómo maneja la API las notificaciones?

**Mecanismo (respuesta de fondo):**
- Wayland NO tiene protocolo de notificaciones. Lo que hay: DBus `org.freedesktop.Notifications` para el CONTRATO (Notify/Close/GetCapabilities/GetServerInformation/signals), y `wlr-layer-shell` (extensión wlroots implementada por KWin) para el RENDER (surface anclada al borde, TOP layer, exclusive-zone).
- El foco es un tercer mecanismo aparte: `zwp_xdg_activation_v1`. Una surface layer-shell puede recibir pointer input (por eso el click llega), pero NO recibe foco de teclado por defecto y NO puede activar otras ventanas sin token xdg-activation.
- El daemon declara capabilities: `actions, body, body-markup, body-hyperlinks, icon-static, persistence`. NO declara `action-icons` (correcto) — revisar si falta algo para el spec 1.2 completo.

### Q3 — ¿Click→focus de las notificaciones del navegador?

**Mecanismo spec:** los navegadores (Chrome/Firefox) registran la action `"default"` y esperan que el daemon emita `ActionInvoked(id, "default")`; es EL NAVEGADOR quien levanta su propia ventana. El daemon no debería lanzar nada más cuando hay `default` action.

**Bugs detectados por lectura de código (candidatos a "no funciona como debería"):**

1. **BUG-1 (doble handling):** además de emitir `ActionInvoked("default")`, `_on_action_invoked` lanza `Gio.DesktopAppInfo.launch()`/`gtk-launch` cuando no hay URL. Para una notificación de navegador, eso **abre una SEGUNDA instancia/ventana del navegador** en vez de enfocar la existente. El "focus" percibido como roto viene de acá.
2. **BUG-2 (key inventada):** emite SIEMPRE `"default"` aunque el sender no haya provisto esa action. Spec: emitir la key real que el sender registró (primera del par actions[]), o no emitir si no hay actions.
3. **BUG-3 (sin xdg-activation):** `Gio.DesktopAppInfo.launch()` no pasa token de activación; KWin no garantiza raise/focus de la ventana nueva. Fix mecanismo: usar `Gdk.app_launch_context()` (GTK pide token xdg-activation automáticamente en Wayland tras el click del usuario, que es input reciente → el compositor concede el token).
4. **Verificación limitada:** en Wayland nativo no hay xdotool; usar `kdotool` (`kdotool getactivewindow`, `kdotool activate`) o validación visual de Mori.

**Dato ambiental relevante:** hoy verdantis es owner del bus CON plasmashell vivo. Si Plasma vuelve a reclamar el nombre, verdantis pierde (NameLost, `_owned=False`) y queda idle. Verificar re-adquisición al matar plasmashell (Gio re-intenta? → test empírico).

---

## Fase 0 — Línea base y pruebas manuales (SIN código)

**Objetivo:** capturar comportamiento actual antes de tocar nada. Evidencia que valida/descarta BUG-1/2/3.

**Files:**
- Ninguno (solo comandos de observación)
- Test: `tests/test_real_notification.py` ya existe (usar como referencia de lo que ya está cubierto)

**Step 1 — ActionInvoked con action real.**
Abrir monitor del bus en background:
```bash
dbus-monitor --session "interface='org.freedesktop.Notifications'" &
```
Disparar notificación con action default:
```bash
notify-send -a firefox "test" "click me" --action=default:"Abrir" --expire-time=5000
```
Click en el toast. Esperado (mecanismo spec): se ve `ActionInvoked` en dbus-monitor Y el navegador/`notify-send` ya no existe... — con notify-send NO hay sender que responda; usar esto solo para ver el signal. Esperado real: `ActionInvoked` emitido + gtk-launch intentando lanzar (BUG-1 se observa si se abre una app/ventana nueva).

**Step 2 — Repetir con notificación REAL del navegador.**
Abrir Firefox/Chromium nativo Wayland, recibir una notificación real (ej: mensaje de YouTube/WhatsApp Web), click en el toast.
Esperado si BUG-1 aplica: se abre NUEVA ventana de Firefox en vez de enfocar la existente.
Anotar: ¿qué `desktop-entry`/hints mandó el navegador? (capturar con dbus-monitor: `member=Notify`).

**Step 3 — URL vs action.**
```bash
notify-send -a firefox "url" "abre" --action=default:"Abrir" --hint=string:x-kde-urls:"https://example.com"
```
Esperado: ActionInvoked + xdg-open (comportamiento correcto: URL manda).

**Step 4 — Estado del bus (quién es owner).**
```bash
busctl --user list | grep org.freedesktop.Notifications
```
Documentar: verdantis con plasmashell vivo (ya observado hoy: verdantis PID 3905). Luego `pkill plasmashell` y re-chequear; `systemctl --user start plasmashell`? — OJO: no reiniciar plasmashell si no hace falta; solo documentar el estado actual.

**Step 5 — Commit de la evidencia:**
```bash
git add . ; git commit -m "docs: evidencia Fase 0 — comportamiento actual click/focus"
```
(solo si hay notas que guardar; si no, registrar en este plan el resultado observado)

**Verification:** las 4 capturas de dbus-monitor + observación visual de Mori (¿se abrió ventana duplicada? ¿el toast clickeado enfocó algo?).

---

## Fase 1 — Diagnóstico de raíz Wayland: flag `--check` (instrumentación)

**Objetivo:** que el daemon REPORTE su raíz Wayland real (display, socket, compositor, outputs, seat, owner del bus) para diagnóstico reproducible. Código mínimo, sin cambiar comportamiento de render.

**Files:**
- Modify: `src/verdantis_daemon.py` (añadir `--check` en `main()` + función `_wayland_health()`)
- Test: `tests/test_wayland_check.py` (nuevo)

**Step 1: Test que define el contrato de `--check` (TDD, falla primero).**
```python
# tests/test_wayland_check.py
def test_check_prints_wayland_env():
    # _wayland_health() devuelve dict con: wayland_display, xdg_runtime_dir,
    # socket_exists, compositor(s), outputs, seat, layer_shell_supported, bus_owner
    import subprocess, os
    env = dict(os.environ)
    r = subprocess.run(
        [".venv/bin/python", "src/verdantis_daemon.py", "--check"],
        capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 0
    assert "wayland-0" in r.stdout or "WAYLAND_DISPLAY" in r.stdout
```

**Step 2: correr el test → FAIL** (`pytest tests/test_wayland_check.py -v`).

**Step 3: implementar `_wayland_health()` en `src/verdantis_daemon.py`:**
```python
def _wayland_health():
    info = {
        "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
        "socket_exists": False,
        "compositor": "",
        "outputs": [],
        "seat": "",
        "layer_shell_supported": GtkLayerShell.is_supported(),
        "bus_owner": "",
    }
    rt = os.environ.get("XDG_RUNTIME_DIR", "")
    wd = os.environ.get("WAYLAND_DISPLAY", "")
    if rt and wd:
        info["socket_exists"] = os.path.exists(os.path.join(rt, wd))
    # outputs/seat reales: leer del display GDK ya inicializado (Gdk.Display.get_default)
    display = Gdk.Display.get_default()
    if display:
        info["seat"] = display.get_default_seat().get_name() if display.get_default_seat() else ""
        for i in range(display.get_n_monitors()):
            m = display.get_monitor(i)
            info["outputs"].append({
                "idx": i, "model": m.get_model() or "",
                "w": m.get_geometry().width, "h": m.get_geometry().height,
            })
    return info
```
(compositor: leer `env | grep -i XDG_CURRENT_DESKTOP`; o desde `os.environ.get("XDG_CURRENT_DESKTOP")`. Nota: `Gdk.Display.get_default()` solo existe tras inicializar GTK — en `--check` inicializar `Gtk.init()` primero.)

Añadir en `main()`:
```python
parser.add_argument("--check", action="store_true", help="Diagnóstico: imprime estado Wayland y sale")
if args.check:
    Gtk.init([])
    import json
    print(json.dumps(_wayland_health(), indent=2, ensure_ascii=False))
    sys.exit(0)
```

**Step 4: correr test → PASS** (`pytest tests/test_wayland_check.py -v`).

**Step 5: verificación manual:**
```bash
.venv/bin/python src/verdantis_daemon.py --check
```
Esperado: JSON con `socket_exists: true`, outputs con el monitor real (o varios si multi-monitor), `layer_shell_supported: true`, `bus_owner: org.freedesktop.Notifications` (o el de Plasma).

**Step 6: Commit** `test: --check diagnostica raíz Wayland`.

**Nota para Mori:** si `--check` muestra outputs ≠ 1 (multi-monitor), pasar a Fase 4; si el toast cae en el monitor equivocado, eso es Q1 confirmado.

---

## Fase 2 — Documentar el pipeline en tests (fijar el contrato actual)

**Objetivo:** que la suite verifique el contrato DBus/notificaciones actual ANTES de los fixes (evita regresiones). Sin cambiar comportamiento.

**Files:**
- Modify: `tests/test_body_markup.py` (ya cubre body-markup — ampliar si falta)
- Test: `tests/test_dbus_contract.py` (nuevo)

**Step 1: Test del contrato de capabilities y signals:**
```python
# tests/test_dbus_contract.py
def test_capabilities_spec_12():
    # GetCapabilities debe incluir body, body-markup, body-hyperlinks, actions, icon-static
    ...

def test_action_invoked_uses_real_key():
    # Dado actions=["default", "Abrir", "open", "Ir"], _on_action_invoked debe emitir "default"
    # Dado actions=["open", "Ir"] (sin default), debe emitir "open"  ← hoy emite "default" (BUG-2)
    ...
```
Nota: el segundo test documenta el bug actual; pasa a ser el test de regresión del fix en Fase 3.

**Step 2: correr → ver estado actual** (documentar qué falla = BUG-2 confirmado en test, no en runtime).

**Step 3: Commit** `test: contrato DBus/signals fijado`.

---

## Fase 3 — Fix click→focus (BUG-1/2/3)

**Objetivo:** click en toast = activación correcta: `ActionInvoked` con key real + (si hay URL) `xdg-open`; si no, lanzar app SOLO cuando no hay `default` action, y lanzarla con token de activación (xdg-activation) para que KWin haga focus/raise.

**Files:**
- Modify: `src/verdantis_daemon.py` (`_on_action_invoked`, `_focus_or_activate_app`)
- Test: `tests/test_dbus_contract.py` (el de Fase 2 pasa de documentar a exigir)

**Step 1: Test que exige key real (TDD):**
```python
def test_action_invoked_uses_real_key():
    # con actions=["open", "Ir"] → key == "open"
    # con actions=[] → NO se emite ActionInvoked
```
Correr → FAIL (BUG-2 actual).

**Step 2: Fix BUG-2 en `_on_action_invoked`:**
```python
default_action = None
for i in range(0, len(actions) - 1, 2):
    if actions[i] == "default":
        default_action = "default"
        break
if default_action is None and len(actions) >= 2:
    default_action = actions[0]   # primera key real del sender
# solo emitir si hay action real
if default_action and self._dbus_bus:
    ... emit ActionInvoked(nid, default_action)
```
Correr → PASS.

**Step 3: Fix BUG-1 (no auto-lanzar si hay "default" action):**
```python
# en _on_action_invoked, después de emitir el signal:
if url:
    xdg-open url
elif default_action == "default":
    # el sender (navegador) maneja su propio focus vía ActionInvoked — NO lanzar
    pass
else:
    self._focus_or_activate_app(desktop_entry, app_name)
```
Test: `test_no_launch_when_default_action()` — mockear `subprocess.Popen` y `Gio.DesktopAppInfo.launch`; con actions=["default",...] y sin URL → assert que NO se llama a launch.

**Step 4: Fix BUG-3 (xdg-activation al lanzar):** reemplazar `Gio.DesktopAppInfo.launch([], None)` por launch con `Gdk.AppLaunchContext`:
```python
from gi.repository import Gdk
def _launch_with_activation(desktop_path):
    app_info = Gio.DesktopAppInfo.new_from_filename(desktop_path)
    if not app_info:
        return False
    display = Gdk.Display.get_default()
    ctx = Gdk.AppLaunchContext.new() if display else None
    # GTK Wayland pide token xdg-activation automáticamente al lanzar;
    # el click reciente en el toast = input reciente → KWin concede el token
    return app_info.launch([], ctx)
```
Pitfall: `Gdk.AppLaunchContext.new()` — en GTK3 es `Gdk.AppLaunchContext.new()` (no `new_for_display` hasta GTK4). Verificar en runtime; si `ctx` es None o falla, mantener `launch([], None)` como fallback (no romper el caso actual).

Test: `test_launch_uses_gdk_context()` — assert que `_launch_with_activation` llama `app_info.launch` con contexto no-None cuando hay display. (En CI/headless puede no haber display: parametrizar y aceptar fallback.)

**Step 5: Verificación empírica en KWin (foco real):**
```bash
# antes: ventana activa
kdotool getactivewindow
# disparar notificación de navegador real + click
kdotool getactivewindow   # esperado: el navegador (si BUG-1/3 arreglados)
```
Validación visual de Mori (él valida; el agente arma el harness con kdotool).

**Step 6: Suite completa** `pytest tests/ -v` → todo PASS. Luego mutation/metatests si aplica (patrón del repo: tests visuales numéricos + metatests de sensibilidad).

**Step 7: Commit** `fix: click toast → ActionInvoked con key real, sin doble lanzamiento, xdg-activation`.

---

## Fase 4 — Monitor explícito (SOLO si --check muestra multi-output)

**Objetivo:** que el toast aparezca en el monitor correcto.

**Files:**
- Modify: `src/wayland_popup.py` (`_build_ui`, tras `init_for_window`)
- Test: `tests/test_expand_layout.py` (existente — verificar no romper)

**Step 1 (hipótesis antes de tocar):** `GtkLayerShell.set_monitor(window, monitor)` con el monitor primario (`Gdk.Display.get_default_monitor()`) — o el del cursor si KWin lo permite. Elegir PRIMARIO salvo evidencia contraria (KWin layer-shell no expone "monitor del cursor" sin API extra).

**Step 2: implementar + test** (test visual numérico estilo repo: `tests/test_visual.py` — verificar que los márgenes/anchors siguen cuadrando en monitor seleccionado).

**Step 3: verificación visual de Mori** en ambas pantallas.

**Step 4: Commit** `feat: toasts en monitor primario explícito`.

---

## Resumen de archivos a tocar

| Archivo | Fase | Cambio |
|---|---|---|
| `src/verdantis_daemon.py` | 1, 2, 3 | `--check`/`_wayland_health`, fix `_on_action_invoked`, `_launch_with_activation` |
| `src/wayland_popup.py` | 4 | `set_monitor` (solo si multi-monitor) |
| `tests/test_wayland_check.py` | 1 | nuevo |
| `tests/test_dbus_contract.py` | 2, 3 | nuevo (contrato + regresión BUG-2) |
| `tests/test_*.py` existentes | todas | correr suite, no romper |
| `verdantis.service` | solo si falta env | revisar `Environment=` (no parece faltar hoy) |

## Tests / validación

- `pytest tests/ -v` → todo PASS al final de cada fase.
- Evidencia empírica por fase: dbus-monitor (F0), `--check` JSON (F1), suite contrato (F2), kdotool activewindow + ojo de Mori (F3), pantallas (F4).
- NO ensayo-error: cada fix va con su test de regresión ANTES.

## Riesgos / tradeoffs / preguntas abiertas

1. **Dejar de auto-lanzar (BUG-1) cambia UX**: apps que no manejen `default` action dejarán de abrirse al click. Verificar con Chrome Y Firefox reales antes de decidir si el fix aplica siempre o solo cuando hay URL. → Pregunta a Mori: ¿el click debe SIEMPRE abrir la app, o solo cuando no hay action "default"?
2. **Token xdg-activation**: KWin concede token solo si hubo input reciente en la surface que lo pide. El click en el toast es input reciente → debería conceder. Si no, fallback a `launch([], None)` (comportamiento actual). Verificar con kdotool.
3. **Plasma vs verdantis por el bus**: hoy verdantis es owner con plasmashell vivo (dato F0). Si Plasma reclama, verdantis queda idle (NameLost). ¿Se quiere que verdantis COMPITA (flags `ALLOW_REPLACEMENT`+`REPLACE`) o que siga el diseño actual (solo actúa si Plasma no está)? → Decisión de Mori en Fase 0.
4. **Multi-monitor**: si el usuario tiene 1 solo monitor, Fase 4 se omite (YAGNI).
5. **qdbus roto**: no usar como vía de verificación; kdotool cubre el caso.

## Pregunta inicial para Mori (antes de ejecutar Fase 0)

- ¿Tenés más de un monitor? (define si Fase 4 entra)
- ¿Preferís que el click SIEMPRE abra/active la app, o respetar la semántica "default action" del spec (dejar que el navegador se enfoque solo)?
- ¿Verdantis debe tomar el bus aunque Plasma esté vivo, o solo actuar cuando Plasma no está?
