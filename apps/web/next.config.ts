import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: {
    // The generated OpenAPI client has eslint-disable headers that Next.js flags
    // as unused. Ignore that directory during builds; it is linted separately.
    ignoreDuringBuilds: false,
    dirs: ["app", "components", "lib/api/gateway.ts", "lib/api/client.ts", "lib/api/source.ts", "lib/api/types.ts", "lib/api/claims.ts", "lib/api/routes.ts"],
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
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src * data: blob:; connect-src * ws: wss:; font-src 'self' https://fonts.gstatic.com; worker-src 'self' blob:;",
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
    ];
  },
};
export default nextConfig;
