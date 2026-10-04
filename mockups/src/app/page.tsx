/**
 * Variantes del toast — la grilla del tablero de diseño (3 columnas),
 * reimplementada como código post-0.9.0. Cada tarjeta lleva su caption
 * con el spec vivo que la define.
 */
import { ToastMock } from "@/components/toast-mock";

const LONG_BODY =
  "Parrafo largo que se re-wrappea al cambiar el ancho de la columna de texto del card y por lo tanto ocupa varias lineas al ancho completo, desbordando el cap de tres lineas visibles del body, con el ellipsis cayendo al final de la tercera linea exacta.";

function Card({
  titulo,
  spec,
  children,
}: {
  titulo: string;
  spec: string;
  children: React.ReactNode;
}) {
  return (
    <figure
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        margin: 0,
        padding: 16,
        borderRadius: 12,
        background: "#181825",
        border: "1px solid #313244",
      }}
    >
      <figcaption>
        <div style={{ color: "#cdd6f4", fontSize: 13, fontWeight: 700 }}>
          {titulo}
        </div>
        <div
          style={{
            color: "#6c7086",
            fontSize: 11,
            fontFamily: "monospace",
            marginTop: 2,
          }}
        >
          spec: {spec}
        </div>
      </figcaption>
      {children}
    </figure>
  );
}

export default function Home() {
  return (
    <main
      style={{
        maxWidth: 1240,
        margin: "0 auto",
        padding: "40px 24px 80px",
        background: "#11111b",
        minHeight: "100vh",
      }}
    >
      <h1
        style={{
          color: "#e6e9f2",
          fontFamily: "Manrope, sans-serif",
          fontSize: 22,
          fontWeight: 700,
        }}
      >
        Verdantis — mockups del toast
      </h1>
      <p style={{ color: "#a6adc8", fontSize: 13, marginTop: 6 }}>
        Documentación visual post-0.9.0. La verdad del comportamiento son los
        specs de <code>openspec/specs/</code> y el código; este mockup puede
        divergir (ver README).
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
          gap: 32,
          marginTop: 32,
        }}
      >
        <Card titulo="01 · Estándar" spec="toast-imagen-izquierda">
          <ToastMock variant="estandar" />
        </Card>

        <Card
          titulo="02 · Variante navegador"
          spec="toast-imagen-izquierda (label compuesto)"
        >
          <ToastMock
            variant="navegador"
            appName="Brave"
            titulo="Pinterest"
            body="Alguien guardó tu pin."
          />
        </Card>

        <Card titulo="03 · Body largo + Ver más" spec="toast-body-colapso">
          <ToastMock variant="largo" body={LONG_BODY} />
        </Card>

        <Card titulo="04 · Persistente + hover" spec="toast-franja-descarte">
          <ToastMock
            variant="persistente"
            state="hover"
            body="Toast persistente: la franja de descarte solo existe con hover."
          />
        </Card>

        <Card titulo="05 · Con botones de acción" spec="toast-acciones">
          <ToastMock
            variant="botones"
            appName="Telegram Desktop"
            titulo="Mori"
            body="Mensaje de Telegram con actions reales del dataset."
            buttons={[
              ["mail-mark-read", "Marcar como leída"],
              ["default", "Abrir"],
            ]}
          />
        </Card>

        <Card
          titulo="06 · App sin icono (placeholder)"
          spec="toast-iconos-app (fallback)"
        >
          <ToastMock
            variant="placeholder"
            appName="AppDesconocida"
            body="Sin archivo, sin .desktop exacto y sin icono en el tema."
          />
        </Card>

        <Card titulo="07 · Wipe parcial (t=62%)" spec="wipe de tiempo">
          <ToastMock variant="estandar" state="wipe" />
        </Card>

        <Card titulo="08 · Expandido" spec="toast-body-colapso (Ver menos)">
          <ToastMock variant="largo" state="expandido" body={LONG_BODY} />
        </Card>
      </div>
    </main>
  );
}
