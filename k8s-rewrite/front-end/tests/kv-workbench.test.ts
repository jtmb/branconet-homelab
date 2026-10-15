import { test } from "node:test";
import assert from "node:assert/strict";
import { captureRevision, captureMatchesMetadata, canonicalBase64, convertEncoding, draftChange, draftsFor, parseTransfer, replacementDrafts, ValueFence, WorkbenchFailure, workbenchRequest, type KvSelectedPath } from "../src/components/secrets/kv-workbench-model";
const path: KvSelectedPath = { id: "path", mountId: "mount", path: "apps/api", namespace: "apps", name: "original", revision: 7,
  fields: [{ field: "__proto__", key: "original_under_score" }, { field: "binary", key: "bytes" }, { field: "empty", key: "zero" }] };
const fields = [{ field: "__proto__", encoding: "utf8" as const, value: "synthetic text" }, { field: "binary", encoding: "base64" as const, value: "AP8=" }, { field: "empty", encoding: "utf8" as const, value: "" }];
test("captured revisions stay frozen across background metadata changes", () => {
  const native = { resourceVersion: "100", head: 3 };
  const capture = captureRevision(path, native); native.resourceVersion = "101"; native.head = 4;
  assert.deepEqual(capture, { resourceVersion: "100", expectedHead: 3, pathRevision: 7 }); assert.equal(Object.isFrozen(capture), true);
});
test("action capture pauses on native or mapping change and outage; only fresh absence matches initial creation", () => {
  const native = { pathId: path.id, resourceVersion: "100", head: 3, adopted: true, tombstone: false, guardedAdoption: true };
  const capture = captureRevision(path, native);
  assert.equal(captureMatchesMetadata(capture, path, { ...native }, false), true);
  for (const changed of [{ ...native, resourceVersion: "101" }, { ...native, head: 4 }, { ...native, pathId: "other" }])
    assert.equal(captureMatchesMetadata(capture, path, changed, false), false);
  assert.equal(captureMatchesMetadata(capture, { ...path, revision: 8 }, native, false), false);
  assert.equal(captureMatchesMetadata(capture, path, undefined, false), false);
  assert.equal(captureMatchesMetadata(capture, path, undefined, true), false);
  const initial = captureRevision(path, { resourceVersion: "absent", head: 0 });
  assert.equal(captureMatchesMetadata(initial, path, undefined, true), true);
  assert.equal(captureMatchesMetadata(initial, path, undefined, false), false);
  assert.deepEqual(capture, { resourceVersion: "100", expectedHead: 3, pathRevision: 7 });
});

test("group drafts preserve special keys, binary bytes and original empty values; untouched save disabled", () => {
  const drafts = draftsFor(path, fields), unchanged = draftChange(drafts, fields);
  assert.equal(unchanged.changed, false); assert.equal(unchanged.error, ""); assert.deepEqual(unchanged.fields, fields);
  const missing = draftsFor(path, []); assert.equal(missing.every(row => !row.present), true);
  drafts[0].value = "";
  assert.match(draftChange(drafts, fields).error, /Confirm/);
  drafts[0].emptyConfirmed = true;
  assert.equal(draftChange(drafts, fields).changed, true); assert.equal(draftChange(drafts, fields).fields[0].value, "");
  drafts[1].present = false; assert.equal(draftChange(drafts, fields).fields.length, 2);
});
test("encoding conversion preserves exact bytes; rejects invalid base64, surrogates and binary UTF-8", () => {
  assert.equal(convertEncoding(fields[0], "base64"), Buffer.from(fields[0].value).toString("base64"));
  assert.equal(draftChange([{ ...fields[0], encoding: "base64", value: Buffer.from(fields[0].value).toString("base64"), present: true, emptyConfirmed: false }], [fields[0]]).changed, false);
  for (const value of ["a", "Zh==", "a===", "YWJj\n"]) assert.throws(() => canonicalBase64({ field: "x", encoding: "base64", value }));
  assert.throws(() => canonicalBase64({ field: "x", encoding: "utf8", value: "\ud800" }));
  assert.throws(() => convertEncoding(fields[1], "utf8"));
});
test("write-without-read drafts require complete explicit input and contain only metadata, never current values", () => {
  const drafts = replacementDrafts(path);
  assert.equal(drafts.every(draft => draft.present && draft.value === "" && !draft.emptyConfirmed), true);
  assert.match(draftChange(drafts, []).error, /Confirm/);
  drafts[0].value = "synthetic operator-entered replacement";
  drafts[1].encoding = "base64"; drafts[1].value = "AP8=";
  drafts[2].emptyConfirmed = true;
  const replacement = draftChange(drafts, []);
  assert.equal(replacement.changed, true); assert.equal(replacement.error, ""); assert.equal(replacement.fields.length, 3);
  drafts[2].present = false;
  assert.equal(draftChange(drafts, []).fields.length, 2);
  const capture = captureRevision(path, { resourceVersion: "100", head: 8 });
  assert.deepEqual(capture, { resourceVersion: "100", expectedHead: 8, pathRevision: 7 });
});
test("value cancellation fences late completion and a subsequent request remains independent", async () => {
  const fence = new ValueFence(), first = fence.begin(); let resolve!: (value: string) => void;
  const delayed = new Promise<string>(done => { resolve = done; }); let shown = "";
  const finished = delayed.then(value => { if (first.current()) shown = value; });
  fence.invalidate(); assert.equal(first.signal.aborted, true);
  const second = fence.begin(); resolve("synthetic delayed payload"); await finished;
  assert.equal(shown, ""); assert.equal(first.current(), false); assert.equal(second.current(), true);
  second.finish(); first.finish(); fence.invalidate(); assert.equal(second.current(), false);
});
test("bounded import parsing and errors never reflect value input", () => {
  const bundle = { format: "bortus-kv", version: 1, documents: [{ mountId: "mount", path: "apps/api", namespace: "apps", name: "original", mappings: path.fields, fields }] };
  assert.deepEqual(parseTransfer(JSON.stringify(bundle)), bundle);
  assert.throws(() => parseTransfer("synthetic-private-invalid-json"), error => error instanceof Error && !error.message.includes("synthetic-private"));
  assert.throws(() => parseTransfer(" ".repeat(1024 * 1024 + 1)), /one MiB/);
  assert.throws(() => parseTransfer(JSON.stringify({ ...bundle, documents: Array(101).fill(bundle.documents[0]) })), /100/);
  const oversized = draftChange([{ field: "x", value: "x".repeat(256 * 1024 + 1), encoding: "utf8", present: true, emptyConfirmed: true }], []);
  assert.match(oversized.error, /256/);
});
test("failed value responses are sanitized, use no-store and make no blind retry", async () => {
  const original = globalThis.fetch; let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls++; assert.equal(init?.cache, "no-store"); assert.equal(init?.credentials, "same-origin");
    return Response.json({ error: "synthetic private native body", operationId: "11111111-1111-1111-1111-111111111111", outcome: "conflict" }, { status: 409 });
  };
  try {
    await assert.rejects(workbenchRequest("/api/kv/paths/path/data", {}), error => error instanceof WorkbenchFailure && error.status === 409 && !error.message.includes("private") && error.outcome === "conflict");
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});
