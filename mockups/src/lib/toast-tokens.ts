/**
 * Tokens del toast de Verdantis — fuente única del mockup.
 *
 * Cada valor sale del render real (`src/wayland_popup.py` del daemon) y el
 * comentario nombra la constante original para trazabilidad manual. Este
 * archivo NO se deriva automáticamente: los mockups son documentación visual
 * y PUEDEN divergir — la verdad del comportamiento son los specs de main
 * (openspec/specs/) y el código.
 */

// ── Colores (wayland_popup: _hex_rgb / literales del _draw) ────────────────
export const COLORS = {
  cardBg: "#1e1e2e",        // _card_bg
  title: "#e6e9f2",         // _left_title
  body: "#cdd6f4",          // _left_body
  app: "#a6adc8",           // _left_app
  accent: "#80cbc4",        // accent default del daemon (hints "accent")
  xStroke: "#f38ba8",       // color de la X en la franja de descarte
  franjaTint: "rgba(219, 38, 38, 0.18)",   // tinte franja hover (hover_close: 0.32)
  franjaTintHover: "rgba(219, 38, 38, 0.32)",
  placeholderBg: "#313244", // _PLACEHOLDER_BG (icono de app sin resolución)
  placeholderFg: "#a6adc8", // _PLACEHOLDER_FG
  wipe: "rgba(128, 203, 196, 0.18)",        // tinte del wipe de tiempo
  wipeTitle: "#d4edd4",    // _right_title (texto bajo el wipe)
  pageBg: "#11111b",        // fondo de la página de mockups (Catppuccin base)
} as const;

// ── Medidas (wayland_popup: constantes de módulo) ──────────────────────────
export const METRICS = {
  cardW: 360,      // _CARD_WIDTH
  pad: 14,         // _PAD
  imageLeftW: 80,  // _IMAGE_LEFT_W (slot izquierdo, clip circular)
  imageLeftGap: 12,// _IMAGE_LEFT_GAP
  textColW: 240,   // _TEXT_COL_W (360 − 14 − 80 − 12 − 14)
  closeStripW: 44, // _CLOSE_STRIP_W (franja de descarte, solo hover persistente)
  btnH: 28,        // _BTN_H (barra "Ver más")
  btnGap: 8,       // _BTN_GAP
  actionsRowH: 28, // _ACTIONS_ROW_H (fila de botones de acción)
  actionsGap: 8,   // _ACTIONS_GAP
  cardRadius: 12,  // _CARD_RADIUS
  barRadius: 8,    // radio de la barra "Ver más" y los botones
  appIcon: 16,     // _APP_ICON_BOX (logo de la fila de app)
  appRowH: 20,     // _APP_ROW_H
  titleRowH: 22,   // _TITLE_ROW_H
  xStrokeW: 2.5,   // stroke de la X (spec toast-franja-descarte)
  maxLines: 3,     // _MAX_VISIBLE_LINES (cap del body colapsado)
} as const;

// ── Tipografía (wayland_popup: _APP_FONT/_TITLE_FONT/_BODY_FONT) ───────────
export const FONTS = {
  app: { family: "Manrope", size: 10 },
  title: { family: "Manrope", size: 11, weight: 700 },
  body: { family: "Manrope", size: 11 },
  barLabel: { family: "Manrope", size: 11 },   // "Ver más" / botones
} as const;

// ── Variantes del mock (una por caso real del toast) ────────────────────────
export type ToastVariant =
  | "estandar"     // imagen izquierda + body corto
  | "navegador"    // label compuesto "Brave - <tab>", sin título aparte
  | "largo"        // body que desborda → barra "Ver más"
  | "persistente"  // duration=0: franja de descarte con hover
  | "botones"      // con actions (p. ej. Telegram: Marcar como leída)
  | "placeholder"; // app sin icono resuelvable → inicial

export type ToastState = "normal" | "hover" | "wipe" | "expandido";
