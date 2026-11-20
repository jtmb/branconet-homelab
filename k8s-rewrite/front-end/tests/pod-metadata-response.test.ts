import test from "node:test";
import assert from "node:assert/strict";
import { podMetadataResponse } from "../src/lib/pod-metadata-response";
import { podFilter, podSummary } from "../src/lib/pod-query";
import { clusterResponse } from "../src/lib/cluster-response";
import type { ResourceAvailability } from "../src/lib/resource-cache";

const healthy: ResourceAvailability = { state: "healthy", sampledAt: "2026-10-10T00:00:00Z", staleAgeMs: null, retryAfterMs: 10000, durationMs: 50 };
function pod(name: string, namespace = "apps") {
  return { metadata: { name, namespace, uid: namespace + "/" + name, labels: { app: "api", data: "private-label-marker" }, annotations: { credential: "private-annotation-marker" } },
    spec: { containers: [{ name: "api", image: "fixture.invalid/api:v1", env: [{ name: "PASSWORD", value: "private-env-marker" }], args: ["private-args-marker"] }] },
    status: { phase: "Running", containerStatuses: [{ ready: true, restartCount: 2 }] } };
}
test("warm Pod projection preserves the complete existing JSON/privacy contract and current availability", async () => {
  const pods = Array.from({ length: 1000 }, (_, index) => pod(index === 0 ? 'quote"\\newline\n' : "pod-" + index));
  const data = { pods, availability: { pods: healthy } };
  assert.deepEqual(await podMetadataResponse(data, () => true, false).json(), await clusterResponse(data, { pods: pods.map(podSummary) }, ["pods"]).json());
  for (const marker of ["private-label-marker", "private-annotation-marker", "private-env-marker", "private-args-marker"])
    assert(!JSON.stringify(await podMetadataResponse(data, () => true, false).json()).includes(marker));
  const stale = { ...data, availability: { pods: { ...healthy, state: "stale" as const, staleAgeMs: 11000, retryAfterMs: 250, error: "Cluster read unavailable" } } };
  const staleResponse = podMetadataResponse(stale, () => true, false);
  assert(staleResponse.headers.get("Warning"));
  const staleBody = await staleResponse.json();
  assert.equal(staleBody.pods.length, 1000);
  assert.equal(staleBody.availability.state, "stale");
  assert.equal(staleBody.availability.resources.pods.retryAfterMs, 250);
  const unavailable = podMetadataResponse({ ...data, availability: { pods: { ...healthy, state: "unavailable" } } }, () => true, false);
  assert.equal(unavailable.status, 503);
  assert.equal((await unavailable.json()).pods, undefined);
});
test("Pod filters remain independent and replacement snapshots invalidate old metadata", async () => {
  const pods = [pod("api"), pod("system", "kube-system"), pod("other", "other")];
  for (const query of ["namespace=apps", "type=system", "namespace=absent", "labelSelector=app%3Dapi", "labelSelector=%21app"]) {
    const predicate = podFilter(new URLSearchParams(query)), data = { pods, availability: { pods: healthy } };
    assert.deepEqual(await podMetadataResponse(data, predicate, true).json(), await clusterResponse(data, { pods: pods.filter(predicate).map(podSummary) }, ["pods"]).json());
  }
  const replacement = [pod("replacement")];
  assert.equal((await podMetadataResponse({ pods: replacement, availability: { pods: healthy } }, () => true, false).json()).pods[0].name, "replacement");
  assert.deepEqual((await podMetadataResponse({ pods: [], availability: { pods: { ...healthy, state: "empty" } } }, () => true, false).json()).pods, []);
  assert.throws(() => podFilter(new URLSearchParams("type=invalid")));
});
