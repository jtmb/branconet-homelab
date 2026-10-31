import { test } from "node:test";
import assert from "node:assert/strict";
import { ClusterResourceCache } from "../src/lib/resource-cache";
import { KubernetesCommandError } from "../src/lib/kubectl-client";

test("resource-only warm read skips overview derivation and preserves TTL, stale expiry and invalidation", async () => {
  let now = 1000, calls = 0, overviewReads = 0, fail = false;
  const pods = [{ metadata: {name:"one"}, get status() { overviewReads++; throw Error("Overview must not scan resource-only read"); } }];
  const cache = new ClusterResourceCache(async resource => { assert.equal(resource,"pods");calls++; if(fail)throw new KubernetesCommandError(502,"Kubernetes command failed");return {items:pods}; },()=>now);
  (globalThis as any).__bortusResources = cache;
  const {getCachedClusterResource,invalidateCache} = await import("../src/lib/cluster-cache");
  const first = await getCachedClusterResource("pods");
  await Promise.all(Array.from({length:20},()=>getCachedClusterResource("pods")));
  assert.equal(calls,1); assert.equal(overviewReads,0); assert.equal(first.value?.items,pods);
  fail=true;now+=10001;
  assert.equal((await getCachedClusterResource("pods")).availability.state,"stale");
  now+=120001;
  assert.equal((await getCachedClusterResource("pods")).availability.state,"unavailable");
  fail=false;invalidateCache();
  assert.equal((await getCachedClusterResource("pods")).availability.state,"healthy");
  assert.equal(overviewReads,0);
});
