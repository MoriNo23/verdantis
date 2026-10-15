#!/usr/bin/env python3
"""QA helper: simula en la TERMINAL cómo van llegando y apilándose las toasts.

Corre el `NotificationManager` real (`src/verdantis_daemon.py`) con reloj virtual y
sin ventanas: imprime un frame por evento con las toasts que están en pantalla (su
offset y alto reales, de `_stack_offsets()`) y las que esperan en la cola. Sirve
para cazar bugs de la pila en texto, sin depender de mirar el escritorio.

Fiel al daemon en lo que importa:
  - `_show_popup` REAL: el hueco se reserva antes de mapear y cada toast lleva el
    holdback de cierre por posición (CLOSE_STAGGER_MS) — el frame lo muestra.
  - vencimiento: el mismo camino que el timer (`popup._close()` → `on_close` →
    `_on_closed`), con el `duration` real de cada toast.
  - cierre por click: `_close_id`, el mismo que usan la X y CloseNotification.

Regla que se verifica sola: la toast NO se crea hasta que hay hueco visual (máx.
MAX_VISIBLE en pantalla); las que esperan son datos, sin popup ni timer.

Uso:
    .venv/bin/python tests/qa_sim_pila.py                 # 10 de golpe, timeout 6s
    .venv/bin/python tests/qa_sim_pila.py --n 20 --timeout 4
    .venv/bin/python tests/qa_sim_pila.py --click 3       # un click del usuario en t+3s
    .venv/bin/python tests/qa_sim_pila.py --sticky        # persistentes (no vencen)

Sale con 1 si detectó algún bug (sirve como chequeo, no solo como vista).
"""
import argparse
import os
import sys

# Igual que tests/conftest.py: nunca mapear ventanas reales en la sesión del usuario.
os.environ["GDK_BACKEND"] = "offscreen"
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

import wayland_popup as wp  # noqa: E402  (primero: fija Gdk 3.0)
import verdantis_daemon as vd  # noqa: E402

# Sin ventana: el sim no llama a prepare(). `stack_height()` cae en el mismo
# cálculo del daemon (calc_card_height) y no se dibuja nada en el escritorio.
wp.WaylandPopup.prepare = lambda self: None


class Reloj:
    """Reloj virtual: el scheduler del daemon apunta acá (no pasa tiempo real)."""

    def __init__(self):
        self.ms = 0
        self._eventos = []
        self._seq = 0

    def schedule(self, ms, cb):
        """Firma del scheduler del daemon: (ms, callback) -> id."""
        self._seq += 1
        self._eventos.append((self.ms + ms, self._seq, cb))
        return self._seq

    def correr_hasta(self, limite_ms):
        """Ejecuta los eventos en orden hasta `limite_ms` (los callbacks pueden
        agendar nuevos: se re-evalúa la cola)."""
        while True:
            pendientes = sorted(e for e in self._eventos if e[0] <= limite_ms)
            if not pendientes:
                break
            t, _, cb = pendientes[0]
            self._eventos.remove((t, _, cb))
            self.ms = t
            cb()
        self.ms = limite_ms


def _seg(ms):
    return "t+{:5.2f}s".format(ms / 1000.0)


def main():
    ap = argparse.ArgumentParser(description="Simulador de la pila de toasts")
    ap.add_argument("--n", type=int, default=10, help="cuántas llegan de golpe")
    ap.add_argument("--timeout", type=float, default=6.0,
                    help="expire_timeout en segundos (el del server es 6)")
    ap.add_argument("--sticky", action="store_true",
                    help="persistentes (expire_timeout=0: no vencen solas)")
    ap.add_argument("--click", type=float, default=None,
                    help="segundo virtual en que el usuario cierra la de arriba")
    args = ap.parse_args()

    reloj = Reloj()
    mgr = vd.NotificationManager(corner="top-right", scheduler=reloj.schedule)
    tope = vd.NotificationManager.MAX_VISIBLE

    creadas = []          # (nid, popup) en orden de creación
    nacimiento = {}       # nid -> ms virtual en que se creó (para el "vence")
    cerradas = set()
    bugs = []
    max_visto = 0

    # El vencimiento real lo dispara el timer del popup (`prepare()` +
    # `GLib.timeout_add`); acá no hay ventana, así que se agenda el MISMO camino
    # (`popup._close()` → on_close → _on_closed) con el `duration` real.
    real_show = mgr._show_popup

    def show_con_vencimiento(nid, kwargs):
        real_show(nid, kwargs)
        popup = mgr._active[-1][1]
        creadas.append((nid, popup))
        nacimiento[nid] = reloj.ms
        if popup.duration > 0:
            reloj.schedule(int(popup.duration), lambda p=popup: p._close())

    mgr._show_popup = show_con_vencimiento

    def mirar(evento):
        """Chequeos por evento + imprime el frame."""
        nonlocal max_visto
        max_visto = max(max_visto, len(mgr._active))
        offsets = mgr._stack_offsets()
        # BUG 1: más toasts en pantalla que el tope visual.
        if len(mgr._active) > tope:
            bugs.append("{}: {} en pantalla (tope {})".format(evento, len(mgr._active), tope))
        # BUG 2: solape (el gap de 12px entre cards).
        for i in range(1, len(mgr._active)):
            fin_arriba = offsets[i - 1] + mgr._active[i - 1][1].stack_height() + mgr.STACK_GAP
            if offsets[i] < fin_arriba - 0.5:
                bugs.append("{}: solape entre {} y {}".format(evento, i, i + 1))
        # BUG 3: fantasma (cerrada pero sigue ocupando un hueco).
        for nid, p in mgr._active:
            if getattr(p, "_closed", False):
                bugs.append("{}: fantasma #{} cerrada pero en pantalla".format(evento, nid))
        # BUG 4: creada y ni en pantalla ni cerrada (se perdió un toast).
        activas = [nid for nid, _ in mgr._active]
        for nid, p in creadas:
            if nid not in activas and nid not in cerradas and not getattr(p, "_closed", False):
                bugs.append("{}: popup #{} creada sin hueco (huérfana)".format(evento, nid))

        print("[{}] {:<28} en pantalla: {} de {}  |  esperando: {}".format(
            _seg(reloj.ms), evento, len(mgr._active), tope, len(mgr._pending)))
        for i, (nid, p) in enumerate(mgr._active):
            print("        #{:<3} y={:4.0f}px  h={:3.0f}px  {:<14} {}".format(
                nid, offsets[i], p.stack_height(),
                "no vence" if p.duration == 0
                else "vence {}".format(_seg(nacimiento[nid] + p.duration)),
                p.titulo[:34]))
        if mgr._pending:
            print("        cola ({}): {}".format(
                len(mgr._pending),
                " → ".join((q[1]["titulo"][:24] for q in mgr._pending[:6])))
                + (" → …" if len(mgr._pending) > 6 else ""))

    # 1) LLEGADAS: el burst entra a la cola (notify() NO crea la toast).
    for i in range(args.n):
        reloj.schedule(0, lambda i=i: mgr.notify(
            app_name="sim", summary="Noti {}".format(i + 1),
            body="Cuerpo distinto de la notificacion numero {} para el sim".format(i + 1),
            expire_timeout=(0 if args.sticky else int(args.timeout * 1000)),
        ))
    reloj.correr_hasta(0)                     # llegan todas de golpe
    mirar("llegan {} de golpe".format(args.n))

    # 2) VENCE el primero (a partir de acá el reloj avanza y la cola drena).
    if args.click is not None:
        reloj.schedule(int(args.click * 1000), lambda: mgr._close_id(
            mgr._active[0][0] if mgr._active else 0))
    limite = int(max(args.timeout, 0.0) * 1000 * (args.n + 2)) + 60000

    while reloj._eventos and reloj.ms <= limite:
        # Avanza al próximo evento y muestra el frame de lo que pasó.
        proximos = sorted(t for t, _, _ in reloj._eventos)
        antes = (len(creadas), len(cerradas), len(mgr._pending), len(mgr._active))
        reloj.correr_hasta(proximos[0])
        for nid, p in creadas:
            if getattr(p, "_closed", False):
                cerradas.add(nid)
        despues = (len(creadas), len(cerradas), len(mgr._pending), len(mgr._active))
        if despues != antes:
            if despues[0] > antes[0] and len(mgr._active) > 0 and len(mgr._active) <= tope:
                mirar("entra #{} ({})".format(creadas[-1][0], creadas[-1][1].titulo[:20]))
            else:
                mirar("se libera hueco (venció o click)")

    mirar("estado final")
    print("\n=== resumen ===")
    orden = [nid for nid, _ in creadas]
    print("  llegaron          : {}".format(args.n))
    print("  creadas/mostradas : {} (sin popup de más)".format(len(creadas)))
    print("  máx. en pantalla  : {} (tope {})".format(max_visto, tope))
    print("  orden de creación : {}".format(
        "FIFO por llegada OK" if orden == sorted(orden) else "DESORDENADO {}".format(orden)))
    print("  cola final        : {}".format(len(mgr._pending)))
    if bugs:
        print("  BUGS:")
        for b in dict.fromkeys(bugs):
            print("    - {}".format(b))
        return 1
    print("  detectores        : 0 bugs (ni tercero, ni solape, ni fantasma, ni huérfana)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
