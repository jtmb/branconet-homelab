import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output environment variables to console for debugging
  env: {
    NEXT_PUBLIC_APP_NAME: "Botrus K8s",
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