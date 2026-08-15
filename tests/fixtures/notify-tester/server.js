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
import { buildFocusPlan } from "./focus.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 8766);
const GUI = join(__dirname, "index.html");

// nid -> titulo de la ventana a re-enfocar al recibir ActionInvoked (Paso 5 fix).
const pendingTitles = new Map();

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
          // gdbus Notify devuelve "(uint32 NID,)"; extraemos el nid para mapear
          // nid -> titulo de la ventana a re-enfocar al recibir ActionInvoked.
          const m = String(out).match(/uint32\s+(\d+)/);
          const nid = m ? Number(m[1]) : null;
          if (nid != null) {
            // El titulo de la ventana PWA suele ser el summary o appName.
            // Pero el re-enfoque robusto usa desktop_entry -> StartupWMClass.
            pendingTitles.set(nid, {
              title: payload.summary || payload.appName || "",
              desktopEntry: payload.desktopEntry || "",
            });
          }
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
// re-enfoca la ventana de Brave/PWA para validar el fix end-to-end (PWA re-enfoca
// en vez de abrir duplicada). Tambien loguea.
//
// En Wayland puro xdotool/wmctrl NO operan sobre ventanas. El re-enfoque usa
// kdotool (KWin), que ademas hace switch de desktop automatico si la ventana
// esta en otro desktop virtual. Fallback a xdotool si kdotool no existe.
import { spawn as _spawn, execFileSync } from "node:child_process";

// Detectar la herramienta de re-enfoque disponible (kdotool prioridad en Wayland).
function execFileSyncSafe(cmd) {
  try {
    execFileSync("which", [cmd], { stdio: "ignore" });
    return cmd;
  } catch {
    return null;
  }
}
function focusTool() {
  if (execFileSyncSafe("kdotool")) return "kdotool";
  if (execFileSyncSafe("xdotool")) return "xdotool";
  return null;
}

const FOCUS_TOOL = focusTool();
console.log(`[re-enfoque] herramienta: ${FOCUS_TOOL || "NINGUNA (solo log)"}`);

function focusWindowByMeta(meta) {
  if (!FOCUS_TOOL || !meta) return;
  const plan = buildFocusPlan(meta);
  for (const step of plan) {
    if (step.type === "class") {
      if (focusByClass(step.value)) return;
    } else {
      if (focusByTitle(step.value)) return;
    }
  }
}

function focusByClass(wmClass) {
  if (!wmClass) return false;
  try {
    const uuid = execFileSync(
      "kdotool", ["search", "--class", wmClass], { encoding: "utf8" },
    ).trim().split("\n")[0];
    if (uuid) {
      execFileSync("kdotool", ["windowactivate", uuid], { stdio: "ignore" });
      console.log(`[re-enfoque] clase '${wmClass}' -> ${uuid}`);
      return true;
    }
  } catch (e) {
    console.error(`[re-enfoque] clase '${wmClass}' fallo: ${e.message}`);
  }
  return false;
}

function focusByTitle(title) {
  if (!title) return false;
  if (FOCUS_TOOL === "kdotool") {
    try {
      const uuid = execFileSync("kdotool", ["search", title], { encoding: "utf8" }).trim().split("\n")[0];
      if (uuid) {
        execFileSync("kdotool", ["windowactivate", uuid], { stdio: "ignore" });
        console.log(`[re-enfoque] titulo '${title}' -> ${uuid}`);
        return true;
      }
    } catch (e) {
      console.error(`[re-enfoque] kdotool titulo '${title}' fallo: ${e.message}`);
    }
  } else if (FOCUS_TOOL === "xdotool") {
    try {
      execFileSync("xdotool", ["search", "--name", title, "windowactivate"], { stdio: "ignore" });
      console.log(`[re-enfoque] titulo '${title}' (xdotool)`);
      return true;
    } catch (e) {
      console.error(`[re-enfoque] xdotool titulo '${title}' fallo: ${e.message}`);
    }
  }
  return false;
}

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
      // Re-enfocar la ventana asociada a esta notificacion (PWA o navegador).
      // Usa desktop_entry -> StartupWMClass (clase) con fallback a titulo.
      const meta = pendingTitles.get(Number(nid));
      if (meta) {
        focusWindowByMeta(meta);
        pendingTitles.delete(Number(nid));
      }
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
