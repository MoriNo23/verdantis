// Server node: sirve el GUI web en http://localhost:8766/notify-tester.html
// y expone POST /notify que dispara una notificación REAL por DBus (gdbus) con
// TODOS los parámetros del Notify (spec freedesktop 1.2) + hints que Verdantis
// consume. Esto SÍ reproduce el bug del click en PWA (el HTML estático con la API
// Notification no podía mandar hints de DBus).
import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { spawn } from "node:child_process";
import {
  buildHints,
  buildActions,
  buildNotifyArgs,
} from "./notify.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 8766);
const GUI = join(__dirname, "index.html");

function send(res, code, obj) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(obj));
}

function toLines(str) {
  return String(str || "")
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && (req.url === "/" || req.url === "/notify-tester.html")) {
    try {
      const html = await readFile(GUI, "utf8");
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(html);
    } catch (e) {
      send(res, 500, { error: String(e) });
    }
    return;
  }

  if (req.method === "POST" && req.url === "/notify") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      let payload;
      try {
        payload = JSON.parse(body || "{}");
      } catch (e) {
        send(res, 400, { error: "JSON inválido" });
        return;
      }

      const hints = buildHints({
        desktopEntry: payload.desktopEntry || "",
        url: payload.url || "",
        xKdeUrls: toLines(payload.xKdeUrls),
        urgency: Number.isFinite(payload.urgency) ? payload.urgency : 1,
        imagePath: payload.imagePath || "",
        accent: payload.accent || "",
        category: payload.category || "",
        suppressSound: Boolean(payload.suppressSound),
      });
      const flatActions = buildActions(payload.actions);

      // requireInteraction (Web API) -> expire_timeout = 0 (persistente)
      const timeout = payload.requireInteraction ? 0 : (payload.timeout ?? 6000);

      const args = buildNotifyArgs({
        appName: payload.appName || "Verdantis Tester",
        summary: payload.summary || "Prueba",
        body: payload.body || "",
        actions: flatActions,
        hints,
        timeout,
        replacesId: Number(payload.replacesId || 0),
        appIcon: payload.appIcon || "",
      });

      const child = spawn("gdbus", args, { stdio: ["ignore", "pipe", "pipe"] });
      let out = "";
      let err = "";
      child.stdout.on("data", (d) => (out += d));
      child.stderr.on("data", (d) => (err += d));
      child.on("close", (code) => {
        if (code === 0) {
          send(res, 200, { ok: true, dbusId: out.trim() });
        } else {
          send(res, 502, { ok: false, code, error: err.trim() || out.trim() });
        }
      });
    });
    return;
  }

  send(res, 404, { error: "no encontrado" });
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.error(`Puerto ${PORT} ya en uso. ¿Ya corre un server? Usa el que está, o pkill -f 'node server.js'.`);
    process.exit(0);
  }
  throw err;
});

server.listen(PORT, () => {
  console.log(`Verdantis notify-tester en http://localhost:${PORT}/notify-tester.html`);
});

// ---- Paso 5 (plan fix-pwa-click-focus): escuchar ActionInvoked y re-enfocar Brave ----
// El emisor (gdbus) muere al salir, asi que nadie recibia la señal dirigida.
// Arrancamos un dbus-monitor persistente que parsea ActionInvoked del daemon y
// re-enfoca la ventana de Brave (xdotool/wmctrl, best-effort) para validar el
// fix end-to-end (PWA re-enfoca en vez de abrir duplicada). Tambien loguea.
import { spawn as _spawn } from "node:child_process";

const monitor = _spawn("dbus-monitor", [
  "type='signal',interface='org.freedesktop.Notifications',member='ActionInvoked'",
], { stdio: ["ignore", "pipe", "pipe"] });

let buf = "";
function handleLine(line) {
  // dbus-monitor emite bloques como:
  //   signal time=... -> destination=... path=...; interface=...; member=ActionInvoked
  //   uint32 NID
  //   string ":1.42"
  if (/member=ActionInvoked/.test(line)) {
    // reiniciar captura de bloque
    buf = "AI:" + line + "\n";
    return;
  }
  if (buf.startsWith("AI:")) {
    buf += line + "\n";
    const m = buf.match(/uint32\s+(\d+)[\s\S]*?string\s+"([^"]+)"/);
    if (m) {
      const nid = m[1];
      const key = m[2];
      console.log(`ActionInvoked recibido: nid=${nid} key=${key}`);
      // Re-enfocar la ventana de Brave (PWA o navegador) best-effort.
      _spawn("xdotool", ["search", "--class", "brave", "windowactivate"],
        { stdio: "ignore" });
      buf = "";
    }
  }
}

if (monitor.stdout) {
  monitor.stdout.setEncoding("utf8");
  monitor.stdout.on("data", (d) => {
    d.split("\n").forEach((l) => l.trim() && handleLine(l.trim()));
  });
}
if (monitor.stderr) {
  monitor.stderr.setEncoding("utf8");
  monitor.stderr.on("data", (d) => process.stderr.write(`[dbus-monitor] ${d}`));
}
monitor.on("exit", (code) => {
  if (code) console.error(`dbus-monitor salio (${code}). El re-enfoque no funcionara.`);
});
