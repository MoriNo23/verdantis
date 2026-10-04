/**
 * Tokens del toast — la paleta como swatches, con el hex del render real.
 */
import { COLORS, FONTS, METRICS } from "@/lib/toast-tokens";

const PALETTE: [string, string, string][] = [
  ["cardBg", "#1e1e2e", "fondo del card (_card_bg)"],
  ["title", "#e6e9f2", "título (_left_title)"],
  ["body", "#cdd6f4", "body (_left_body)"],
  ["app", "#a6adc8", "fila de app (_left_app / _PLACEHOLDER_FG)"],
  ["accent", "#80cbc4", "accent default del daemon"],
  ["xStroke", "#f38ba8", "X de cierre de la franja"],
  ["placeholderBg", "#313244", "square del placeholder (_PLACEHOLDER_BG)"],
  ["franjaTint", "rgba(219,38,38,0.18)", "tinte franja hover (0.32 directo)"],
  ["wipe", "rgba(128,203,196,0.18)", "tinte del wipe de tiempo"],
];

const SIZES: [string, number][] = [
  ["_CARD_WIDTH", METRICS.cardW],
  ["_PAD", METRICS.pad],
  ["_IMAGE_LEFT_W", METRICS.imageLeftW],
  ["_IMAGE_LEFT_GAP", METRICS.imageLeftGap],
  ["_TEXT_COL_W", METRICS.textColW],
  ["_CLOSE_STRIP_W", METRICS.closeStripW],
  ["_BTN_H", METRICS.btnH],
  ["_ACTIONS_ROW_H", METRICS.actionsRowH],
  ["_CARD_RADIUS", METRICS.cardRadius],
  ["barra/botones radio", METRICS.barRadius],
  ["_APP_ICON_BOX", METRICS.appIcon],
  ["_APP_ROW_H", METRICS.appRowH],
  ["_TITLE_ROW_H", METRICS.titleRowH],
  ["X stroke", METRICS.xStrokeW],
];

export default function Tokens() {
  return (
    <main
      style={{
        maxWidth: 900,
        margin: "0 auto",
        padding: "40px 24px 80px",
        background: "#11111b",
        minHeight: "100vh",
      }}
    >
      <h1 style={{ color: "#e6e9f2", fontSize: 22, fontWeight: 700 }}>
        Tokens del toast
      </h1>
      <p style={{ color: "#a6adc8", fontSize: 13 }}>
        La paleta y las medidas del render real — la referencia que consumen
        los mockups.
      </p>

      <h2 style={{ color: "#cdd6f4", fontSize: 15, marginTop: 32 }}>Colores</h2>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 12 }}>
        {PALETTE.map(([name, hex, uso]) => (
          <div
            key={name}
            style={{
              width: 200,
              borderRadius: 10,
              overflow: "hidden",
              border: "1px solid #313244",
              background: "#181825",
            }}
          >
            <div
              style={{
                height: 56,
                background: hex.startsWith("rgba") ? "#1e1e2e" : hex,
                position: "relative",
              }}
            >
              {hex.startsWith("rgba") && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: hex,
                  }}
                />
              )}
            </div>
            <div style={{ padding: 10, fontFamily: "monospace", fontSize: 11 }}>
              <div style={{ color: "#e6e9f2" }}>{name}</div>
              <div style={{ color: "#80cbc4" }}>{hex}</div>
              <div style={{ color: "#6c7086", marginTop: 4 }}>{uso}</div>
            </div>
          </div>
        ))}
      </div>

      <h2 style={{ color: "#cdd6f4", fontSize: 15, marginTop: 40 }}>Medidas</h2>
      <div
        style={{
          marginTop: 12,
          padding: 16,
          borderRadius: 12,
          background: "#181825",
          border: "1px solid #313244",
          color: "#cdd6f4",
          fontFamily: "monospace",
          fontSize: 12,
          lineHeight: 2,
        }}
      >
        {SIZES.map(([name, v]) => (
          <div key={name} style={{ display: "flex", justifyContent: "space-between", maxWidth: 360 }}>
            <span>{name}</span>
            <span style={{ color: "#80cbc4" }}>{v}px</span>
          </div>
        ))}
      </div>

      <h2 style={{ color: "#cdd6f4", fontSize: 15, marginTop: 40 }}>Tipografía</h2>
      <div
        style={{
          marginTop: 12,
          padding: 16,
          borderRadius: 12,
          background: "#181825",
          border: "1px solid #313244",
          color: "#cdd6f4",
          fontFamily: "monospace",
          fontSize: 12,
          lineHeight: 2,
        }}
      >
        <div>
          app: Manrope {FONTS.app.size}px · título: Manrope{" "}
          {FONTS.title.size}px Bold · body: Manrope {FONTS.body.size}px ·
          barra/botones: Manrope {FONTS.barLabel.size}px
        </div>
        <div style={{ color: "#6c7086" }}>
          Manrope va bundled (src/fonts/ del daemon, copiada acá — sin red)
        </div>
      </div>
    </main>
  );
}
