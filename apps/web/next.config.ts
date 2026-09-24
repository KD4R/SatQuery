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
            value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws: wss:; font-src 'self';",
          },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://api:8000/api/v1/:path*",
      },
    ];
  },
};
export default nextConfig;
