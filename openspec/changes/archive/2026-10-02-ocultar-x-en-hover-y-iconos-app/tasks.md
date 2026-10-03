# Tasks

## 1. Franja X — tests primero (contrato nuevo)

- [x] 1.1 Actualizar los tests que fijan el comportamiento actual al contrato hover-dependiente: `test_eff_text_width_shrinks_for_persistent` (332/240 sin hover, 288/196 con hover), `test_persistent_reserves_strip_in_text_width` y `test_expand_strip_reserves_close_strip` en `tests/test_action_zones.py` (reserva solo con hover) — verificación: esos tests fallan en rojo contra el código actual, documentando el delta del contrato.
- [x] 1.2 Test pixel-level de visibilidad: render headless del widget persistente sin hover → cero píxeles de tinte/X; con hover (`_hover = True`) → tinte presente en los 44 px derechos y píxeles del rosa #f38ba8 de la X — verificación: el test pasa en el estado nuevo y el caso "sin hover reserva 44 px" del contrato viejo queda cubierto por 1.1.
- [x] 1.3 Metatest de sensibilidad (convención `test_tests_*.py`): inyectar la versión bugueada (franja dibujada sin hover, y reserva permanente de 44 px) y verificar que la suite la detecta — verificación: el metatest pasa porque los tests de 1.1/1.2 se rompen con el bug inyectado.

## 2. Franja X — implementación

- [x] 2.1 Ancho hover-dependiente en la métrica única: `_eff_text_width()` resta `_CLOSE_STRIP_W` solo con `self._persistent and self._hover`; `_draw` calcula `strip_w` igual; eliminar la resta interna y el parámetro `persistent` de `calc_card_height` y actualizar sus callers (`desired_height`, `_apply_margins`, tests) — verificación: tests de 1.x en verde y `tests/test_layout_consistency.py` verde (altura y wrap no divergen).
- [x] 2.2 Transición de altura en hover: `_on_enter`/`_on_leave` recomputan `desired_height()` y llaman `self._on_resize` solo si el alto cambió — verificación: test nuevo que simula enter/leave con un cuerpo cuyo re-wrap cambia el número de líneas → la altura cambia por la vía existente y ningún bloque del card (app/título/body/barra "Ver más") se solapa en el render.
- [x] 2.3 Validador del tablero en verde: `python3 DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py --self-test` — verificación: exit 0 con xs=[40, 440, 840], alturas=[113, 108, 108, 174, 113] y columnas (332, 240, 288) derivadas de las constantes (la 288 pasa a ser el estado hover, nota semántica del design D7).

## 3. Iconos — auditoría de adquisición

- [x] 3.1 Auditoría end-to-end documentada del `app_icon`: trace desde DBus `Notify` → `_local_path`/`os.path.exists` en el daemon → `kwargs["app_icon"]` → cadena del widget, con senders reales (Brave `file:///tmp/...`, app de sistema con nombre pelado, app desconocida) — verificación: hallazgos listados en la task al completarla (incl. confirmación de que los nombres pelados hoy llegan como `""`) y repro mínimo con una noti de prueba.

  **Hallazgos** (dataset real: `~/.local/share/verdantis/history.jsonl`, 1000 notificaciones):
  - **43.5% (435/1000) mandan un NOMBRE DE TEMA pelado** en `app_icon` (13 nombres distintos). Remitentes: "Gestión de redes" 420, "Comprimir" 5, "trimar" 4, "Spectacle" 3, "Notificaciones del sistema" 2, "Reloj" 1. Ejemplos: `network-wireless-disconnected` (151), `network-wireless-on` (113), `dialog-warning` (89), `network-limited` (60).
  - **Confirmado el hallazgo del proposal**: `app_icon_file = _local_path(app_icon) if os.path.exists(...) else ""` los convierte TODOS en `""` → el `_icon_from_theme(app_icon, 16)` del widget es **código muerto** en la práctica. Repro: `app_icon="network-wireless-disconnected"` → `kwargs["app_icon"]=''` → `_app_icon_pb = None` (fila sin logo).
  - **Todos los nombres pelados auditados SÍ resuelven** por `_icon_from_theme` (10/10: 16×16 o 32×32) → el passthrough recupera un logo real para el 100% de ese 43.5%. Con el fix, el mismo caso da `_app_icon_pb = 16x16`.
  - **35.4% vacío** (ej. `xat-notifier`, que no manda icono) → esos caen al `.desktop` exacto / tema por `app_name`, luego al placeholder (task 5).
  - **12.5% `file://` URI** (Brave, favicon del tab en `/tmp`): solo **12 de 125 siguen existiendo** en disco — son efímeros y mueren con la sesión. Cuando existen, el path normalizado ya gana hoy y **no cambia** con el fix.
  - **8.6% path absoluto** (kitty → `/usr/lib/kitty/logo/kitty.png`): ya funciona; tampoco cambia.
  - Los mismos iconos pelados tampoco llegaban al avatar (línea 372 usa la misma normalización) — ahí el fallback documentado a `.desktop`/tema por `app_name` ya cubría el caso; el fix del logo de 16 px no altera esa vía.
  - `spectacle` y `kclock` resuelven a **32×32** desde el tema: no son cuadrados en general → motivates el `contain` de la task 4.
- [x] 3.2 Fix de passthrough en el daemon: `kwargs["app_icon"] = app_icon_file or app_icon` (path normalizado si existe; string crudo si no) — verificación: test nuevo con `app_icon` pelado resoluble en tema muestra logo en la fila; el test de `file://` existente sigue verde; replay del dashboard (que guarda el crudo) muestra el logo igual.

## 4. Iconos — render sin cortes (contain)

- [x] 4.1 Test del modo contain: icono 32×16 → slot 16×16 completo con bandas transparentes y sin perder extremos; icono cuadrado → llena el slot; avatares siguen en cover (regresión) — verificación: test en rojo contra `_resample` actual (center-crop).
- [x] 4.2 Implementar `mode="cover"|"contain"` en `_resample` (contain = escalar preservando aspect + compositar centrado sobre pixbuf transparente), hilarlo por `_get_app_icon_from_desktop` y usar contain solo en la cadena del logo de 16 px — verificación: 4.1 verde y `tests/test_icon_resolution.py` + metatests de HYPER verdes.

## 5. Iconos — placeholder del logo

- [x] 5.1 Test del placeholder: cadena que no resuelve (sin archivo, sin `.desktop` exacto, sin tema) → el widget tiene un pixbuf 16×16 de placeholder (no `None`) y la fila dibuja el texto con el offset `+20` constante, igual con logo resuelto o con placeholder — verificación: test en rojo contra el código actual (fila sin icono).
- [x] 5.2 Implementar la síntesis del placeholder (design D6: cuadrado redondeado `#313244` + inicial Manrope Bold ~9 px `#A6ADC8`, materializado en `__init__`) y cerrar la open question de la forma final con un screenshot — verificación: 5.1 verde y screenshot del placeholder renderizado.

  **Open question CERRADA** (`render_out/placeholder_logo.png`, 4 iniciales a 6× para inspección):
  - **Inicial** (no glifo neutro): "N" de Netflix es más informativo que un ícono genérico y no requiere asset nuevo.
  - **Radio**: `size // 4` = 4 px en el slot de 16, en línea con el radio de la barra "Ver más" (8 px sobre 28 de alto ≈ 2/7) y más cerrado que el card (12 px sobre 360). Se ve coherente con el resto del toast.
  - **Tipografía**: Manrope Bold a `round(size * 0.56)` ≈ 9 px; el centrado es por la **caja de tinta** (`(size-h)/2 - y_bearing`), no por la advance — verificado con iniciales de descendente ("Q", "J") y acentuada ("Í"): quedan centradas.
  - El square es **opaco** en el interior y transparente en las esquinas redondeadas, así se lee como superficie, no como hueco.

## 6. Integración, verificación viva y release

- [x] 6.1 Suite completa en verde: `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_uv_migration.py` — verificación: 0 failed (conteo ≥ 180 passed ajustado a los tests nuevos) y limpieza de `/tmp/pytest-of-fullmetal` antes y después (pitfall del tmpfs).
- [x] 6.2 Verificación en vivo con el daemon real: `systemctl --user restart verdantis.service` → hover en un persistente (texto re-wrappea a 288 y aparece la X), salir del card (X invisible, texto a 332), cerrar un toast vecino con el puntero quieto (sin X "pegada"), e iconos con senders reales incl. el placeholder — verificación: comportamiento observado sin oscilaciones de resize; si aparece oscilación, aplicar el fallback del design D2 (window congelada durante hover) antes de cerrar.

  **Verificación completa en vivo (KWin/Wayland, puntero real movido con `ydotool`+`kdotool`, X medida por píxeles en la franja x≥1300):**
  - ✅ daemon reiniciado, reporta `0.7.0`, sin errores en el journal.
  - ✅ iconos con senders reales (dataset de `history.jsonl`): nombre de tema pelado → logo del tema; vacío → placeholder con inicial; path absoluto → kitty; `file://` → path. Verificado con render de píxeles (`render_out/filas_app_iconos.png`) y con la cadena real `Notify→_local_path→widget`.
  - ✅ hover sí/no: sin hover → 0 px de X; hover → 91 px de X en x[1320..1336] y texto re-wrappeado (2→3 líneas); salir → 0 px de nuevo, 332 px, alto restaurado. Sin oscilación.
  - ✅ **reflow de la pila bajo puntero quieto: era un bug real (X pegada) y quedó corregido.** Con dos toasts (A arriba, B abajo), hover sobre B y cierre de A por DBus (sin mover el puntero):
    - ANTES (sin el fix): B subía por el reflow y la franja **seguía dibujada** (91 px de X) con el puntero fuera del card.
    - CAUSA: KWin/Wayland **no** entrega `leave-notify` cuando la surface se aparta de un puntero quieto — el `leave` llega al mover el puntero, no al mover la ventana.
    - FIX (dentro de D3, que autoriza el endurecimiento "con el repro en la mano"): `_apply_margins` calcula el delta vertical del margen y llama a `_card._sincronizar_hover_tras_desplazar(dy)`, que consulta la posición real con `Gdk.Window.get_device_position` y resetea/mantiene el hover. Contrato triestado: `(True,x,y)` dentro · `(False,0,0)` fuera (consultado) · `None` no consultable (no tocar estado, evita resets a ciegas). Cubre las dos direcciones del spec (nunca X visible sin puntero, nunca oculta teniéndolo).
    - AHORA: hover B → 91 px; tras cerrar A → **0 px**, franja perdida y alto sin hover. Sin oscilación.
    - `tests/test_reflow_hover.py` (8 tests) cubre el fix por ambos lados + guarda de API (`get_device_position` sobre la window, no `translate_coordinates`/`get_origin`, que devuelven 0,0 en layer-shell Wayland).
  - Nota de proceso: la primera versión del fix quedó muda en runtime (devolvía el fallback `None`) por usar `Gdk.Device.get_device_position`/translate inexistentes o no fiables bajo Wayland; el unit test no lo detectó porque monkeypatcheaba `_puntero_en_card`. Se corrigió validando la API contra un `WaylandPopup` real antes de re-verificar en vivo, y se añadió la guarda de API.
- [x] 6.3 Bump `VERSION` → 0.7.0 en `src/verdantis_daemon.py` dentro del commit `feat:` (en español, conventional) y verificar tras reiniciar con `busctl --user call org.freedesktop.Notifications /org/freedesktop/Notifications org.freedesktop.Notifications GetServerInformation` → "0.7.0" — verificación: output del busctl con la versión nueva y bump reportado al usuario.

  **Verificado**: `VERSION = "0.7.0"` (única fuente, línea 21 de `verdantis_daemon.py`) y `busctl --user call ... GetServerInformation` → `ssss "Verdantis" "MoriNo23" "0.7.0" "1.2"`. Bump MINOR (primer `feat:` del ciclo). Pendiente: crear el commit `feat:` — no se hace commit automático sin pedido explícito del usuario.
