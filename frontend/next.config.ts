import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Proxy Flask backend endpoints during dev:
    // Next: http://localhost:3000
    // Flask: http://localhost:5000
    const flaskInternalUrl = process.env.FLASK_INTERNAL_URL || "http://127.0.0.1:5000";
    return [
      { source: "/api/:path*", destination: `${flaskInternalUrl}/api/:path*` },
    ];
  },
};

export default nextConfig;
