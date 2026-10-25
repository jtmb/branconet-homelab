import test from "node:test";
import assert from "node:assert/strict";
import { podMetadataResponse } from "../src/lib/pod-metadata-response";
import type { ResourceAvailability } from "../src/lib/resource-cache";

const availability: ResourceAvailability = { state: "healthy", sampledAt: "2026-10-25T00:00:00Z", staleAgeMs: null, retryAfterMs: 9123, durationMs: 7 };

test("small warm bodies keep private encoded prefixes and copy only on demand", async () => {
  for (const count of [0, 1, 17]) {
    const data = { pods: Array.from({ length: count }, (_, i) => ({ metadata: { name: `${i}-é😀`, namespace: "apps" }, spec: { containers: [{ image: "fixture.invalid/app:v1" }] } })), availability: { pods: availability } };
    const expected = await podMetadataResponse(data, () => true, false).text();
    assert(Buffer.byteLength(expected) < 16384);
    const NativeResponse = globalThis.Response, slice = Uint8Array.prototype.slice, encode = TextEncoder.prototype.encode;
    const bodyKinds: unknown[] = [], copies: number[] = [], encodings: string[] = [];
    globalThis.Response = new Proxy(NativeResponse, { construct(target, args) { bodyKinds.push(args[0]); return Reflect.construct(target, args); } });
    Uint8Array.prototype.slice = function (start, end) { const value = slice.call(this, start, end); copies.push(value.byteLength); return value; };
    TextEncoder.prototype.encode = function (value) { encodings.push(value ?? ""); return encode.call(this, value); };
    try {
      const response = podMetadataResponse(data, () => true, false);
      await Promise.resolve();
      assert(bodyKinds[0] instanceof ReadableStream, "small body bypasses eager Response string encoding");
      assert.deepEqual(copies, [], "no prefix copy before consumption");
      assert.equal(encodings.length, 1, "only current availability is UTF8-encoded per warm response");
      assert(encodings[0].startsWith(',"availability":'));
      await response.body!.cancel();
      assert.deepEqual(copies, []);
      const reader = podMetadataResponse(data, () => true, false).body!.getReader();
      const first = await reader.read();
      assert.equal(copies.length, 1);
      assert.equal(first.value!.byteLength, copies[0]);
      first.value!.fill(0);
      await reader.cancel();
      assert.equal(copies.length, 1, "partial abandonment performs no remaining prefix copies");
      assert.equal(await podMetadataResponse(data, () => true, false).text(), expected, "consumer mutation never reaches cached prefix");
      const stale = podMetadataResponse({ ...data, availability: { pods: { ...availability, state: "stale", retryAfterMs: 41, staleAgeMs: 10123 } } }, () => true, false);
      assert(stale.headers.has("Warning"));
      assert.equal((await stale.json()).availability.resources.pods.retryAfterMs, 41);
      assert.equal((await podMetadataResponse(data, () => true, false).json()).availability.resources.pods.retryAfterMs, 9123);
    } finally {
      globalThis.Response = NativeResponse;
      Uint8Array.prototype.slice = slice;
      TextEncoder.prototype.encode = encode;
    }
  }
});
