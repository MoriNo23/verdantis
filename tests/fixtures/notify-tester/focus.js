// Lógica pura de resolución de objetivo de re-enfoque para el tester de Verdantis.
// Separada de server.js para poder testearla sin DBus ni kdotool.
//
// En KDE Plasma 6 Wayland, kdotool NO puede focusear por título de forma fiable
// cuando el titulo del toast (summary) no coincide con el titulo real de la
// ventana del navegador (ej el summary es "Nueva idea para ti" pero la ventana
// de Brave PWA se titula "Pinterest"). La forma robusta es resolver el
// desktop_entry -> StartupWMClass del .desktop -> kdotool search --class.
//
// Orden de preferencia para re-enfocar:
//   1. clase WM derivada del desktop_entry (PWA/app nativa con StartupWMClass)
//   2. nombre base del desktop_entry (fallback si no hay StartupWMClass)
//   3. titulo (summary/app_name) — frágil, solo si no hay desktop_entry

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const APP_DIRS = [
  join(homedir(), ".local/share/applications"),
  "/usr/local/share/applications",
  "/usr/share/applications",
];

/** Lee el valor de StartupWMClass de un .desktop (o null si no existe). */
export function readStartupWMClass(desktopEntry, dirs = APP_DIRS) {
  const name = desktopEntry.endsWith(".desktop") ? desktopEntry : desktopEntry + ".desktop";
  for (const dir of dirs) {
    const path = join(dir, name);
    if (!existsSync(path)) continue;
    try {
      const text = readFileSync(path, "utf8");
      const m = text.match(/^\s*StartupWMClass\s*=\s*(.+)$/m);
      if (m) return m[1].trim();
    } catch {
      // ignora archivos ilegibles
    }
  }
  return null;
}

/** Nombre base del desktop_entry sin extensión ni ruta. */
export function desktopEntryBase(desktopEntry) {
  return desktopEntry.split("/").pop().replace(/\.desktop$/, "");
}

/**
 * Devuelve el plan de re-enfoque ordenado por confiabilidad:
 *   [{type:'class', value}, {type:'title', value}]
 * `title` puede ser null (entonces solo se intenta por clase).
 */
export function buildFocusPlan({ desktopEntry = "", title = "" } = {}, dirs = APP_DIRS) {
  const plan = [];
  if (desktopEntry) {
    const wmClass = readStartupWMClass(desktopEntry, dirs);
    if (wmClass) {
      plan.push({ type: "class", value: wmClass });
    } else {
      // fallback: el nombre base suele coincidir con el WM class de la app
      plan.push({ type: "class", value: desktopEntryBase(desktopEntry) });
    }
  }
  if (title) {
    plan.push({ type: "title", value: title });
  }
  return plan;
}
