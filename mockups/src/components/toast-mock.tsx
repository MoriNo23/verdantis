/**
 * ToastMock — réplica estática y FIEL del toast de Verdantis.
 *
 * Los estados (hover, wipe, expandido) se muestran como variantes estáticas
 * lado a lado, no como interacción: es documentación visual del render real
 * (ver lib/toast-tokens.ts para la procedencia de cada valor y la advertencia
 * de que el spec + código son la verdad).
 */
import { COLORS, FONTS, METRICS } from "@/lib/toast-tokens";
import type { ToastState, ToastVariant } from "@/lib/toast-tokens";

type Props = {
  variant: ToastVariant;
  state?: ToastState;
  appName?: string;
  titulo?: string;
  body?: string;
  buttons?: [string, string][]; // pares [key, label] como llegan por D-Bus
};

export function ToastMock({
  variant,
  state = "normal",
  appName = "Nombre de la app",
  titulo = "Título de la notificación",
  body = "Body sanitizado con wrap Pango a la columna de texto del card.",
  buttons = [
    ["mail-mark-read", "Marcar como leída"],
    ["default", "Abrir"],
  ],
}: Props) {
  const isBrowser = variant === "navegador";
  const isPersistent = variant === "persistente";
  const showButtons = variant === "botones";
  const hovered = state === "hover" && isPersistent;
  const expanded = state === "expandido";
  const wipe = state === "wipe";
  const overflow = variant === "largo" || expanded;

  // Columna de texto: 240; persistente CON hover le cede la franja (196)
  const colW = METRICS.textColW - (hovered ? METRICS.closeStripW : 0);
  const label = isBrowser ? `${appName} - ${titulo}` : appName;
  const appInicial = (appName || "?").trim().charAt(0).toUpperCase() || "?";
  const visButtons = buttons.slice(0, 3);

  return (
    <div
      style={{
        position: "relative",
        width: METRICS.cardW,
        borderRadius: METRICS.cardRadius,
        background: COLORS.cardBg,
        boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
        overflow: "hidden",
        flex: "0 0 auto",
        padding: METRICS.pad,
        paddingRight: hovered ? METRICS.closeStripW + METRICS.pad : METRICS.pad,
        boxSizing: "border-box",
      }}
    >
      {/* Bloque superior: imagen izquierda + columna de texto (top-aligned) */}
      <div style={{ display: "flex", gap: METRICS.imageLeftGap }}>
        {/* Imagen izquierda: slot 80, clip circular. Sin imagen de la
            notificación NI icono de app resuelto → placeholder con la
            inicial (spec toast-imagen-izquierda: el slot nunca desaparece). */}
        <div
          style={{
            width: METRICS.imageLeftW,
            height: METRICS.imageLeftW,
            borderRadius: "50%",
            background: COLORS.placeholderBg,
            color: COLORS.placeholderFg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: FONTS.title.family,
            fontWeight: 700,
            fontSize: 36,
            flex: "0 0 auto",
          }}
        >
          {appInicial}
        </div>

        <div style={{ width: colW, flexShrink: 0 }}>
          {/* Fila de app: slot 16 + texto (offset constante +20, spec
              toast-imagen-izquierda: el nombre se centra en su icono) */}
          <div
            style={{
              height: METRICS.appRowH,
              display: "flex",
              alignItems: "center",
              gap: 4,
              color: COLORS.app,
              fontFamily: FONTS.app.family,
              fontSize: FONTS.app.size,
              whiteSpace: "nowrap",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: METRICS.appIcon,
                height: METRICS.appIcon,
                borderRadius: 4,
                background: COLORS.placeholderBg,
                color: COLORS.placeholderFg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 9,
                fontWeight: 700,
                flex: "0 0 auto",
              }}
            >
              {appInicial}
            </div>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>
              {label}
            </span>
          </div>

          {/* Título (los navegadores lo pliegan en el label: hide_title) */}
          {!isBrowser && (
            <div
              style={{
                height: METRICS.titleRowH,
                color: COLORS.title,
                fontFamily: FONTS.title.family,
                fontWeight: 700,
                fontSize: FONTS.title.size,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {titulo}
            </div>
          )}

          {/* Body: wrap a la columna, cap de 3 líneas colapsado (spec
              toast-body-colapso: el "..." cae tras la línea exacta) */}
          <div
            style={{
              color: COLORS.body,
              fontFamily: FONTS.body.family,
              fontSize: FONTS.body.size,
              lineHeight: "21px",
              marginTop: 4,
              maxHeight: expanded ? undefined : 21 * METRICS.maxLines,
              overflow: "hidden",
            }}
          >
            {body}
          </div>
        </div>
      </div>

      {/* Fila de botones de acción (spec toast-acciones: ≤3, banda accent 22%) */}
      {showButtons && (
        <div
          style={{
            height: METRICS.actionsRowH,
            marginTop: METRICS.actionsGap,
            display: "flex",
            gap: 8,
          }}
        >
          {visButtons.map(([key, labelBtn], i) => (
            <div
              key={key}
              style={{
                flex: 1,
                borderRadius: METRICS.barRadius,
                background: `rgba(128, 203, 196, ${
                  i === 0 && state === "hover" ? 0.38 : 0.22
                })`,
                color: COLORS.title,
                fontFamily: FONTS.barLabel.family,
                fontSize: FONTS.barLabel.size,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {labelBtn}
            </div>
          ))}
        </div>
      )}

      {/* Barra "Ver más": full-width, accent 22%, radio 8 (anti-misclick) */}
      {overflow && (
        <div
          style={{
            height: METRICS.btnH,
            marginTop: METRICS.btnGap,
            borderRadius: METRICS.barRadius,
            background: "rgba(128, 203, 196, 0.22)",
            color: COLORS.title,
            fontFamily: FONTS.barLabel.family,
            fontSize: FONTS.barLabel.size,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 3,
          }}
        >
          {expanded ? "Ver menos" : "Ver más"}
          <span style={{ color: COLORS.accent, fontSize: 9 }}>
            {expanded ? "▲" : "▼"}
          </span>
        </div>
      )}

      {/* Franja de descarte: SOLO persistente + hover (spec toast-franja-descarte) */}
      {hovered && (
        <div
          style={{
            position: "absolute",
            right: 0,
            top: 0,
            bottom: 0,
            width: METRICS.closeStripW,
            background: COLORS.franjaTint,
          }}
        >
          {/* X: stroke 2.5px, #f38ba8, centrada en la franja */}
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              transform: "translate(-50%, -50%)",
            }}
          >
            <line
              x1="3"
              y1="3"
              x2="17"
              y2="17"
              stroke={COLORS.xStroke}
              strokeWidth={METRICS.xStrokeW}
              strokeLinecap="round"
            />
            <line
              x1="17"
              y1="3"
              x2="3"
              y2="17"
              stroke={COLORS.xStroke}
              strokeWidth={METRICS.xStrokeW}
              strokeLinecap="round"
            />
          </svg>
        </div>
      )}

      {/* Wipe de tiempo (estado parcial) */}
      {wipe && (
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: "62%",
            background: COLORS.wipe,
            pointerEvents: "none",
          }}
        />
      )}
    </div>
  );
}
