import {
  CoreV1Api,
  KubeConfig,
  wrapHttpLibrary,
  ResponseContext,
} from "@kubernetes/client-node";
import fetch from "node-fetch";
import {
  SecretStore,
  SecretError,
  secretFailure,
  type SecretTransport,
} from "./cluster-secrets";
export function secretNamespaces(): string[] {
  const scopes = (process.env.BORTUS_SECRET_NAMESPACES || "default")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!scopes.length)
    throw new SecretError(
      503,
      "BORTUS_SECRET_NAMESPACES must name at least one namespace",
    );
  return [...new Set(scopes)];
}
export function createSecretTransport(): SecretTransport {
  try {
    const config = new KubeConfig();
    if (process.env.KUBECONFIG) config.loadFromDefault();
    else if (process.env.KUBERNETES_SERVICE_HOST) config.loadFromCluster();
    else config.loadFromDefault();
    const cluster = config.getCurrentCluster();
    if (
      !cluster ||
      !cluster.server.startsWith("https:") ||
      cluster.skipTLSVerify
    )
      throw new SecretError(
        503,
        "A TLS-verified Kubernetes API connection is required",
      );
    const api = config.makeApiClient(CoreV1Api);
    const options = {
      httpApi: wrapHttpLibrary({
        async send(request) {
          const response = await fetch(request.getUrl(), {
            method: request.getHttpMethod(),
            headers: request.getHeaders(),
            body: request.getBody(),
            agent: request.getAgent(),
            signal: AbortSignal.timeout(8000),
          });
          const headers: Record<string, string> = {};
          response.headers.forEach((value, key) => {
            headers[key] = value;
          });
          return new ResponseContext(response.status, headers, {
            text: () => response.text(),
            binary: () => response.buffer(),
          });
        },
      }),
    };
    return {
      read: (namespace, name) =>
        api.readNamespacedSecret({ namespace, name }, options),
      list: async (namespace) => {
        const items = [];
        let cursor: string | undefined;
        do {
          const page = await api.listNamespacedSecret(
            { namespace, limit: 200, _continue: cursor },
            options,
          );
          items.push(...page.items);
          cursor = page.metadata?._continue;
        } while (cursor);
        return items;
      },
      create: (namespace, body) =>
        api.createNamespacedSecret({ namespace, body }, options),
      replace: (namespace, name, body) =>
        api.replaceNamespacedSecret({ namespace, name, body }, options),
    };
  } catch (error) {
    throw secretFailure(error);
  }
}
export function nativeSecrets() {
  return new SecretStore(createSecretTransport(), secretNamespaces());
}
