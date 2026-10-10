import type { CachedData } from "./cluster-cache";
import { clusterAvailability, clusterUnavailable } from "./cluster-response";
import { publicClusterMetadata } from "./cluster-metadata";
import { podSummary } from "./pod-query";

// Resource-cache snapshots are replaced, never edited. A weak key gives the
// projection exactly the raw snapshot's lifetime, including bounded stale use.
// Only redacted metadata is retained; request filters and responses are not.
const projections = new WeakMap<CachedData["pods"], { rows: unknown[]; json: string }>();

export function podMetadataResponse(data: Pick<CachedData, "pods" | "availability">, predicate: (pod: any) => boolean, filtered: boolean): Response {
  const failure = clusterUnavailable(data, "pods");
  if (failure) return failure;
  let projection = projections.get(data.pods);
  if (!projection) {
    const rows = publicClusterMetadata(data.pods.map(podSummary)) as unknown[];
    projection = { rows, json: JSON.stringify(rows) };
    projections.set(data.pods, projection);
  }
  const rows = filtered ? JSON.stringify(projection.rows.filter((_, index) => predicate(data.pods[index]))) : projection.json;
  // Availability changes on every read, even while the Pod snapshot is shared.
  // JSON.stringify supplies every inserted fragment; no unescaped input enters
  // this envelope. Account checks remain in the request middleware.
  return new Response(`{"pods":${rows},"availability":${JSON.stringify(clusterAvailability(data))},"privateFieldsOmitted":true}`, {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      ...(data.availability.pods?.state === "stale" ? { Warning: '110 - "Stale cluster snapshot"' } : {}) },
  });
}
