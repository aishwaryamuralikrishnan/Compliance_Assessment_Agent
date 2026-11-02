import type { NextConfig } from "next";

// The browser talks to one origin: /api/* is proxied to the FastAPI process, so the session cookie is first-party
// and there is no CORS. API_URL overrides the backend address (containers, deployment).
const API_URL = process.env.API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone", // web/Dockerfile copies .next/standalone: the server and only the modules it needs
  reactStrictMode: true,
  compress: false, // compression buffers the Server-Sent Events of /api/runs/{id}/events; a reverse proxy can compress the rest in production
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
