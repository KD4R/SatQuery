import path from "node:path";

import type { NextConfig } from "next";

import { LEGACY_REDIRECTS } from "./lib/nav";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Pin the tracing root to this app. Without it Next infers the root from the
  // nearest lockfile up the tree, so a stray package-lock.json in a parent
  // directory nests the standalone server at .next/standalone/<path>/server.js
  // and the Playwright/Docker copy steps silently miss it.
  outputFileTracingRoot: path.join(__dirname),
  async redirects() {
    // Superseded routes -> the canonical mission console and its sections. Query
    // strings are carried through by Next, so deep links keep their parameters.
    return LEGACY_REDIRECTS.map(({ source, destination }) => ({
      source,
      destination,
      permanent: false,
    }));
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            // The browser talks to this origin (gateway via /api/v1 and /ws/v1
            // rewrites) plus the basemap tiles and OpenStreetMap place search
            // (lib/geo/geocode.ts); ws:/wss: is kept for the mission event socket.
            // Fonts are bundled via @fontsource, so no font CDN is allowed.
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://*.arcgisonline.com https://*.cartocdn.com https://basemaps.cartocdn.com; connect-src 'self' ws: wss: https://*.arcgisonline.com https://*.cartocdn.com https://basemaps.cartocdn.com https://nominatim.openstreetmap.org; font-src 'self'; worker-src 'self' blob:;",
          },
        ],
      },
    ];
  },
  async rewrites() {
    // Inside the compose network the gateway is "api"; a dev server on the host
    // reaches it on localhost, so the origin is overridable without touching
    // container configuration. API_URL/NEXT_PUBLIC_API_URL are honoured too —
    // they are the names the dashboard-era tooling and compose "web" service set.
    const gatewayOrigin =
      process.env.GATEWAY_ORIGIN ??
      process.env.API_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://api:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${gatewayOrigin}/api/v1/:path*`,
      },
      // The mission event socket (lib/ws/useMissionEvents.ts) connects to
      // ws(s)://<this host>/ws/v1/missions/<id>. Without this rule that path is a
      // 404 on the web server and live agent events never arrive. Behind a
      // separate reverse proxy, route /ws/ to the gateway with Upgrade headers
      // instead and this rewrite is simply never reached.
      {
        source: "/ws/v1/:path*",
        destination: `${gatewayOrigin}/ws/v1/:path*`,
      },
    ];
  },
};
export default nextConfig;
