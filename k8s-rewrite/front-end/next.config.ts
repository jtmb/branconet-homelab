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
  // Rewrite flat paths to /cluster/* internals
  async rewrites() {
    return {
      beforeFiles: [
        { source: "/", destination: "/cluster" },
        // Node detail must be listed before flat listing route
        { source: "/nodes/:hostname", destination: "/cluster/nodes/:hostname" },
        { source: "/nodes", destination: "/cluster/nodes" },
        { source: "/deploy", destination: "/cluster/deploy" },
        { source: "/secrets", destination: "/cluster/secrets" },
        { source: "/settings", destination: "/cluster/settings" },
        { source: "/flux", destination: "/cluster/flux" },
        // Detail routes must be listed before flat listing routes
        { source: "/pods/:namespace/:name", destination: "/cluster/pods/:namespace/:name" },
        { source: "/pods/:namespace/:name/shell", destination: "/cluster/pods/:namespace/:name/shell" },
        { source: "/deployments/:namespace/:name", destination: "/cluster/deployments/:namespace/:name" },
        { source: "/name-spaces/:name", destination: "/cluster/name-spaces/:name" },
        { source: "/ingresses/:namespace/:name", destination: "/cluster/ingresses/:namespace/:name" },
        { source: "/pods", destination: "/cluster/pods" },
        { source: "/name-spaces", destination: "/cluster/name-spaces" },
        { source: "/deployments", destination: "/cluster/deployments" },
        { source: "/services", destination: "/cluster/services" },
        { source: "/ingresses", destination: "/cluster/ingresses" },
        { source: "/storage", destination: "/cluster/storage" },
      ],
      afterFiles: [],
      fallback: [],
    };
  },
};

export default nextConfig;