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

/**
 * The dark-console theme is applied before first paint (p2-integration): the
 * dashboard cards persist a "satquery-theme" choice, and this inline bootstrap
 * reads it (cookie, then storage, then system) so a saved light theme does not
 * flash dark. Beyond dataset.theme it does not touch the page — the console's
 * own stylesheet owns everything else.
 */
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
