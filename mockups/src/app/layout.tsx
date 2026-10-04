import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Verdantis — Mockups del toast",
  description:
    "Documentación visual del toast de verdantis (wireframe-ui / Next.js)",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased">
      <body
        className="min-h-full flex flex-col"
        style={{
          background: "#11111b",
          fontFamily: "Manrope, sans-serif",
        }}
      >
        <nav
          style={{
            display: "flex",
            gap: 24,
            padding: "14px 24px",
            background: "#181825",
            borderBottom: "1px solid #313244",
            fontSize: 13,
          }}
        >
          <a href="/" style={{ color: "#80cbc4", textDecoration: "none" }}>
            Variantes
          </a>
          <a
            href="/anatomia"
            style={{ color: "#a6adc8", textDecoration: "none" }}
          >
            Anatomía
          </a>
          <a
            href="/tokens"
            style={{ color: "#a6adc8", textDecoration: "none" }}
          >
            Tokens
          </a>
          <span
            style={{
              marginLeft: "auto",
              color: "#585b70",
              fontFamily: "monospace",
              fontSize: 11,
            }}
          >
            verdantis 0.9.0 · post-0.9.0 specs
          </span>
        </nav>
        {children}
      </body>
    </html>
  );
}
