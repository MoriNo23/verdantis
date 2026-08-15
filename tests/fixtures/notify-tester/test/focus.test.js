// Tests de la lógica de resolución de re-enfoque (focus.js).
// No toca kdotool ni DBus: valida el plan de búsqueda por clase/título.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  readStartupWMClass,
  desktopEntryBase,
  buildFocusPlan,
} from "../focus.js";

function fakeAppsDir(files) {
  const dir = mkdtempSync(join(tmpdir(), "verd-"));
  for (const [name, content] of Object.entries(files)) {
    writeFileSync(join(dir, name), content);
  }
  return [dir];
}

test("readStartupWMClass lee el valor del .desktop", () => {
  const dirs = fakeAppsDir({
    "brave-abc123-Default.desktop":
      "[Desktop Entry]\nName=Pinterest\nStartupWMClass=brave-abc123\n",
  });
  assert.equal(readStartupWMClass("brave-abc123-Default", dirs), "brave-abc123");
  // acepta con o sin .desktop
  assert.equal(readStartupWMClass("brave-abc123-Default.desktop", dirs), "brave-abc123");
});

test("readStartupWMClass devuelve null si no existe", () => {
  assert.equal(readStartupWMClass("noexiste", [tmpdir()]), null);
});

test("desktopEntryBase quita ruta y extension", () => {
  assert.equal(desktopEntryBase("/usr/share/foo.desktop"), "foo");
  assert.equal(desktopEntryBase("bar"), "bar");
});

test("buildFocusPlan: PWA con StartupWMClass -> clase primero", () => {
  const dirs = fakeAppsDir({
    "brave-abc123-Default.desktop":
      "[Desktop Entry]\nStartupWMClass=brave-abc123\n",
  });
  const plan = buildFocusPlan(
    { desktopEntry: "brave-abc123-Default", title: "Nueva idea" },
    dirs,
  );
  assert.deepEqual(plan, [
    { type: "class", value: "brave-abc123" },
    { type: "title", value: "Nueva idea" },
  ]);
});

test("buildFocusPlan: desktop_entry sin StartupWMClass -> nombre base como clase", () => {
  const dirs = fakeAppsDir({ "firefox.desktop": "[Desktop Entry]\nName=Firefox\n" });
  const plan = buildFocusPlan({ desktopEntry: "firefox", title: "" }, dirs);
  assert.deepEqual(plan, [{ type: "class", value: "firefox" }]);
});

test("buildFocusPlan: sin desktop_entry -> solo titulo", () => {
  const plan = buildFocusPlan({ desktopEntry: "", title: "Slack" });
  assert.deepEqual(plan, [{ type: "title", value: "Slack" }]);
});

test("buildFocusPlan: clase tiene prioridad sobre titulo (orden)", () => {
  const dirs = fakeAppsDir({
    "app.desktop": "[Desktop Entry]\nStartupWMClass=app-wm\n",
  });
  const plan = buildFocusPlan({ desktopEntry: "app", title: "X" }, dirs);
  assert.equal(plan[0].type, "class");
  assert.equal(plan[0].value, "app-wm");
  assert.equal(plan[1].type, "title");
});
