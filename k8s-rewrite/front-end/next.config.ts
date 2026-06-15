import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output environment variables to console for debugging
  env: {
    NEXT_PUBLIC_APP_NAME: "Branconet K8s Manager",
  },
};

export default nextConfig;