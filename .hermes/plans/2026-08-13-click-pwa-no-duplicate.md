# Plan: click en navegador no abre PWA duplicada (verdantis)

## Problema (root-cause)
Al click en toast de navegador, `verdantis_daemon.py:_on_action_invoked` (L247-249)
siempre hace `xdg-open <url>`. Si la URL es de una web instalada como PWA en
Brave/Chrome, `xdg-open` la entrega al navegador y este abre una ventana-PWA
nueva (p.ej. WhatsApp Web) en vez de enfocar la pestaña. Además, para PWAs el
navegador YA re-enfoca su propia ventana al recibir `ActionInvoked`, así que el
`xdg-open` es redundante y daña.

## Decisión de Mori
- Si `desktop_entry` es una PWA instalada -> solo emitir `ActionInvoked` (la PWA
  re-enfoca sola). NO `xdg-open`.
- Si es navegador genérico o vacío -> `ActionInvoked` + `xdg-open` (abre/focusea tab).

## Mecanismo de detección PWA (confirmado en disco)
Brave crea `~/.local/share/applications/brave-<appid>-<profile>.desktop` con
`Exec=.../brave --profile-directory=Default --app-id=<appid>` y
`StartupWMClass=crx_<appid>`. El navegador manda ese `.desktop` en el hint
`desktop-entry` de la notificación. Se distingue del navegador genérico
(`brave-browser-nightly.desktop`, `firefox-nightly.desktop`) por:
  - `Exec` contiene `--app-id=`, o
  - `StartupWMClass` empieza con `crx_`

## Cambios
1. `src/verdantis_daemon.py`: nueva `_is_pwa(desktop_entry)` que resuelve el path
   del `.desktop` y lee `Exec`/`StartupWMClass`.
2. Modificar `_on_action_invoked`: calcular `is_pwa`; si PWA -> solo ActionInvoked;
   si no -> ActionInvoked + xdg-open (comportamiento actual).

## Tests (TDD, rojo->verde)
`tests/test_click_pwa.py`:
- test_is_pwa_true: usa el .desktop real de WhatsApp (brave-hnpfj...-Default)
- test_is_pwa_false_browser: brave-browser-nightly.desktop
- test_is_pwa_false_empty
- test_on_action_invoked_pwa_no_xdgopen: mock subprocess.Popen + emit_signal,
  desktop_entry PWA -> NO xdg-open, SI ActionInvoked
- test_on_action_invoked_generic_xdgopen: desktop_entry navegador + url -> SI xdg-open
- metatest de sensibilidad: inyectar versión bugueada (xdg-open siempre) y verificar
  que el test lo detecta.

## Tester de notificaciones (frente 2)
`tests/fixtures/notify-tester.html`: botón que pide permiso y dispara
`new Notification(title, {body, tag})` con URL en body, para ejercitar el camino
real D-Bus de verdantis desde el navegador. Servir con
`python3 -m http.server 8766 --directory tests/fixtures`.

## Fuera de alcance
Bug de diseño (Mori lo aborda luego).
