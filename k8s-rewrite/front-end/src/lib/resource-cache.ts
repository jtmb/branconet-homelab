import { KubernetesCommandError } from "./kubectl-client";

export const CLUSTER_RESOURCES = ["nodes", "pods", "pv", "pvc", "longhorn", "sc", "namespaces", "services", "deployments", "replicasets", "ingresses"] as const;
export type ClusterResource = typeof CLUSTER_RESOURCES[number];
export type ResourceState = "healthy" | "empty" | "stale" | "unavailable" | "unsupported";
export interface ResourceAvailability {
  state: ResourceState;
  sampledAt: string | null;
  staleAgeMs: number | null;
  retryAfterMs: number;
  durationMs: number;
  error?: string;
}
export interface ResourceList { items: any[] }
interface Entry {
  value?: ResourceList;
  successAt?: number;
  nextAttempt: number;
  failures: number;
  attempts: number;
  durationMs: number;
  error?: string;
  unsupported?: boolean;
  flight?: Promise<void>;
}
type Loader = (resource: ClusterResource) => Promise<ResourceList>;

/** One shared request per resource, with independently retained snapshots and failure backoff. */
export class ClusterResourceCache {
  private entries = new Map<ClusterResource, Entry>();
  private generation = 0;
  constructor(private loader: Loader, private now = Date.now) {}

  private entry(resource: ClusterResource): Entry {
    let entry = this.entries.get(resource);
    if (!entry) { entry = { nextAttempt: 0, failures: 0, attempts: 0, durationMs: 0 }; this.entries.set(resource, entry); }
    return entry;
  }

  private async readOne(resource: ClusterResource) {
    const entry = this.entry(resource);
    if (entry.flight) await entry.flight;
    else if (this.now() >= entry.nextAttempt) {
      const generation = this.generation, start = this.now();
      entry.attempts++;
      const flight = (async () => {
        try {
          const value = await this.loader(resource);
          if (!value || !Array.isArray(value.items) || value.items.length > 10000)
            throw new KubernetesCommandError(502, "Cluster list exceeds limits or has an invalid shape");
          if (generation !== this.generation) return;
          entry.value = value;
          entry.successAt = this.now();
          entry.nextAttempt = this.now() + 10000;
          entry.failures = 0; entry.error = undefined; entry.unsupported = false;
        } catch (error) {
          if (generation !== this.generation) return;
          entry.failures++;
          entry.unsupported = resource === "longhorn" && error instanceof KubernetesCommandError && error.status === 404;
          entry.error = error instanceof KubernetesCommandError ? error.message : "Cluster read unavailable";
          entry.nextAttempt = this.now() + (entry.unsupported ? 300000 : Math.min(30000, 1000 * 2 ** Math.min(entry.failures - 1, 5)));
        } finally {
          if (generation === this.generation) entry.durationMs = Math.max(0, this.now() - start);
        }
      })();
      entry.flight = flight;
      await flight;
      if (entry.flight === flight) entry.flight = undefined;
    }
    return this.snapshot(resource);
  }

  private snapshot(resource: ClusterResource) {
    const entry = this.entry(resource);
    const age = entry.successAt === undefined ? null : Math.max(0, this.now() - entry.successAt);
    const usable = entry.value !== undefined && age !== null && age <= 120000;
    const stale = Boolean(usable && (entry.error || age! >= 10000));
    const state: ResourceState = entry.unsupported ? "unsupported" : !usable ? "unavailable" : stale ? "stale" : entry.value!.items.length ? "healthy" : "empty";
    const availability: ResourceAvailability = {
      state, sampledAt: entry.successAt === undefined ? null : new Date(entry.successAt).toISOString(),
      staleAgeMs: stale ? age : null, retryAfterMs: Math.max(0, entry.nextAttempt - this.now()), durationMs: entry.durationMs,
      ...(entry.error ? { error: entry.error } : {}),
    };
    return { value: usable && !entry.unsupported ? entry.value : undefined, availability };
  }

  /** Read one resource through the same freshness, coalescing and failure path. */
  readResource(resource: ClusterResource) {
    return this.readOne(resource);
  }

  async read(resources: readonly ClusterResource[]) {
    const unique = [...new Set(resources)];
    const pairs = await Promise.all(unique.map(async resource => [resource, await this.readOne(resource)] as const));
    return Object.fromEntries(pairs) as Partial<Record<ClusterResource, ReturnType<ClusterResourceCache["snapshot"]>>>;
  }

  invalidate() {
    this.generation++;
    for (const entry of this.entries.values()) { entry.nextAttempt = 0; entry.flight = undefined; }
  }

  diagnostics() {
    return Object.fromEntries([...this.entries].map(([resource, entry]) => [resource, {
      ...this.snapshot(resource).availability, attempts: entry.attempts, failures: entry.failures, inFlight: Boolean(entry.flight),
      itemCount: this.snapshot(resource).value?.items.length ?? null,
    }]));
  }
}
