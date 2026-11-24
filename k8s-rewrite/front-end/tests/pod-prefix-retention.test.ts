import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import * as clusterResponse from "../src/lib/cluster-response";
import * as metadata from "../src/lib/cluster-metadata";
import * as query from "../src/lib/pod-query";
import type { podMetadataResponse } from "../src/lib/pod-metadata-response";

test("metadata cache retains only encoded projection and preserves immutable filtered rows", async () => {
  const retained: unknown[] = [];
  class ObservedWeakMap<K extends WeakKey, V> extends WeakMap<K, V> {
    set(key: K, value: V): this { retained.push(value); return super.set(key, value); }
  }
  const source = readFileSync("src/lib/pod-metadata-response.ts", "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const exports: { podMetadataResponse?: typeof podMetadataResponse } = {};
  vm.runInNewContext(compiled, { exports, WeakMap: ObservedWeakMap, TextEncoder, TextDecoder, ReadableStream, Response,
    require(name: string) {
      if (name === "./cluster-response") return clusterResponse;
      if (name === "./cluster-metadata") return metadata;
      if (name === "./pod-query") return query;
      throw new Error("Unexpected source dependency");
    } });
  const respond = exports.podMetadataResponse!;
  for (const count of [1, 1031]) {
    const pods = Array.from({ length: count }, (_, i) => ({ metadata: { name: `original-é😀-${i}`, namespace: "apps", uid: `uid-${i}`, labels: { app: "public", data: "private-marker" } } }));
    const data = { pods, availability: { pods: { state: "healthy" as const, sampledAt: null, staleAgeMs: null, retryAfterMs: 701, durationMs: 3 } } };
    const expected = await respond(data, () => true, false).text();
    const cached = retained.at(-1) as Record<string, unknown>;
    assert(!Object.hasOwn(cached, "rows"), "do not retain the duplicate row graph");
    assert(cached.body instanceof Uint8Array, "private encoded bytes are the retained projection");
    assert.deepEqual(Object.keys(cached).sort(), ["body", "byteLength"]);
    assert(!expected.includes("private-marker"));
    pods[0].metadata.name = "mutated-after-first-projection";
    const selected = await respond(data, pod => pod.metadata.uid === "uid-0", true).json();
    assert.equal(selected.pods.length, 1);
    assert.equal(selected.pods[0].name, "original-é😀-0", "filter uses the immutable projection");
    assert.equal(await respond(data, () => true, false).text(), expected);
    assert.equal(retained.at(-1), cached, "filters do not add a retained row cache");
    assert.deepEqual((await respond(data, () => false, true).json()).pods, []);
  }
});
