import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The E2E suite and the seeded backend use 127.0.0.1; Next blocks dev resources from other
  // origins unless they are listed.
  allowedDevOrigins: ["127.0.0.1"],
  devIndicators: false,
};

export default nextConfig;
