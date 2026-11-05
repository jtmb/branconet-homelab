import test from "node:test";
import assert from "node:assert/strict";
import { podMetadataResponse } from "../src/lib/pod-metadata-response";
import type { ResourceAvailability } from "../src/lib/resource-cache";

const healthy: ResourceAvailability = { state: "healthy", sampledAt: "2026-10-25T00:00:00Z", staleAgeMs: null, retryAfterMs: 10000, durationMs: 12 };
function snapshot(count: number) {
  return { pods: Array.from({ length: count }, (_, index) => ({
    metadata: { uid: `apps/${index}`, namespace: "apps", name: `${index}-Ã°Å¸Ëœâ‚¬ÃƒÂ©"\\\n${"x".repeat(83)}`, labels: { data: "private-marker" } },
    spec: { containers: [{ image: "fixture.invalid/public:v1", env: [{ value: "private-marker" }] }] },
    status: { phase: "Running" },
  })), availability: { pods: healthy } };
}

test("warm large construction and abandonment do no entity-sized allocation or prefix copy", async () => {
  const data = snapshot(1001);
  await podMetadataResponse(data, () => true, false).arrayBuffer();
  const NativeArray = globalThis.Uint8Array;
  const originalSlice = NativeArray.prototype.slice;
  const originalSet = NativeArray.prototype.set;
  const allocations: number[] = [], copies: number[] = [];
  globalThis.Uint8Array = new Proxy(NativeArray, {
    construct(target, args) {
      if (typeof args[0] === "number") allocations.push(args[0]);
      return Reflect.construct(target, args);
    },
  });
  NativeArray.prototype.slice = function (start, end) {
    const result = originalSlice.call(this, start, end);
    copies.push(result.byteLength);
    return result;
  };
  NativeArray.prototype.set = function (source, offset) {
    copies.push(source.length);
    return originalSet.call(this, source, offset);
  };
  try {
    const abandoned = podMetadataResponse(data, () => true, false);
    await Promise.resolve();
    assert.deepEqual(copies, [], "no eager copy or stream prefetch");
    assert(allocations.every(size => size <= 65536), "no whole-entity allocation");
    await abandoned.body!.cancel();
    assert.deepEqual(copies, [], "cancelled unread response does not copy its prefix");
    const reader = podMetadataResponse(data, () => true, false).body!.getReader();
    const first = await reader.read();
    assert.equal(first.value!.byteLength, 65536);
    assert.deepEqual(copies, [65536]);
    await reader.cancel();
    await Promise.resolve();
    assert.deepEqual(copies, [65536], "partial cancellation prevents all remaining prefix copies");
  } finally {
    globalThis.Uint8Array = NativeArray;
    NativeArray.prototype.slice = originalSlice;
    NativeArray.prototype.set = originalSet;
  }
});

test("owned chunks preserve exact Unicode JSON, fresh footers, clones and independent mutation", async () => {
  const data = snapshot(997);
  const expected = await podMetadataResponse(data, () => true, false).text();
  assert(!expected.includes("private-marker"));
  const response = podMetadataResponse(data, () => true, false);
  assert.equal(Number(response.headers.get("Content-Length")), Buffer.byteLength(expected));
  const chunks: Uint8Array[] = [];
  const reader = response.body!.getReader();
  while (true) { const { value, done } = await reader.read(); if (done) break; assert(value.byteLength <= 65536); chunks.push(value); }
  assert(chunks.length > 3);
  assert.equal(Buffer.concat(chunks).toString("utf8"), expected);
  chunks[0].fill(0);
  assert.equal(await podMetadataResponse(data, () => true, false).text(), expected);
  const original = podMetadataResponse(data, () => true, false), clone = original.clone();
  assert.deepEqual(await Promise.all([original.text(), clone.text()]), [expected, expected]);
  const stale = { ...data, availability: { pods: { ...healthy, state: "stale" as const, staleAgeMs: 11123, retryAfterMs: 73 } } };
  const staleResponse = podMetadataResponse(stale, () => true, false);
  assert(staleResponse.headers.has("Warning"));
  assert.equal((await staleResponse.json()).availability.resources.pods.retryAfterMs, 73);
  assert.equal((await podMetadataResponse(data, () => true, false).json()).availability.resources.pods.retryAfterMs, 10000);
});

test("small text and filtered large streams retain independent complete inventories", async () => {
  for (const count of [0, 1, 59, 271, 10000]) {
    const data = snapshot(count);
    const response = podMetadataResponse(data, () => true, false);
    const body = await response.json();
    assert.equal(body.pods.length, count);
    assert.equal(new Set(body.pods.map((row: { id: string }) => row.id)).size, count);
    const selected = podMetadataResponse(data, pod => Number(pod.metadata.uid.split("/")[1]) % 2 === 0, true);
    assert.equal((await selected.json()).pods.length, Math.ceil(count / 2));
  }
});
