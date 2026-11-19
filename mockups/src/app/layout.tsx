import type { Metadata } from "next";
import Link from "next/link";
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
          <Link href="/" style={{ color: "#80cbc4", textDecoration: "none" }}>
            Variantes
          </Link>
          <Link
            href="/anatomia"
            style={{ color: "#a6adc8", textDecoration: "none" }}
          >
            Anatomía
          </Link>
          <Link
            href="/tokens"
            style={{ color: "#a6adc8", textDecoration: "none" }}
          >
            Tokens
          </Link>
          <span
            style={{
              marginLeft: "auto",
              color: "#585b70",
              fontFamily: "monospace",
              fontSize: 11,
            }}
          >
            verdantis 0.18.5 · specs vigentes
          </span>
        </nav>
        {children}
      </body>
    </html>
  );
}
