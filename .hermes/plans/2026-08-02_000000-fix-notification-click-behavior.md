# Plan de Implementación: Corrección del Comportamiento de Clic en Notificaciones (Redirección Estándar y Cierre Inmediato)

> **Para Hermes:** Usar la skill `subagent-driven-development` para implementar este plan paso a paso.

**Objetivo:** Replicar el comportamiento nativo de notificaciones (Windows, Linux, macOS) para que al hacer clic en una notificación:
1. Si contiene una URL o recurso web, redirija abriendo dicha URL (`xdg-open`).
2. Si proviene de una app (Telegram, Discord, Spotify, Mail, etc.), emita el signal DBus `ActionInvoked` para que la aplicación receptora redirija internamente al mensaje, conversación o elemento específico, aplicando un enfoque de respaldo (`desktop-entry` / `app_name`) si la app lo requiere.
3. Cierre inmediatamente la ventana flotante de la notificación.
4. Se elimine la firma del vendor `"opencode"` en el servicio DBus.

**Arquitectura:**
- **Emisión de `ActionInvoked`:** Al hacer clic en el cuerpo de la notificación, emite la acción `"default"` sobre DBus. Esto es el estándar freedesktop que usan Telegram, Thunderbird, Discord, etc., para abrir el chat o mensaje específico que originó la notificación.
- **Manejo de URLs:** Extrae de los `hints` (`url`, `x-kde-urls`, `data.url`) cualquier dirección web/URI. Si existe, la abre con `xdg-open`.
- **Respaldo de Activación/Enfoque:** Extrae `desktop-entry` o `app_name` de los `hints`. Si la app no maneja la redirección DBus autónomamente, utiliza la información del archivo `.desktop` para enfocar la instancia en ejecución.
- **Destrucción Visual del Popup:** En el handler de clic (`_on_action_invoked`), invoca directamente `popup._close()` para que la ventana GTK sea destruida al instante en pantalla.
- **Limpieza de Vendor:** Reemplaza la cadena `"opencode"` en `GetServerInformation` por `"notify-app"`.

---

### Tarea 1: Eliminar la firma "opencode" del vendor DBus

**Objetivo:** Reemplazar el nombre del vendor `"opencode"` en el método `GetServerInformation`.

**Archivos:**
- Modificar: `src/notify_daemon.py:262-264`

**Paso 1: Modificar `_handle_method_call` en `src/notify_daemon.py`**
Reemplazar:
```python
elif method_name == "GetServerInformation":
    invocation.return_value(GLib.Variant("(ssss)", (
        "notify-app", "opencode", "0.1.0", "1.2",
    )))
```
Por:
```python
elif method_name == "GetServerInformation":
    invocation.return_value(GLib.Variant("(ssss)", (
        "notify-app", "notify-app", "0.1.0", "1.2",
    )))
```

---

### Tarea 2: Mejorar la extracción de hints (`desktop-entry`, `url`, `x-kde-urls`)

**Objetivo:** Capturar correctamente el campo `desktop-entry` enviado por las aplicaciones clientes en DBus.

**Archivos:**
- Modificar: `src/notify_daemon.py` (métodos `_extract_url` y `notify`)

**Paso 1: Extraer y almacenar `desktop-entry` en los datos de la notificación**
En `NotificationManager.notify()`:
```python
desktop_entry = hints.get("desktop-entry", "") or app_name
self._notifications[nid] = {
    "actions": actions,
    "hints": hints,
    "url": url,
    "app_name": app_name,
    "desktop_entry": desktop_entry,
}
```

---

### Tarea 3: Implementar la redirección nativa (`ActionInvoked` + URL + Enfoque Fallback)

**Objetivo:** Redirigir al contexto específico del mensaje/app y cerrar la notificación de inmediato.

**Archivos:**
- Modificar: `src/notify_daemon.py` (`_on_action_invoked`)

**Paso 1: Implementar `_focus_or_activate_app(desktop_entry, app_name)`**
```python
def _focus_or_activate_app(self, desktop_entry, app_name):
    target = desktop_entry or app_name
    if not target:
        return
    desktop_path = _find_desktop_file(target)
    if desktop_path and os.path.exists(desktop_path):
        try:
            app_info = Gio.DesktopAppInfo.new_from_filename(desktop_path)
            if app_info:
                app_info.launch([], None)
                return
        except Exception:
            pass
    try:
        subprocess.Popen(["gtk-launch", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
```

**Paso 2: Actualizar `_on_action_invoked(self, nid)`**
```python
def _on_action_invoked(self, nid):
    info = self._notifications.get(nid, {})
    actions = info.get("actions", [])
    url = info.get("url", "")
    app_name = info.get("app_name", "")
    desktop_entry = info.get("desktop_entry", "")

    default_action = "default"
    for i in range(0, len(actions), 2):
        if actions[i] == "default":
            default_action = actions[i]
            break

    # 1. Emitir la señal DBus ActionInvoked para que la app cliente (Telegram, Spotify, etc.)
    # reciba la acción y redirija al mensaje/chat/canción específica.
    if self._dbus_bus:
        try:
            self._dbus_bus.emit_signal(
                None, "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", "ActionInvoked",
                GLib.Variant("(us)", (nid, default_action)),
            )
        except Exception:
            pass

    # 2. Si la notificación contiene una URL explícita, abrirla con xdg-open.
    if url:
        try:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        # Fallback de enfoque/activación por desktop-entry
        self._focus_or_activate_app(desktop_entry, app_name)

    # 3. CERRAR INMEDIATAMENTE el popup visual en pantalla
    for aid, popup in list(self._active):
        if aid == nid:
            popup._close()
            break
```

---

### Tarea 4: Verificación y Pruebas Integradas

**Objetivo:** Probar el comportamiento con notificaciones simuladas y clientes reales.

**Pasos de prueba:**
1. **Verificación de firma:**
   - Comprobar que `GetServerInformation` retorne `"notify-app"` como vendor.
2. **Notificación con URL:**
   - Crear notificación con hint de URL (`url="https://github.com"`).
   - Verificar que al hacer clic se abra la página web y el popup se cierre al instante.
3. **Notificación de aplicación (ej. Telegram / Chat / Email):**
   - Verificar la emisión de `ActionInvoked` en la bus de DBus y el cierre inmediato de la ventana.
4. **Verificación del temporizador vs Clic:**
   - Comprobar que al hacer clic la ventana desaparezca de inmediato sin esperar el timeout de 6-8 segundos.
