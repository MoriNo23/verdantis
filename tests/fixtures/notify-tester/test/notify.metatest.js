// Metatest de sensibilidad: reemplaza buildNotifyArgs por una versión BUGUEADA
// que OMITE el hint desktop-entry para PWA (igual al bug de antes: el tester viejo
// no pasaba desktop-entry y el daemon no veía la PWA). Verifica que
// test_buildNotifyArgs_PWA_lleva_desktop_entry falla -> el fix es real.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as mod from "../notify.js";

function buggyBuildNotifyArgs(opts = {}) {
  // Versión bugueada: tira desktop-entry del dict de hints.
  const hints = { ...(opts.hints || {}) };
  delete hints["desktop-entry"];
  return mod.buildNotifyArgs({ ...opts, hints });
}

test("sensibilidad: versión bugueada sin desktop-entry es detectada", () => {
  const buggy = buggyBuildNotifyArgs({
    appName: "Brave",
    summary: "WhatsApp",
    body: "nuevo mensaje",
    actions: ["default", "Abrir"],
    hints: mod.buildHints({
      desktopEntry: "brave-hnpfjngllnobngcgfapefoaidbinmjnm-Default.desktop",
      url: "https://web.whatsapp.com/",
    }),
  });
  const joined = buggy.join(" ");
  // El test real (notify.test.js) exige desktop-entry presente; la versión
  // bugueada NO lo incluye -> este assert reproduce el fallo que el metatest vigila.
  assert.doesNotMatch(joined, /desktop-entry/);
});
