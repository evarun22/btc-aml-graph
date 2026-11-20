/** @type {import('next').NextConfig} */
const API_URL = process.env.API_URL || "http://localhost:8010";

const nextConfig = {
  reactStrictMode: true,

  // Local reasoning models answer in 30-120s. Next's rewrite proxy aborts at
  // 30s by default and returns a generic 500 while the API is still working.
  experimental: {
    proxyTimeout: 300000,
  },

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
