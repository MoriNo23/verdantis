"""Flask dashboard for Verdantis — notification history + replay.

Runs in a background thread inside the daemon process so it can access
the NotificationManager's in-memory history directly (no IPC needed).

  GET  /                 → dashboard HTML
  GET  /api/history      → JSON list of recent notifications
  POST /api/replay/<id>  → re-emit a captured notification
  GET  /api/stats        → counts + uptime
"""

import json
import os
import threading
import time

from flask import Flask, jsonify, request, Response

import history_store

from app_info import APP_NAME

app = Flask(__name__)

# Set by NotificationDaemon when it starts the dashboard.
_daemon = None


def start_dashboard(daemon, host="127.0.0.1", port=8777):
    """Launch the dashboard in a background daemon thread."""
    global _daemon
    _daemon = daemon
    srv = threading.Thread(
        target=lambda: app.run(host, port, debug=False, use_reloader=False),
        daemon=True,
    )
    srv.start()
    return srv


def _history_records():
    """Registros de historial (más viejo primero): disco (persistido) con
    fallback a la memoria del manager (daemon recién arrancado)."""
    try:
        recs = history_store.read()
        if recs:
            return recs
    except Exception:
        pass
    if _daemon:
        return _daemon._manager.history
    return []


@app.route("/")
def index():
    return Response(_DASHBOARD_HTML, content_type="text/html; charset=utf-8")


@app.route("/api/history")
def api_history():
    # newest first
    return jsonify(list(reversed(_history_records())))


@app.route("/api/replay/<int:nid>", methods=["POST"])
def api_replay(nid):
    if not _daemon:
        return jsonify({"error": "daemon not wired"}), 500
    # buscar en disco primero (tiene avatar_file/banner_file guardados — claves
    # de persistencia, ver la excepción de terminología en history_store); si el
    # archivo de historial no existe, caer al historial en memoria.
    entries = _history_records()
    entry = next((e for e in entries if e["id"] == nid), None)
    if entry is None:
        return jsonify({"error": "id not found"}), 404
    hints = _deserialise_hints(entry.get("hints") or {})
    # Reproducir "tal cual": la imagen izquierda del sender se guardó como PNG en
    # el directorio propio (los favicons de /tmp son efímeros). Inyectarlo como
    # image-path; si no había imagen del sender, la reproducción vuelve a
    # resolver el fallback (desktop/tema) igual que la original.
    image_left_file = entry.get("avatar_file")
    if image_left_file:
        p = history_store.icon_path(image_left_file)
        if os.path.exists(p):
            hints["image-path"] = p
    _daemon._manager.notify(
        app_name=entry["app_name"],
        app_icon=entry["app_icon"],
        summary=entry["summary"],
        body=entry["body"],
        actions=entry["actions"],
        hints=hints,
        expire_timeout=entry["expire_timeout"],
        replaces_id=0,
        sender="dashboard-replay",
        replay=True,  # dibuja el card pero no emite señales al bus
    )
    return jsonify({"ok": True, "replayed": nid})


@app.route("/api/stats")
def api_stats():
    if not _daemon:
        return jsonify({"error": "daemon not wired"})
    hist = _history_records()
    apps = {}
    for h in hist:
        a = h["app_name"] or "(unknown)"
        apps[a] = apps.get(a, 0) + 1
    return jsonify({
        "total": len(hist),
        "active": len(_daemon._manager._active),
        "queued": len(_daemon._manager._pending),
        "by_app": apps,
    })


# Hints may contain bytes (image-data is raw RGB); we stored them as str.
# For replay we only need the scalar hints (urgency, desktop-entry, etc).
def _deserialise_hints(stored):
    out = {}
    for k, v in stored.items():
        if k in ("urgency",):
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                pass
        elif isinstance(v, str) and v in ("True", "False"):
            out[k] = (v == "True")
        elif isinstance(v, (int, float, bool, str)):
            out[k] = v
    return out


# ── Dashboard HTML (light theme, self-contained) ─────────────────────
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__APP_NAME__ Dashboard</title>
<style>
  :root {
    --bg: #f5f5f5;
    --card: #ffffff;
    --border: #e0e0e0;
    --text: #1a1a2e;
    --text-muted: #6c7086;
    --accent: #80cbc4;
    --accent-bg: rgba(128, 203, 196, 0.12);
    --accent-bg-hover: rgba(128, 203, 196, 0.22);
    --danger: #d20f2a;
    --danger-bg: rgba(210, 15, 42, 0.10);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Manrope', 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    min-height: 100vh;
  }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .subtitle { color: var(--text-muted); font-size: 13px; margin-bottom: 24px; }
  .stats-bar {
    display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap;
  }
  .stat {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 20px; min-width: 120px;
  }
  .stat .label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .stat .value { font-size: 24px; font-weight: 700; margin-top: 2px; }
  .notif-list { display: flex; flex-direction: column; gap: 10px; }
  .notif-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
    display: flex; align-items: flex-start; gap: 12px;
    transition: border-color 0.15s;
  }
  .notif-card:hover { border-color: var(--accent); }
  .notif-icon {
    width: 40px; height: 40px; border-radius: 8px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: 700; color: white;
  }
  .notif-body { flex: 1; min-width: 0; }
  .notif-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .notif-app { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .notif-time { font-size: 11px; color: var(--text-muted); }
  .notif-summary { font-size: 14px; font-weight: 700; margin-bottom: 2px; }
  .notif-text { font-size: 13px; color: #4c4f69; line-height: 1.5; word-break: break-word; }
  .replay-btn {
    background: var(--accent-bg); border: 1px solid var(--accent);
    border-radius: 8px; padding: 6px 14px; font-size: 12px; font-weight: 600;
    color: #1a8a80; cursor: pointer; flex-shrink: 0; align-self: center;
    transition: background 0.15s;
  }
  .replay-btn:hover { background: var(--accent-bg-hover); }
  .replay-btn:active { transform: scale(0.95); }
  .replay-btn.replayed { background: #e8e8e8; border-color: var(--border); color: var(--text-muted); }
  .empty { text-align: center; padding: 60px; color: var(--text-muted); font-size: 14px; }
  .urgent { border-left: 3px solid var(--danger); }
  .tooltip-hints { font-size: 10px; color: var(--text-muted); margin-top: 4px; font-family: monospace; }
</style>
</head>
<body>
  <h1>__APP_NAME__ Dashboard</h1>
  <div class="subtitle">Historial de notificaciones en tiempo real — click Replay para re-disparar</div>

  <div class="stats-bar" id="stats"></div>
  <div class="notif-list" id="list"></div>
  <div class="empty" id="empty" style="display:none">Sin notificaciones aún. Dispará una desde tu tester.</div>

<script>
const _appColors = {};
const _palette = ['#80cbc4','#f9e2af','#cba6f7','#f38ba8','#89b4fa','#a6e3a1','#fab387','#74c7ec'];
function colorFor(app) {
  if (!_appColors[app]) _appColors[app] = _palette[Object.keys(_appColors).length % _palette.length];
  return _appColors[app];
}
function initials(s) { return (s||'?')[0].toUpperCase(); }
function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('es', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

async function refresh() {
  try {
    const [histRes, statsRes] = await Promise.all([
      fetch('/api/history'), fetch('/api/stats')
    ]);
    const hist = await histRes.json();
    const stats = await statsRes.json();

    // stats
    let sh = `<div class="stat"><div class="label">Total</div><div class="value">${stats.total||0}</div></div>`;
    sh += `<div class="stat"><div class="label">Active</div><div class="value">${stats.active||0}</div></div>`;
    sh += `<div class="stat"><div class="label">Queued</div><div class="value">${stats.queued||0}</div></div>`;
    if (stats.by_app) {
      const top = Object.entries(stats.by_app).sort((a,b)=>b[1]-a[1]).slice(0,4);
      for (const [app, cnt] of top) {
        sh += `<div class="stat"><div class="label">${app}</div><div class="value">${cnt}</div></div>`;
      }
    }
    document.getElementById('stats').innerHTML = sh;

    // list
    const el = document.getElementById('list');
    const empty = document.getElementById('empty');
    if (!hist.length) { el.innerHTML=''; empty.style.display='block'; return; }
    empty.style.display='none';

    el.innerHTML = hist.map(n => {
      const urgent = (n.hints && n.hints.urgency == 2) ? 'urgent' : '';
      const hints = n.hints ? Object.entries(n.hints).filter(([k])=>k!=='image-data').slice(0,4).map(([k,v])=>`${k}=${v}`).join(', ') : '';
      return `<div class="notif-card ${urgent}">
        <div class="notif-icon" style="background:${colorFor(n.app_name)}">${initials(n.app_name)}</div>
        <div class="notif-body">
          <div class="notif-top">
            <span class="notif-app">${n.app_name||'(unknown)'}</span>
            <span class="notif-time">${fmtTime(n.timestamp)}</span>
          </div>
          <div class="notif-summary">${(n.summary||'').replace(/</g,'<')}</div>
          ${n.body ? `<div class="notif-text">${(n.body||'').replace(/</g,'<')}</div>` : ''}
          ${hints ? `<div class="tooltip-hints">${hints}</div>` : ''}
        </div>
        <button class="replay-btn" onclick="replay(${n.id}, this)">Replay</button>
      </div>`;
    }).join('');
  } catch(e) { console.error(e); }
}

async function replay(id, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const r = await fetch('/api/replay/' + id, { method: 'POST' });
    const data = await r.json();
    if (data.ok) { btn.textContent = '✓ Replay'; btn.classList.add('replayed'); }
    else { btn.textContent = 'Error'; }
  } catch(e) { btn.textContent = 'Error'; }
  setTimeout(() => { btn.disabled=false; btn.textContent='Replay'; btn.classList.remove('replayed'); }, 2000);
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""

# Interpolación del nombre single-source (el template usa CSS con llaves y
# porcentajes, así que no es f-string ni %-format: replace directo).
_DASHBOARD_HTML = _DASHBOARD_HTML.replace("__APP_NAME__", APP_NAME)
