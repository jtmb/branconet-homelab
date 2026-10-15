import test from "node:test";
import assert from "node:assert/strict";
import { ClusterResourceCache } from "../src/lib/resource-cache";
import { KubernetesCommandError } from "../src/lib/kubectl-client";

test("overview counts only explicit Longhorn healthy robustness and preserves labelled failed snapshots", async () => {
  let now = 1000, fail = false;
  const records = [
    { state: "attached", robustness: "healthy" },
    { state: "detached", robustness: "healthy" },
    { state: "creating", robustness: "healthy" },
    { state: "attached", robustness: "degraded" },
    { state: "attached", robustness: "faulted" },
    { state: "attached", robustness: "unknown" },
    { state: "attached" },
    {},
  ];
  const calls: string[] = [];
  const fixture = new ClusterResourceCache(async resource => {
    calls.push(resource); assert.equal(resource, "longhorn");
    if (fail) throw new KubernetesCommandError(502, "Kubernetes command failed");
    return { items: records.map((status, i) => ({ metadata: { namespace: "longhorn-system", name: "public-volume-" + i }, spec: { size: "1024" }, status })) };
  }, () => now);
  const globals = globalThis as typeof globalThis & { __bortusResources?: ClusterResourceCache };
  const original = globals.__bortusResources;
  globals.__bortusResources = fixture;
  try {
    const { getCachedClusterData } = await import("../src/lib/cluster-cache");
    const first = await getCachedClusterData(["longhorn"]);
    assert.equal(first.info.longhornVolumes, 8); assert.equal(first.info.healthyVolumes, 3);
    assert.equal(first.availability.longhorn?.state, "healthy");
    assert.equal(first.volumes.length, 8); assert.deepEqual(calls, ["longhorn"]);
    assert.equal(first.volumes[3].status, "attached", "attachment display is independent of the healthy counter");
    fail = true; now += 10001;
    const stale = await getCachedClusterData(["longhorn"]);
    assert.equal(stale.info.healthyVolumes, 3); assert.equal(stale.info.longhornVolumes, 8);
    assert.equal(stale.availability.longhorn?.state, "stale");
    now += 130000;
    const unavailable = await getCachedClusterData(["longhorn"]);
    assert.equal(unavailable.info.healthyVolumes, 0);
    assert.equal(unavailable.availability.longhorn?.state, "unavailable");
  } finally {
    if (original === undefined) delete globals.__bortusResources;
    else globals.__bortusResources = original;
  }
});
