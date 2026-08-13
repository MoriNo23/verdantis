// Lógica pura para construir el comando gdbus que dispara una notificación real
// por el bus de sesión (org.freedesktop.Notifications). Separada del server para
// poder testearla sin DBus (unit tests + metatest de sensibilidad).
//
// Cubre TODOS los parámetros del método Notify (spec freedesktop 1.2) y los hints
// que el daemon de Verdantis realmente consume:
//   - "desktop-entry"      -> _is_pwa() / _is_browser() (decide xdg-open vs solo ActionInvoked)
//   - "url" / "x-kde-urls" -> URL que se abre con xdg-open (salvo PWA)
//   - "urgency" (byte)     -> nivel de urgencia del toast
//   - "image-path"         -> banner/avatar del toast
//   - "accent"             -> color de acento del toast
//   - "category"           -> categoría freedesktop
//   - "suppress-sound"     -> silencia el sonido (mapea Web API "silent")
// Mapeos Web API -> DBus que el tester expone:
//   silent           -> suppress-sound
//   requireInteraction -> expire_timeout = 0 (persistente)
//   tag              -> replaces_id
//   actions          -> actions[] DBus

/** Construye el dict de hints a{sv} a partir de campos simples del GUI. */
export function buildHints({
  desktopEntry = "",
  url = "",
  xKdeUrls = [],
  urgency = 1,
  imagePath = "",
  accent = "",
  category = "",
  suppressSound = false,
} = {}) {
  const hints = {};
  if (desktopEntry) hints["desktop-entry"] = desktopEntry;
  if (url) hints.url = url;
  if (Array.isArray(xKdeUrls) && xKdeUrls.length) hints["x-kde-urls"] = xKdeUrls;
  if (typeof urgency === "number") hints.urgency = urgency;
  if (imagePath) hints["image-path"] = imagePath;
  if (accent) hints.accent = accent;
  if (category) hints.category = category;
  if (suppressSound) hints["suppress-sound"] = true;
  return hints;
}

/**
 * Mapea actions del GUI a la lista freedesktop 1.2 (pares [key, label] aplanados).
 * Ej: [["default","Abrir"]] -> ["default", "Abrir"].
 */
export function buildActions(actionPairs = []) {
  const flat = [];
  for (const pair of actionPairs || []) {
    if (Array.isArray(pair) && pair.length >= 2) {
      flat.push(pair[0], pair[1]);
    }
  }
  return flat;
}

function variantLiteral(value) {
  if (typeof value === "number") return `<byte ${value}>`;
  if (typeof value === "boolean") return `<boolean ${value}>`;
  if (Array.isArray(value)) {
    const items = value.map((v) => `'${String(v).replace(/'/g, "\\'")}'`);
    return `<[${items.join(", ")}]>`;
  }
  return `<'${String(value).replace(/'/g, "\\'")}'>`;
}

/** Serializa un dict JS a literal GVariant a{sv} para gdbus. */
export function dictToGVariant(hints) {
  const entries = Object.entries(hints || {}).map(
    ([k, v]) => `'${k}': ${variantLiteral(v)}`
  );
  return `{${entries.join(", ")}}`;
}

/**
 * Devuelve el array de argumentos para spawn('gdbus', ...) que dispara Notify.
 * Es puro: no toca DBus. Los tests verifican su forma.
 */
export function buildNotifyArgs({
  appName = "",
  summary = "Prueba",
  body = "",
  actions = [],
  hints = {},
  timeout = 6000,
  replacesId = 0,
  appIcon = "",
} = {}) {
  return [
    "call", "--session",
    "--dest", "org.freedesktop.Notifications",
    "--object-path", "/org/freedesktop/Notifications",
    "--method", "org.freedesktop.Notifications.Notify",
    appName,
    String(replacesId),
    appIcon,
    summary,
    body,
    JSON.stringify(actions), // gdbus acepta "['default', 'Abrir']"
    dictToGVariant(hints),
    String(timeout),
  ];
}
