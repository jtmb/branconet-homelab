import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Preserve the internal request origin until Next strips same-origin redirects.
  // Otherwise NextURL changes loopback hosts to localhost and leaks the runtime port.
  skipMiddlewareUrlNormalize: true,
  serverExternalPackages: ["@kubernetes/client-node"],
  outputFileTracingIncludes: { "/api/**": ["./native/secret-flat-selector.node"] },
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
