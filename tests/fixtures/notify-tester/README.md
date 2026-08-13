# Verdantis Notify Tester

App node que dispara notificaciones REALES por D-Bus (`org.freedesktop.Notifications`)
con todos los parámetros del spec freedesktop 1.2 + los hints que el daemon de
Verdantis consume. Reemplaza al viejo `notify-tester.html` estático, que usaba la
API `Notification` del navegador y NO podía mandar hints de D-Bus (por eso no
reproducía el bug del click en PWA).

## Uso

```sh
sh tests/fixtures/serve-tester.sh
# abrir en el navegador: http://localhost:8766/notify-tester.html
```

GUI de 3 paneles:
- **Parámetros D-Bus**: app_name, app_icon, summary, body, replaces_id,
  expire_timeout, desktop-entry, url, x-kde-urls, urgency, image-path, accent, category.
- **Comportamiento**: suppress-sound (silencia), requireInteraction (→ expire_timeout=0).
- **Actions**: builder dinámico de pares [key, label] (ej `default` / `Abrir`).
- **Preview JSON** en vivo del payload que se manda.
- **Log** de eventos (id D-Bus devuelto / errores gdbus).

## Qué reproduce y qué NO

El tester manda la notificación por `gdbus` con el mismo `desktop-entry` que un
navegador real. Eso es la ENTRADA al daemon. Para validar el bug del click en PWA:

1. Elegí `desktop-entry = brave-...-Default.desktop` (PWA WhatsApp) + Acción `default`.
2. Enviá la notificación → Verdantis la dibuja como toast.
3. Clickeá el toast físicamente → el daemon emite `ActionInvoked` y, por ser PWA,
   NO hace `xdg-open` (fix en `verdantis_daemon.py:_on_action_invoked` + `_is_pwa`).
   El navegador recibe `ActionInvoked` y re-enfoca su tab/ventana.

**Limitación**: simular el click del usuario NO tiene método D-Bus estándar. El
click es físico en el toast; el daemon EMITE `ActionInvoked` (el navegador lo
consume). El tester no puede emitir el click de salida. Por eso la parte del
"re-enfocar vs abrir duplicada" se valida VISUALMENTE con el navegador.

## Parámetros Web API vs D-Bus

El tester mapea los que Verdantis consume:
- `silent` → hint `suppress-sound`
- `requireInteraction` → `expire_timeout=0` (persistente)
- `tag` → `replaces_id`
- `actions` → `actions[]` D-Bus

Campos Web API que NO aplican a un daemon D-Bus (no los consume): `badge`, `dir`,
`lang`, `renotify`, `vibrate`, `timestamp`, y los eventos `onshow/onclick/onclose/onerror`
nativos del navegador. Se listan solo a título informativo en el GUI.

## Tests

```sh
cd tests/fixtures/notify-tester
node --test          # 12 unit + metatest, sin D-Bus
```

- `notify.test.js`: forma del comando gdbus, hints, actions builder, PWA lleva
  `desktop-entry`, replaces_id/app_icon, requireInteraction→timeout 0.
- `notify.metatest.js`: sensibilidad — inyecta versión bugueada sin `desktop-entry`
  y verifica que el test la detecta (el fix no es false-positive).

## Verificación del fix del click PWA (automática, en el repo)

No es responsabilidad de este tester (vive en el daemon Python). Se cubre con:

```sh
.venv/bin/python -m pytest tests/test_click_pwa.py tests/test_click_pwa_metatest.py -q
```

Eso mockea `xdg-open` y confirma que para PWA Verdantis NO lo invoca.
