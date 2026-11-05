import { test } from "node:test";
import assert from "node:assert/strict";
import { ClusterResourceCache, type ClusterResource } from "../src/lib/resource-cache";
import { KubernetesCommandError } from "../src/lib/kubectl-client";
import { clusterResponse, clusterUnavailable } from "../src/lib/cluster-response";

test("concurrent requested resources coalesce without unrelated cold fanout", async () => {
  let now = 1000;
  const calls: ClusterResource[] = [];
  const cache = new ClusterResourceCache(async resource => { calls.push(resource); return { items: resource === "pods" ? [{ metadata: { name: "example" } }] : [] }; }, () => now);
  await Promise.all(Array.from({ length: 20 }, () => cache.read(["pods", "nodes"])));
  assert.deepEqual(calls.sort(), ["nodes", "pods"]);
  const hot = await cache.read(["pods"]);
  assert.equal(hot.pods?.availability.state, "healthy");
  assert.equal(calls.length, 2);
  now += 10001;
  await cache.read(["pods"]);
  assert.equal(calls.length, 3);
  assert.equal(cache.diagnostics().nodes.state, "stale");
});

test("failure backoff preserves labelled bounded stale data and never invents empty success", async () => {
  let now = 1000, fail = false, calls = 0;
  const cache = new ClusterResourceCache(async () => { calls++; if (fail) throw new KubernetesCommandError(502, "Kubernetes command failed"); return { items: [{ metadata: { name: "kept" } }] }; }, () => now);
  await cache.read(["pods"]);
  fail = true; now += 10001;
  const stale = (await cache.read(["pods"])).pods!;
  assert.equal(stale.availability.state, "stale");
  assert.equal(stale.availability.staleAgeMs, 10001);
  assert.equal(stale.value?.items[0].metadata.name, "kept");
  const before = calls;
  await Promise.all(Array.from({ length: 20 }, () => cache.read(["pods"])));
  assert.equal(calls, before);
  now += 1000;
  assert.equal((await cache.read(["pods"])).pods?.availability.retryAfterMs, 2000);
  now += 130000;
  const expired = (await cache.read(["pods"])).pods!;
  assert.equal(expired.availability.state, "unavailable");
  assert.equal(expired.value, undefined);
  const unavailable = clusterUnavailable({ availability: { pods: expired.availability } }, "pods")!;
  assert.equal(unavailable.status, 503);
  assert.ok(!(await unavailable.text()).includes('"pods":[]'));
  const response = clusterResponse({ availability: { pods: stale.availability } }, { pods: stale.value!.items }, ["pods"]);
  assert.equal(response.status, 200);
  assert.ok(response.headers.get("Warning"));
  assert.equal((await response.json()).availability.state, "stale");
});

test("optional missing API, partial fields and true empty resources remain distinct", async () => {
  let now = 1000, calls = 0;
  const cache = new ClusterResourceCache(async resource => {
    calls++;
    if (resource === "longhorn") throw new KubernetesCommandError(404, "Kubernetes resource not found");
    if (resource === "pods") throw Error("private-native-marker");
    return { items: [] };
  }, () => now);
  const result = await cache.read(["nodes", "pods", "longhorn"]);
  assert.equal(result.nodes?.availability.state, "empty");
  assert.equal(result.longhorn?.availability.state, "unsupported");
  assert.equal(result.longhorn?.availability.retryAfterMs, 300000);
  assert.ok(!JSON.stringify(cache.diagnostics()).includes("private-native-marker"));
  const response = clusterResponse({ availability: Object.fromEntries(Object.entries(result).map(([resource, data]) => [resource, data!.availability])) }, { nodes: [], pods: [], longhornVolumes: 0 }, ["nodes"]);
  const body = await response.json();
  assert.equal(body.availability.state, "partial");
  assert.deepEqual(body.nodes, []);
  assert.equal(body.pods, null);
  assert.equal(body.longhornVolumes, null);
  now += 2000;
  await cache.read(["longhorn"]);
  assert.equal(calls, 3);
});

test("mutation invalidation prevents an older in-flight snapshot from repopulating cache", async () => {
  const resolvers: ((value: { items: any[] }) => void)[] = [];
  const cache = new ClusterResourceCache(() => new Promise(resolve => resolvers.push(resolve)));
  const old = cache.read(["pods"]);
  cache.invalidate();
  const fresh = cache.read(["pods"]);
  resolvers[1]({ items: [{ id: "after-mutation" }] });
  await fresh;
  resolvers[0]({ items: [{ id: "before-mutation" }] });
  await old;
  assert.equal((await cache.read(["pods"])).pods?.value?.items[0].id, "after-mutation");
  assert.equal(resolvers.length, 2);
});

test("invalid and oversized lists fail without truncation", async () => {
  for (const value of [{ items: null }, { items: Array(10001).fill({}) }]) {
    const cache = new ClusterResourceCache(async () => value as any);
    const result = await cache.read(["pods"]);
    assert.equal(result.pods?.availability.state, "unavailable");
    assert.equal(result.pods?.value, undefined);
  }
});
