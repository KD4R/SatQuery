import type { Metadata, Viewport } from "next";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import "./mission.css";
import "./console-section.css";
import "./dashboard.css";

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

// Dark-first: with no stored choice the page opens dark rather than following the
// OS preference, because the console panels are authored on dark tokens and a
// light OS setting used to open a half-legible page. The toggle still persists.
const themeBootstrap =`(function(){try{var k='satquery-theme';var m=document.cookie.match(/(?:^|; )satquery-theme=(light|dark)(?:;|$)/);var t=localStorage.getItem(k)||(m&&m[1]);if(t!=='light'&&t!=='dark'){t='dark'}document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t;}catch(e){}})()`;

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
