import type { NextConfig } from "next";

/**
 * Phase-1 dashboard config.
 *
 * dev:  Next.js dev server proxies /api/* to the FastAPI replay server on :8765,
 *       so the SPA can do `fetch("/api/runs")` without CORS gymnastics.
 *
 * prod: Built with `output: "export"` and the static bundle is served *by*
 *       FastAPI itself (web/api/serve_replay.py mounts web/ui/out/ as static
 *       files). The Next dev server proxy then drops out and same-origin /api/*
 *       just works because the API and UI are on the same host:port.
 */
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // dev-only: forward /api/* to the FastAPI replay server.
  // The `rewrites` block is a no-op in static export builds.
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8765/api/:path*",
      },
    ];
  },
};

export default nextConfig;
