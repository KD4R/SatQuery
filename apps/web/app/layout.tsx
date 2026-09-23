import type { Metadata, Viewport } from "next";

import "maplibre-gl/dist/maplibre-gl.css";
import "./mission.css";

export const metadata: Metadata = {
  title: "SatQuery AI — Mission Console",
  description: "Evidence-first satellite intelligence command center",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#000000",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Skip link: the console is dense and the map is a keyboard trap risk. */}
        <a href="#mission-main" className="skip-link label">
          Skip to mission console
        </a>
        {children}
      </body>
    </html>
  );
}
