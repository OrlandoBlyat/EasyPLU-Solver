/** @type {import('next').NextConfig} */
const nextConfig = {
  compress: false,
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/:path*`,
      },
    ]
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
