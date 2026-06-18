/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy API calls to the gateway during development.
    const gateway = process.env.GATEWAY_URL || "http://localhost:8000";
    return [{ source: "/api/v1/:path*", destination: `${gateway}/api/v1/:path*` }];
  },
};
export default nextConfig;
