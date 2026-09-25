import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
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
            value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws: wss:; font-src 'self';",
          },
        ],
      },
    ];
  },
  async rewrites() {
    // Inside the compose network the gateway is "api"; a dev server on the host
    // reaches it on localhost, so the origin is overridable without touching
    // container configuration.
    const gatewayOrigin = process.env.GATEWAY_ORIGIN ?? "http://api:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${gatewayOrigin}/api/v1/:path*`,
      },
    ];
  },
};
export default nextConfig;
