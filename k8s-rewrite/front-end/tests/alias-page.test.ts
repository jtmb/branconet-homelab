import { test } from "node:test";
import assert from "node:assert/strict";
import { AliasCatalog, MAX_ALIASES } from "../src/lib/alias-catalog";
import { SecretError } from "../src/lib/cluster-secrets";
const ref = (i: number) => ({ alias: "page_" + String(i).padStart(5, "0"), namespace: "apps", name: "fixture", key: i % 2 ? "__proto__" : "constructor" });
test("cursor projection exactly matches original complete-list filtering for all page boundaries", async () => {
  for (const count of [0, 100, 101, 603, 10000]) {
    const catalog = new AliasCatalog(async () => [Array.from({ length: count }, (_, i) => ({ ...ref(i), namespace: i % 13 === 0 ? "history" : i % 11 === 0 ? "outside" : "apps" }))]);
    const original = await catalog.list("file"), scope = new Set(["apps"]); let cursor: string | null = null; const collected = [];
    do {
      const expected = original.filter(row => scope.has(row.namespace) && (cursor === null || row.alias > cursor));
      const page = await catalog.page("file", scope, null, cursor);
      assert.deepEqual(page, { references: expected.slice(0, 100), nextCursor: expected.length > 100 ? expected[99].alias : null });
      assert(page.references.length <= 100); collected.push(...page.references); cursor = page.nextCursor;
    } while (cursor !== null);
    assert.deepEqual(collected, original.filter(row => scope.has(row.namespace)));
    assert.deepEqual(await catalog.page("file", new Set(), null, null), { references: [], nextCursor: null });
  }
});
test("page clones only returned references, isolates callers and does not cache a namespace scope", async () => {
  const catalog = new AliasCatalog(async () => [Array.from({ length: 1000 }, (_, i) => ref(i))]);
  const cache = await catalog.cache.get("file"); let keyReads = 0;
  for (const row of cache.rows) { const key = row.key; Object.defineProperty(row, "key", { enumerable: true, get() { keyReads++; return key; } }); }
  const first = await catalog.page("file", new Set(["apps"]), null, null); assert.equal(keyReads, 100);
  first.references[0].key = "caller-change"; assert.notEqual((await catalog.resolve("file", first.references[0].alias))!.key, "caller-change");
  const next = await catalog.page("file", new Set(["outside"]), null, null); assert.deepEqual(next, { references: [], nextCursor: null });
  assert.deepEqual(await catalog.page("file", new Set(["apps"]), "outside", null), { references: [], nextCursor: null });
});
test("exact spelling/prototype-like aliases and exclusive cursors retain original lexical order", async () => {
  const rows = ["__proto__", "constructor", "a/b", "a_b", "a-b", "A", "z"].map(alias => ({ ...ref(0), alias }));
  const catalog = new AliasCatalog(async () => [rows]); const original = await catalog.list("");
  for (const cursor of [null, "__proto__", "a.b", "z", "zz"]) {
    assert.deepEqual((await catalog.page("", new Set(["apps"]), null, cursor)).references, original.filter(row => cursor === null || row.alias > cursor));
  }
});
test("page retains TTL, invalidation, full-source refusals and expired-source failure semantics", async () => {
  let now = 0, fail = false, loads = 0, rows = [ref(0)];
  const catalog = new AliasCatalog(async () => { loads++; if (fail) throw new SecretError(503, "Metadata unavailable"); return [rows]; }, () => now);
  const page = () => catalog.page("file", new Set(["apps"]), null, null);
  await page(); rows = [ref(1)]; await page(); assert.equal(loads, 1); catalog.invalidate(); assert.equal((await page()).references[0].alias, ref(1).alias);
  fail = true; now = 10001; await assert.rejects(page(), error => error instanceof SecretError && error.status === 503);
  for (const invalid of [[...Array.from({ length: MAX_ALIASES }, (_, i) => ref(i)), ref(MAX_ALIASES)], [ref(0), { ...ref(0), key: "conflict" }]]) {
    await assert.rejects(new AliasCatalog(async () => [invalid]).page("", new Set(["apps"]), null, null), error => error instanceof SecretError && [409, 503].includes(error.status));
  }
});
