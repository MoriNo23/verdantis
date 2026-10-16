<p align="center">
  <img src="assets/verdantis-logo.png" width="200" alt="Verdantis logo">
</p>

# Verdantis

Desktop notification daemon for **Wayland (KDE Plasma 6)**. It owns
`org.freedesktop.Notifications` on the session bus and draws its own toasts
with GTK3 + gtk-layer-shell (cairo/Pango) — no Plasma dependency. A
replacement for mako/deadd. The stack is a queue, not a parade:
notifications show in arrival order and nothing covers anything.

- **Strict FIFO stack** — max 2 toasts on screen, a queue of up to 20
  behind; `urgency` changes duration and style, never position.
- **Crisp text on any machine** — gray antialiasing pinned by code, not
  inherited from fontconfig (subpixel AA tints text over translucent
  surfaces).
- **Own look** — accent color, an 80 px image slot on every toast, a time
  wipe, and hover pauses expiry.
- **History + replay** — every notification is archived to disk and can be
  re-shown with the real render through the CLI (`list` / `replay` /
  `clear`).
- **Honest freedesktop.org 1.2 contract** — only capabilities that actually
  work are announced.

```
                     360 px
┌───────────────────────────────────────────────┐
│ ╭─────╮  [16px]  Brave - Tab title            │
│ │ IMG │  Toast title                          │
│ │ 80px│  Sanitized body, wrapped…             │
│ ╰─────╯  [ Reply ]    [ Archive ]             │
└───────────────────────────────────────────────┘
   │          │
   │          └─ app line + title + body ("See more") + actions
   └─ left image: ALWAYS present (80 px); notification image →
      exact .desktop icon → initial-letter placeholder

Time wipe: a full-height tint whose front sweeps right to left — the part
already swept (the right side) stays tinted. While the pointer is over the
toast, expiry pauses (on leave it resumes with the remaining time). Dismiss
strip + X on hover for ANY toast (persistent or timed).
```

## Requirements

- **KDE Plasma 6 on Wayland** — the tested daily driver. Other compositors
  with wlr-layer-shell support (Sway, Hyprland) should work; GNOME/Mutter is
  not supported (no layer-shell protocol).
- GTK3 3.24+, `libgtk-layer-shell` (dev package) and `python3-gi` from your
  distro — the venv uses the system GObject-introspection libraries.
- Python 3.13 with `venv` + pip, and a systemd user session.
- Debian/Ubuntu are the tested target (`install.sh` runs `apt`); on other
  distros, install the system packages above by hand.

## Install

```bash
./install.sh                                      # apt deps + .venv/
systemctl --user enable --now verdantis.service   # daemon as a user service
```

Only one process can own `org.freedesktop.Notifications`: stop any other
notification daemon (mako, deadd, …) so Verdantis can take the bus name.
Check the current owner with:

```bash
busctl --user list | grep Notifications
```

## Daemon (normal use)

Apps send notifications over DBus and Verdantis draws them:

```bash
systemctl --user status verdantis.service
busctl --user call org.freedesktop.Notifications \
  /org/freedesktop/Notifications org.freedesktop.Notifications GetServerInformation
# => ssss "Verdantis" "MoriNo23" "0.14.0" "1.2"
```

### Stack rules

- Max **2 toasts on screen**; the rest wait in line.
- The line is **FIFO by arrival**: no type (low/normal/critical) wins a slot
  or skips ahead — `urgency` only changes duration and style, never position.
- The line is **capped at 20**: in a flood the oldest entries are dropped,
  the newest always get in.
- **A toast is not created until there is a visual slot**: waiting entries
  are data — no window, no timer.
- The slot frees when a toast **expires** or the user **closes** it; the
  first in line enters at that moment.
- An incoming toast **never covers** an existing one: its first frame
  already sits in its slot (below the one above, with the 12 px gap).
- Text is rasterized with gray antialiasing pinned by code: crisp on any
  machine, without inheriting fontconfig subpixel rendering.

## History & replay (CLI)

Every notification (except `transient` ones) is archived to
`$XDG_DATA_HOME/verdantis/history.jsonl` — capped at 1000 records — with a
copy of the icon bytes (browser favicons live in `/tmp` and die with the
session). That history is what replay reproduces **in production**:

```bash
.venv/bin/python src/verdantis.py list --last 20        # table: id, date, app, summary
.venv/bin/python src/verdantis.py replay --last 5       # re-shows them, one by one
.venv/bin/python src/verdantis.py replay --id 42        # one specific record
.venv/bin/python src/verdantis.py replay --app brave    # filter by app (substring)
.venv/bin/python src/verdantis.py replay --last 10 --duration 3000   # override duration (ms)
.venv/bin/python src/verdantis.py clear --yes           # wipe history + icons (irreversible)
```

| Flag | Default | Description |
|---|---|---|
| `--last N` | `20` for `list`, `5` for `replay` | How many records, in arrival order (oldest first); `0` = no limit |
| `--app X` | | Case-insensitive substring filter on the app name |
| `--id N` | | The **most recent** record with that id (ids repeat: every daemon restart resets the counter); wins over `--last` |
| `--duration MS` | the archived value | Overrides duration (handy for persistent toasts, which carry `0`) |
| `--yes` | | Mandatory confirmation for `clear` |

Replay **does not go through the bus**: it uses the daemon's render (Wayland
layer-shell, or the X11 fallback with `--force-fallback`), it does not
re-archive, dedup does not filter it, and it works even when the daemon is
not the owner of `org.freedesktop.Notifications`. Since there is no sender,
a click opens the archived URL with `xdg-open` and does not emit
`ActionInvoked`; with no archived URL a click does nothing (default cursor,
nothing promised). Reproduced buttons do not fire: without a sender there is
no action to run.

## One-shot (no daemon)

```bash
.venv/bin/python src/verdantis.py --title "Hello" --body "World" --icon icon.png --image photo.jpg --corner top-right
```

| Flag | Default | Description |
|---|---|---|
| `--title` | `Notificación` | Title |
| `--body` | `""` | Body |
| `--icon` | `None` | Left image (80 px slot) |
| `--app-icon` | `None` | 16 px app logo in the app line |
| `--app-name` | `""` | App line (Brave, Telegram…) |
| `--image` | `None` | Big image (banner) |
| `--duration` | `6000` | Duration, ms (mirrors the daemon default) |
| `--margin` | `16` | Screen edge margin, px |
| `--corner` | `top-right` | `top-right`, `top-left`, `bottom-right`, `bottom-left` |
| `--accent` | `#80cbc4` | Accent color, hex (identity default, `app_info.DEFAULT_ACCENT`) |
| `--force-wayland` | | Force the GTK3 + layer-shell backend |
| `--force-fallback` | | Force the X11 fallback branch |
| `--daemon` | | Start as the DBus daemon |

## Backends

- **Wayland**: GTK3 + gtk-layer-shell (precise corner anchoring).
- **X11/fallback**: GTK3 (`Gtk.Window` positioned via `move()`); on Wayland
  without layer-shell the one-shot fails cleanly (stderr + non-zero exit),
  no fallback.

## Project structure

```text
src/
  verdantis.py         entry point: --daemon, CLI (list/replay/clear), one-shot
  verdantis_daemon.py  DBus name owner: Notify/CloseNotification/signals, queue
  wayland_popup.py     toast render: GTK3 + gtk-layer-shell, cairo/Pango
  x11_popup.py         X11 fallback (positionable window), reuses the widget
  replay.py            history CLI + the shared render branch
  history_store.py     JSONL store + icon byte copies (best-effort)
  app_info.py          single source of identity (name, id, vendor, accent)
tests/                 D-Bus contract, audit, history/replay + sensitivity metatests
mockups/               Next.js visual docs of the toast (may diverge)
```

## Mockups

`mockups/` is a Next.js app that documents the toast visually: variants,
geometry and tokens. It is documentation and **may diverge** — the source of
truth for behavior is `openspec/specs/` plus the code.

```bash
cd mockups
pnpm i
pnpm dev      # http://localhost:3000
```

Pages: `/` (variants), `/anatomia` (px dimensions), `/tokens` (palette and
metrics).

## Development

```bash
.venv/bin/python -m pytest tests/ -q     # D-Bus contract, audit, replay (+ metatests)
```

- Product map: `PRD.md`.
- Formal behavior truth: `openspec/specs/`.
- Dev conventions: `AGENTS.md`.

## Contributing

Issues are welcome. For bug reports please include your distro/compositor,
the server version (`busctl --user call ... GetServerInformation`) and the
steps to reproduce.

Pull requests: open an issue first — this is a single-author project and
review may take a while. Keep the test suite green and follow the
conventions in `AGENTS.md` (code, comments and commits are in Spanish).

## License

[MIT](LICENSE)
