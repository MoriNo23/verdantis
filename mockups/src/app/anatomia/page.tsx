/**
 * Anatomía del toast con cotas px — el redline del tablero, en código.
 * Los valores salen de lib/toast-tokens.ts (trazabilidad a wayland_popup).
 */
import { COLORS, METRICS } from "@/lib/toast-tokens";

const pad = METRICS.pad;

function Cota({
  label,
  top,
  left,
  width,
  height,
}: {
  label: string;
  top?: number;
  left?: number;
  width?: number;
  height?: number;
}) {
  return (
    <div
      style={{
        position: "absolute",
        top,
        left,
        width,
        height,
        border: "1px dashed rgba(203, 166, 247, 0.8)",
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: -18,
          left: 2,
          color: "#cba6f7",
          fontSize: 10,
          fontFamily: "monospace",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </span>
    </div>
  );
}

export default function Anatomia() {
  const bodyTop = pad + METRICS.appRowH + METRICS.titleRowH + 4;
  return (
    <main
      style={{
        maxWidth: 1000,
        margin: "0 auto",
        padding: "40px 24px 80px",
        background: "#11111b",
        minHeight: "100vh",
      }}
    >
      <h1 style={{ color: "#e6e9f2", fontSize: 22, fontWeight: 700 }}>
        Anatomía del toast
      </h1>
      <p style={{ color: "#a6adc8", fontSize: 13 }}>
        Cotas px derivadas de <code>src/wayland_popup.py</code> — cada valor
        vive en <code>mockups/src/lib/toast-tokens.ts</code> con su constante
        original.
      </p>

      {/* Escala 2x para legibilidad */}
      <div
        style={{
          position: "relative",
          width: METRICS.cardW * 2,
          height: 320,
          margin: "60px auto",
          transform: "scale(1)",
        }}
      >
        {/* Card */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: METRICS.cardRadius,
            background: COLORS.cardBg,
          }}
        />
        {/* Imagen izquierda */}
        <div
          style={{
            position: "absolute",
            left: pad,
            top: pad,
            width: METRICS.imageLeftW,
            height: METRICS.imageLeftW,
            borderRadius: "50%",
            background: COLORS.placeholderBg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: COLORS.placeholderFg,
            fontWeight: 700,
            fontSize: 24,
          }}
        >
          V
        </div>
        {/* Filas de texto */}
        <div
          style={{
            position: "absolute",
            left: pad + METRICS.imageLeftW + METRICS.imageLeftGap,
            top: pad,
            color: COLORS.app,
            fontSize: 10,
            height: METRICS.appRowH,
            lineHeight: `${METRICS.appRowH}px`,
          }}
        >
          Nombre de la app — 10px
        </div>
        <div
          style={{
            position: "absolute",
            left: pad + METRICS.imageLeftW + METRICS.imageLeftGap,
            top: pad + METRICS.appRowH,
            color: COLORS.title,
            fontSize: 11,
            fontWeight: 700,
            height: METRICS.titleRowH,
            lineHeight: `${METRICS.titleRowH}px`,
          }}
        >
          Título de la notificación
        </div>
        <div
          style={{
            position: "absolute",
            left: pad + METRICS.imageLeftW + METRICS.imageLeftGap,
            top: bodyTop,
            width: METRICS.textColW,
            color: COLORS.body,
            fontSize: 11,
            lineHeight: "21px",
          }}
        >
          Body con wrap Pango a la columna de texto — el ellipsis cae al final
          de la tercera línea exacta.
        </div>

        {/* ── Cotas ── */}
        <Cota label="pad 14" top={pad - 8} left={pad - 8} width={METRICS.cardW - pad * 2 + 16} height={1} />
        <Cota label="imagen izquierda 80 (clip circular)" top={pad} left={pad} width={METRICS.imageLeftW} height={METRICS.imageLeftW} />
        <Cota label="gap 12" top={pad + 30} left={pad + METRICS.imageLeftW} width={METRICS.imageLeftGap} height={1} />
        <Cota label="columna de texto 240 (196 con franja en hover)" top={pad + METRICS.imageLeftW + 4} left={pad + METRICS.imageLeftW + METRICS.imageLeftGap} width={METRICS.textColW} height={1} />
        <Cota label="fila app 20" top={pad} left={pad + METRICS.imageLeftW + METRICS.imageLeftGap - 6} width={1} height={METRICS.appRowH} />
        <Cota label="fila título 22" top={pad + METRICS.appRowH} left={pad + METRICS.imageLeftW + METRICS.imageLeftGap - 6} width={1} height={METRICS.titleRowH} />
        <Cota label="card 360 × radio 12" top={0} left={0} width={METRICS.cardW} height={1} />
      </div>

      {/* Nota de medidas globales (equivale a la nota del tablero viejo) */}
      <div
        style={{
          margin: "0 auto",
          padding: 16,
          borderRadius: 12,
          background: "#181825",
          border: "1px solid #313244",
          color: "#cdd6f4",
          fontFamily: "monospace",
          fontSize: 12,
          lineHeight: 1.8,
          maxWidth: 720,
        }}
      >
        <div style={{ color: "#80cbc4", fontWeight: 700 }}>
          medidas globales
        </div>
        columnas 240 / 196 (franja en hover de persistente) · franja de
        descarte 44 · barra "Ver más" 28 · fila de botones 28 ·
        radios card/barra 12 / 8 · avatar → imagen izquierda 80 · X stroke
        2.5 · cap de body 3 líneas
      </div>
    </main>
  );
}
