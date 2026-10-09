import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: ["@kubernetes/client-node"],
  // Output environment variables to console for debugging
  env: {
    NEXT_PUBLIC_APP_NAME: "BORTUS K8s",
  },
  // Redirect old /vars route to /secrets
  async redirects() {
    return [
      {
        source: "/vars",
        destination: "/secrets",
        permanent: true,
      },
    ];
  },
  // Pages now served directly by (dashboard) route group — no rewrites needed
};

export default nextConfig;
