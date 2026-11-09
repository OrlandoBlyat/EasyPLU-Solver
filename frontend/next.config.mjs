import { hostname, networkInterfaces } from "node:os"

function localAddresses() {
  try {
    return Object.values(networkInterfaces()).flatMap(addresses =>
      (addresses || []).filter(address => !address.internal).map(address => address.address)
    )
  } catch {
    // Restricted build environments may not permit interface enumeration.
    return []
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  compress: false,
  // Allow HMR from this machine's LAN addresses without trusting arbitrary origins.
  allowedDevOrigins: [
    hostname(),
    ...localAddresses(),
    ...(process.env.DEV_ALLOWED_ORIGINS || "").split(",").map(value => value.trim()).filter(Boolean),
  ],
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
