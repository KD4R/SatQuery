import type { Metadata, Viewport } from "next";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
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

const themeBootstrap = `(function(){try{var k='satquery-theme';var m=document.cookie.match(/(?:^|; )satquery-theme=(light|dark)(?:;|$)/);var t=localStorage.getItem(k)||(m&&m[1]);if(t!=='light'&&t!=='dark'){t=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t;}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
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
