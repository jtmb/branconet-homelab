import { NextResponse } from "next/server";
import type { CachedData } from "./cluster-cache";
import type { ClusterResource } from "./resource-cache";
import { publicClusterMetadata } from "./cluster-metadata";

export function clusterAvailability(data: Pick<CachedData, "availability">) {
  const states = Object.values(data.availability).map(value => value!.state);
  const state = states.some(value => value === "unavailable") ? "partial" : states.some(value => value === "stale") ? "stale" : states.every(value => value === "empty" || value === "unsupported") ? "empty" : "healthy";
  return { state, resources: data.availability };
}

export function clusterUnavailable(data: Pick<CachedData, "availability">, ...required: ClusterResource[]) {
  if (required.some(resource => !data.availability[resource] || ["unavailable", "unsupported"].includes(data.availability[resource]!.state)))
    return NextResponse.json({ error: "Cluster data unavailable", availability: { ...clusterAvailability(data), state: "unavailable" } }, { status: 503, headers: { "Cache-Control": "no-store" } });
  return null;
}

export function clusterMissing(data: Pick<CachedData, "availability">, resource: ClusterResource, message: string) {
  const stale = data.availability[resource]?.state === "stale";
  return NextResponse.json({ error: stale ? "Resource absent from stale snapshot; refresh required" : message, availability: clusterAvailability(data) }, { status: stale ? 503 : 404, headers: { "Cache-Control": "no-store" } });
}

const fields: Partial<Record<ClusterResource, string[]>> = {
  nodes: ["nodes", "node", "readyNodes", "version"], pods: ["pods", "pod", "runningPods"],
  pv: ["volumes"], pvc: ["pvc"], sc: ["storageClasses"], namespaces: ["namespaces", "namespace"],
  services: ["services", "service"], deployments: ["deployments", "deployment"], ingresses: ["ingresses", "ingress"],
  longhorn: ["longhornVolumes", "healthyVolumes"],
};
export function clusterResponse(data: Pick<CachedData, "availability">, payload: Record<string, unknown>, required: ClusterResource[] = []) {
  const failure = clusterUnavailable(data, ...required);
  if (failure) return failure;
  const body = { ...payload };
  for (const [resource, availability] of Object.entries(data.availability)) {
    if (availability && ["unavailable", "unsupported"].includes(availability.state))
      for (const field of fields[resource as ClusterResource] || []) if (field in body) body[field] = null;
  }
  const availability = clusterAvailability(data);
  return NextResponse.json({ ...publicClusterMetadata(body) as Record<string, unknown>, availability, privateFieldsOmitted: true }, {
    headers: { "Cache-Control": "no-store", ...(Object.values(data.availability).some(value => value?.state === "stale") ? { Warning: '110 - "Stale cluster snapshot"' } : {}) },
  });
}
