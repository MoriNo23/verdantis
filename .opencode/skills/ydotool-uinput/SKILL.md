---
name: ydotool-uinput
description: Usar ydotool 1.0.4 (Debian trixie) para simular teclado y mouse via /dev/uinput en esta sesión Wayland/KWin Plasma 6. Usar cuando haya que mover el cursor, hacer click, scrollear o escribir en una app sin X11 (incluye pruebas manuales de toasts/interacciones de verdantis). Cubre cómo verificar la posición real del cursor y los bugs conocidos de `--absolute` y del parser de `mousemove`.
---

# ydotool 1.0.4 en KWin/Wayland

Todo lo de abajo está medido en esta máquina (Debian 13 trixie, Plasma 6 Wayland,
pantalla LVDS-1 1366x768 escala 1, usuario `fullmetal` uid 1000).

## Estado verificado (2026-10-02)

| Qué | Valor |
|---|---|
| Versión instalada | `ydotool 1.0.4-3` (Debian trixie) |
| Último release upstream | `v1.0.4` (2023-01-30) → **ya tenemos el último release** |
| Candidate de apt | `1.0.4-3` (sin updates; backports tiene `1.0.4-2~bpo13+1`, más viejo) |
| Daemon | `ydotoold` corriendo como unit de usuario `ydotool.service` (PID propio, `Restart=always`) |
| Socket | `/run/user/1000/.ydotool_socket` (srw-------, owner = usuario) |
| Permisos | `/dev/uinput` es `root:input 0660` y el usuario **ya está en el grupo `input`** → no hace falta `sudo` |
| Comandos | `click`, `mousemove`, `type`, `key`, `debug`, `bakers` — **NO existen** `getmouselocation` ni `stdin` (eso es master) |

Upstream master tiene ~20 commits sin release (último 2025-12-22): agrega el tool
`stdin`, arregla un **buffer overflow en `mousemove`** (commits `0ea32733`/`b4ea5074`)
y cambios en `click`. Ver "Actualizar a master" al final si alguna vez hace falta.

## Preflight (30 segundos)

```bash
systemctl --user is-active ydotool.service     # esperado: active
pgrep -a ydotoold                              # esperado: /usr/bin/ydotoold
ls -l "$XDG_RUNTIME_DIR/.ydotool_socket"       # el socket vive en XDG_RUNTIME_DIR
```

- Si `$XDG_RUNTIME_DIR` no está exportado (cron, `ssh` sin pam_systemd), el client
  cae a `/tmp/.ydotool_socket` y falla con
  `failed to connect socket '/tmp/.ydotool_socket'`. Fix: `export YDOTOOL_SOCKET=/run/user/1000/.ydotool_socket`.
- Daemon caído: `systemctl --user restart ydotool.service`.
- NoSupported/noPermiso en `/dev/uinput`: agregar el usuario al grupo `input`
  (requiere re-login) o correr el daemon como root.

## Uso (solo los 6 comandos de 1.0.4)

```bash
# Mouse — SIEMPRE relativo (ver pitfalls)
ydotool mousemove -- 120 0              # +120 px a la derecha
ydotool mousemove -- -100 -50           # arriba-izquierda
ydotool mousemove -w -- 0 -3            # scroll down 3 (wheel, siempre relativo)
ydotool click 0xC0                      # click izquierdo (down+up)
ydotool click 0xC1                      # click derecho
ydotool click -r 3 0xC0                 # triple click
ydotool click 0x40                       # left down (para drag: mover, después 0x80)
ydotool click 0x80                       # left up

# Teclado
ydotool type 'hola mundo'
ydotool type --delay 5 --next-delay 50 'texto'
ydotool type --file - < archivo.txt
ydotool key 29:1 28:1 28:0 29:0         # Ctrl+Enter (keycode:1 = down, :0 = up)
ydotool key --delay 5 105:1 105:0        # keycode 105 = KEY_LEFT
```

Flags reales de 1.0.4 (del binario, no del man page de master):
- `mousemove [-a|--absolute] [-w|--wheel] [-x X] [-y Y] [-- x y]`
- `key [-d|--key-delay ms] [code:1|code:0 ...]` (default 12 ms)
- `type [-d|--key-delay ms] [-D|--next-delay ms] [-f|--file path] "texto"`
- `click [-d|--next-delay ms] [-r|--repeat N] [boton_hex ...]`
  Botones: `0x00` LEFT, `0x01` RIGHT, `0x02` MIDDLE, `0x03` SIDE, `0x04` EXTRA,
  `0x05` FORWARD, `0x06` BACK, `0x07` TASK; máscaras `0x40` = down, `0x80` = up
  (click completo = `0xC0`).

## Verificar dónde está el cursor de verdad

```bash
kdotool getmouselocation            # x:835 y:499 screen:0 window:{uuid}
kdotool getmouselocation --shell    # x=835 y=499 screen=0 window=... (para eval)
```

**NUNCA verificar con `xdotool getmouselocation`**: bajo Wayland sólo ve el puntero
de Xwayland y devuelve posiciones viejas. Medido: `xdotool` dijo `835,499` mientras
el cursor real ya estaba en `678,538` (después de un `ydotool mousemove -- 200 0`).
`kdotool` (KWin, nativo) leyó `479,538 → 678,538`, que es el movimiento real.

`kdotool` v0.3.0 **no tiene** comando para mover el mouse (sólo `getmouselocation`),
así que el movimiento siempre es ydotool y en relativo.

## Receta: mover el cursor (con verificación, siempre)

```bash
# N píxeles a la derecha, con read-back y corrección de la deriva
pos() { kdotool getmouselocation | sed -n 's/^x:\([0-9-]*\) y:\([0-9-]*\).*/\1 \2/p'; }
read -r X Y <<< "$(pos)"
ydotool mousemove -- 120 0; sleep 0.3
read -r NX NY <<< "$(pos)"          # comprobá: esperabas X+120, Y
echo "delta real: $((NX-X)) $((NY-Y))"
```

Para "ir a un punto absoluto" (x,y) es el mismo bucle pero restando el delta:

```bash
ir_a() {  # ir_a 640 400
  read -r X Y <<< "$(pos)"
  ydotool mousemove -- $(( $1 - X )) $(( $2 - Y )); sleep 0.3
}
```

La deriva medida es de pocos píxeles (ver pitfalls), por eso el read-back en bucle
es parte de la receta y no opcional.

## Pitfalls (todos medidos en esta máquina)

1. **`--absolute` está roto con KWin 6 — no lo uses.** Upstream emula el absoluto
   enviando `REL_X=INT32_MIN, REL_Y=INT32_MIN` y después el delta. KWin interpreta
   ese valor mágico como salto al origen: el cursor queda **clavado en (1,1)**.
   Medido: `ydotool mousemove --absolute 200 1000` → cursor en `x:1 y:1`, y después
   `--absolute 1900 50` tampoco hace nada, tampoco los relativos **negativos**
   (no puede salir del borde). Desenclavar: `ydotool mousemove -- 400 300`
   (relativos positivos). Solución: `ir_a()` de arriba.
2. **Nunca pasar más de 2 números a `mousemove`.** En 1.0.4 el parser escribe en
   `int32_t pos[2]` sin bounds check: `ydotool mousemove -- 1 2 3 4` desborda el
   stack (arreglado en master en dic-2025). Máximo 2, y no mezclar `-x/-y` con
   posicionales de más (`-x` + `-y` + 1 posicional = 3 escrituras).
3. **Los relativos no son exactamente 1:1.** La mayoría son exactos (`-100,-50` →
   exactamente eso; `+60,0` → exacto), pero algunos eventos se desvían ±3..7 px
   (medido: pedir `-7 -3` terminó en `-0 +3` de error; un `+400 +300` desde (1,1)
   terminó en `432,324`). Consecuencia: **siempre verificar con `kdotool`**, nunca
   asumir. El primer evento después de un evento raro es el que más desvía.
4. **Los bounds son 1..(ancho-1)**: pedir fuera de 1366x768 se clampea al borde, y
   el error no es visible en el comando (exit 0).
5. **`ydotool` no tiene `--version`** (`Unknown command: --version`). Para la versión
   del daemon: `ydotoald -V` (imprime `unknown` en el build de Debian, sirve como
   smoke test de que el binario corre). La versión real del paquete:
   `dpkg -l ydotool`.
6. **Los keycodes son del kernel (`linux/input-event-codes.h`), no de X11.**
   `TAB=15` (en X es 23), `ENTER=28`, `LEFT=105`, `UP=103`. Si copiás un keycode de
   un tutorial de xdotool/X11 va a fallar o hacer otra cosa.

## Keycodes que se usan siempre (kernel, de `/usr/include/linux/input-event-codes.h`)

```
ESC 1        Q 16   W 17   E 18   R 19   T 20   Y 21   U 22   I 23   O 24   P 25
ENTER 28     CTRL 29  SHIFT 42/54   ALT 56/100    SPACE 57   TAB 15   BACKSPACE 14
DELETE 111   HOME 102  END 107  PAGEUP 104  PAGEDOWN 109
UP 103  DOWN 108  LEFT 105  RIGHT 106
F1 59  F2 60  F3 61  F11 87  F12 88      CAPSLOCK 58  SCROLLLOCK 70  PAUSE 119
```

Para descubrir otros: `grep KEY_ /usr/include/linux/input-event-codes.h` o
`sudo libinput record` y ver el nombre que reporta libinput.

## Diagnóstico rápido

```bash
systemctl --user status ydotool.service      # daemon vivo
ydotool debug                               # imprime fd del socket + argv parseado
grep -A3 -i ydotool /proc/bus/input/devices # el device virtual existe (handlers mouseX eventY)
ls -l /dev/uinput                           # root:input 0660
```

Si `ydotool` no hace nada pero no报错: el device virtual puede haber quedado sin
reconocer tras un suspend/resume → `systemctl --user restart ydotool.service`
(recrea `/dev/uinput` y el socket).

## Actualizar a master (opcional, no recomendado por defecto)

No hay update empaquetado (ya estamos en el último release). Sólo para bajar los
fixes sin release:

```bash
git clone https://github.com/ReimuNotMoe/ydotool /tmp/opencode/ydotool
cd /tmp/opencode/ydotool && git log --oneline -1   # revisar el commit
cmake -B build -DCMAKE_BUILD_TYPE=Release .        # requiere cmake >= 3.22
make -C build -j"$(nproc)"
sudo install -m755 build/ydotool /usr/local/bin/ydotool   # sólo el client
sudo install -m755 build/ydotoold /usr/local/bin/ydotoald  # opcional, cambia el unit
systemctl --user restart ydotool.service
```

Trae: fix del buffer overflow de `mousemove`, tool `stdin` (teclear desde ssh),
cambios en `click`. Perder: si instalás el `ydotoold` de master hay que regenerar el
unit (`ExecStart=/usr/local/bin/ydotoold`), el de Debian apunta a `/usr/bin/ydotoold`.
