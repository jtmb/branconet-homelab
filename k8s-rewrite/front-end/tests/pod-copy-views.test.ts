import test from "node:test";
import assert from "node:assert/strict";
import { podMetadataResponse } from "../src/lib/pod-metadata-response";

test("body copying avoids full-range views while preserving owned bounded bytes", async () => {
  for (const count of [1, 1049]) {
    const data = { pods: Array.from({ length: count }, (_, i) => ({ metadata: { name: `unit-é😀-${i}`, namespace: "apps", uid: `uid-${i}` } })),
      availability: { pods: { state: "healthy" as const, sampledAt: null, staleAgeMs: null, retryAfterMs: 91, durationMs: 3 } } };
    const expected = await podMetadataResponse(data, () => true, false).text();
    const response = podMetadataResponse(data, () => true, false), original = Uint8Array.prototype.subarray;
    let views = 0;
    Uint8Array.prototype.subarray = function (start, end) { views++; return original.call(this, start, end); };
    const chunks: Uint8Array[] = [];
    try {
      const reader = response.body!.getReader();
      while (true) { const next = await reader.read(); if (next.done) break; assert(next.value.byteLength <= 65536); chunks.push(next.value); }
    } finally { Uint8Array.prototype.subarray = original; }
    assert.equal(Buffer.concat(chunks).toString("utf8"), expected);
    if (count === 1) assert.equal(views, 0, "whole prefix and footer need no transient views");
    else assert(views <= 1, "only the partial final prefix needs a view");
    chunks[0].fill(0);
    assert.equal(await podMetadataResponse(data, () => true, false).text(), expected);
  }
});
