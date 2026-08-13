// Unit tests de la lógica pura de construcción de la notificación DBus.
// No tocan DBus: validan la forma del comando gdbus que el backend spawnnea.
// Cubre TODOS los parámetros del Notify + hints que Verdantis consume.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildHints,
  buildActions,
  dictToGVariant,
  buildNotifyArgs,
} from "../notify.js";

test("buildHints incluye desktop-entry y url", () => {
  const h = buildHints({ desktopEntry: "brave-foo.desktop", url: "https://x.com", urgency: 2 });
  assert.equal(h["desktop-entry"], "brave-foo.desktop");
  assert.equal(h.url, "https://x.com");
  assert.equal(h.urgency, 2);
});

test("buildHints vacío solo incluye urgency por defecto", () => {
  assert.deepEqual(buildHints({}), { urgency: 1 });
});

test("buildHints incluye hints extra (image-path/accent/category/x-kde-urls)", () => {
  const h = buildHints({
    imagePath: "/tmp/x.png", accent: "#ff0000", category: "im.received",
    xKdeUrls: ["https://a.com", "https://b.com"], suppressSound: true,
  });
  assert.equal(h["image-path"], "/tmp/x.png");
  assert.equal(h.accent, "#ff0000");
  assert.equal(h.category, "im.received");
  assert.deepEqual(h["x-kde-urls"], ["https://a.com", "https://b.com"]);
  assert.equal(h["suppress-sound"], true);
});

test("buildActions aplana pares [key,label]", () => {
  assert.deepEqual(buildActions([["default", "Abrir"], ["reply", "Responder"]]),
    ["default", "Abrir", "reply", "Responder"]);
});

test("buildActions ignora pares incompletos", () => {
  assert.deepEqual(buildActions([["default", "Abrir"], ["roto"]]), ["default", "Abrir"]);
});

test("buildActions vacío -> []", () => {
  assert.deepEqual(buildActions([]), []);
});

test("dictToGVariant serializa a{sv} con byte/boolean/list", () => {
  const gv = dictToGVariant({
    urgency: 1, "suppress-sound": true,
    "x-kde-urls": ["https://a.com"], "desktop-entry": "firefox.desktop",
  });
  assert.equal(
    gv,
    "{'urgency': <byte 1>, 'suppress-sound': <boolean true>, 'x-kde-urls': <['https://a.com']>, 'desktop-entry': <'firefox.desktop'>}"
  );
});

test("buildNotifyArgs destino DBus correcto", () => {
  const args = buildNotifyArgs({
    appName: "Brave", summary: "Hola", body: "mundo",
    actions: ["default", "Abrir"],
    hints: { "desktop-entry": "brave-foo.desktop", url: "https://x.com", urgency: 1 },
  });
  assert.equal(args[0], "call");
  assert.equal(args[1], "--session");
  assert.deepEqual(args.slice(2, 6), [
    "--dest", "org.freedesktop.Notifications",
    "--object-path", "/org/freedesktop/Notifications",
  ]);
  assert.equal(args[6], "--method");
  assert.equal(args[7], "org.freedesktop.Notifications.Notify");
});

test("buildNotifyArgs PWA lleva desktop-entry (reproduce bug click)", () => {
  const args = buildNotifyArgs({
    appName: "Brave", summary: "WhatsApp", body: "nuevo mensaje",
    actions: ["default", "Abrir"],
    hints: buildHints({
      desktopEntry: "brave-hnpfjngllnobngcgfapefoaidbinmjnm-Default.desktop",
      url: "https://web.whatsapp.com/",
    }),
  });
  const joined = args.join(" ");
  assert.match(joined, /desktop-entry/);
  assert.match(joined, /brave-hnpfjngllnobngcgfapefoaidbinmjnm-Default\.desktop/);
  assert.match(joined, /url/);
});

test("buildNotifyArgs pasa replaces_id y app_icon", () => {
  const args = buildNotifyArgs({
    appName: "X", summary: "s", body: "b", replacesId: 42, appIcon: "firefox",
  });
  assert.equal(args[9], "42");   // replaces_id (posición del spec Notify)
  assert.equal(args[10], "firefox"); // app_icon
});

test("buildNotifyArgs requireInteraction -> expire_timeout=0 (vía server)", () => {
  // El server traduce requireInteraction a timeout=0 antes de llamar buildNotifyArgs;
  // verificamos que buildNotifyArgs respeta timeout=0.
  const args = buildNotifyArgs({ summary: "s", timeout: 0 });
  assert.equal(args[args.length - 1], "0");
});
