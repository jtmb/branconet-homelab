import test from "node:test";
import assert from "node:assert/strict";
import { podMetadataResponse } from "../src/lib/pod-metadata-response";

test("availability coalesces into bounded owned chunks with exact UTF8 boundary framing", async () => {
  for (const padding of [0, 65100, 65300, 65536, 130900, 131072, 197113]) {
    const data = { pods: [{ metadata: { name: `é😀${"x".repeat(padding)}`, namespace: "apps" }, status: { phase: "Running" } }],
      availability: { pods: { state: "healthy" as const, sampledAt: null, staleAgeMs: null, retryAfterMs: 19, durationMs: 2 } } };
    const expected = await podMetadataResponse(data, () => true, false).text();
    const bytes = Buffer.from(expected), reader = podMetadataResponse(data, () => true, false).body!.getReader();
    const chunks: Uint8Array[] = [];
    while (true) { const next = await reader.read(); if (next.done) break; assert(next.value.byteLength > 0 && next.value.byteLength <= 65536); chunks.push(next.value); }
    assert.equal(chunks.length, Math.ceil(bytes.byteLength / 65536), "no extra footer-only chunk when it fits");
    for (const chunk of chunks.slice(0, -1)) assert.equal(chunk.byteLength, 65536);
    assert.deepEqual(Buffer.concat(chunks), bytes);
    chunks[0].fill(0);
    assert.equal(await podMetadataResponse(data, () => true, false).text(), expected);
  }
});
