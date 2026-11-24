import { MetadataCache } from "./metadata-cache";
import { SecretError } from "./cluster-secrets";

export async function probeSecretScopes(namespaces: readonly string[], probe: (namespace: string, deadline: number) => Promise<void>, deadline = Date.now() + 8000) {
  let next = 0, failed = false;
  const results = await Promise.allSettled(Array.from({ length: Math.min(4, namespaces.length) }, async () => {
    while (!failed && next < namespaces.length) {
      try {
        if (Date.now() >= deadline) throw new SecretError(503, "Readiness dependency deadline exceeded");
        await probe(namespaces[next++], deadline);
      } catch (error) { failed = true; throw error; }
    }
  }));
  const failure = results.find(result => result.status === "rejected");
  if (failure?.status === "rejected") throw failure.reason;
}
export const createReadinessCache = (check: (key: string, signal: AbortSignal) => Promise<void>) => new MetadataCache<void>(check, 10000, 9000);
