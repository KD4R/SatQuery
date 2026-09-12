import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
export const metadata: Metadata = {
  title: "SatQuery AI — Mission Control",
  description: "Evidence-first satellite intelligence command center",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
