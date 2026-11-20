import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire, stripTypeScriptTypes } from "node:module";
import vm from "node:vm";
import test from "node:test";

// PUBLIC SOURCE ONLY. Extract one declaration; never import application modules.
const requireTool = createRequire(import.meta.url);
const ts = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const file = path.resolve("src/lib/kv-metadata-query.ts");
const raw = fs.readFileSync(file, "utf8");
const ast = ts.createSourceFile(file, raw, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((s: { name?: { text: string } }) => s.name?.text === "isKvMetadataQuery");
assert.equal(declarations.length, 1);
assert.ok(ts.isFunctionDeclaration(declarations[0]));
const selected = stripTypeScriptTypes(declarations[0].getText(ast).replace(/^export\s+/, ""));
type Classifier = (url: string) => boolean;
function isolated(URLBinding: unknown = URL): Classifier {
  return vm.runInNewContext(`"use strict"; ${selected}; isKvMetadataQuery`, { URL: URLBinding }, { timeout: 1000 });
}
const id = "12345678-abcd-1234-abcd-123456789abc";
const detail = `/api/kv/paths/${id}`;
const cases: Array<[string, string, boolean]> = [];
for (const collection of ["mounts", "paths", "policies", "identities", "audit"]) {
  const u = `/api/kv/${collection}`;
  cases.push([`${collection} bare`, u, true], [`${collection} cursor`, `${u}?cursor=synthetic`, true],
    [`${collection} duplicate`, `${u}?cursor=a&cursor=b`, false], [`${collection} unknown`, `${u}?secret=synthetic`, false],
    [`${collection} fragment`, `${u}#synthetic`, false]);
}
cases.push(
  ["paths mount scope", "/api/kv/paths?mountId=synthetic&cursor=x", true],
  ["audit three keys", "/api/kv/audit?operationId=x&cursor=y&pathId=z", true],
  ["paths duplicate mount", "/api/kv/paths?mountId=x&mountId=x", false],
  ["audit duplicate operation", "/api/kv/audit?operationId=x&operationId=y", false],
  ["mounts scope refused", "/api/kv/mounts?mountId=x", false],
  ["encoded allowed key", "/api/kv/paths?%63ursor=x", true],
  ["encoded duplicate", "/api/kv/paths?cursor=x&%63ursor=y", false],
  ["empty key refused", "/api/kv/paths?=x", false],
  ["case sensitive key", "/api/kv/paths?Cursor=x", false],
  ["empty cursor is metadata", "/api/kv/paths?cursor=", true],
  ["values are not interpreted", "/api/kv/paths?cursor=a%26secret%3Db", true],
  ["blank query", "/api/kv/paths?", true],
  ["empty fragment", "/api/kv/paths#", true],
  ["plus key refused", "/api/kv/paths?cur+sor=x", false],
);
for (const suffix of ["", "/status", "/capabilities", "/versions"]) {
  cases.push([`detail ${suffix || "bare"}`, detail + suffix, true],
    [`detail query ${suffix || "bare"}`, `${detail}${suffix}?cursor=x`, false]);
}
for (const suffix of ["/data", "/versions/1/data", "/rollback", "/reconcile", "/destroy", "/adopt", "/rotations", "/operations"]) {
  cases.push([`private suffix ${suffix}`, detail + suffix, false]);
}
cases.push(
  ["uppercase detail after fixed prefix", detail.replace("paths", "PATHS").toUpperCase().replace("/API/KV/", "/api/kv/"), true],
  ["upper prefix refused", "/API/KV/paths", false],
  ["absolute URL refused", "https://bortus.invalid/api/kv/paths", false],
  ["protocol relative refused", "//bortus.invalid/api/kv/paths", false],
  ["wrong route refused", "/api/kv-other/paths", false],
  ["empty refused", "", false],
  ["leading whitespace refused", " /api/kv/paths", false],
  ["trailing slash refused", "/api/kv/paths/", false],
  ["short uuid refused", "/api/kv/paths/1234/status", false],
  ["nonhex uuid refused", detail.replace("12345678", "g2345678"), false],
  ["detail trailing slash refused", detail + "/", false],
  ["dot normalization refused", "/api/kv/mounts/../paths", false],
  ["encoded dot normalization refused", "/api/kv/mounts/%2e%2e/paths", false],
  ["backslash normalization refused", "/api/kv/paths\\..\\mounts", false],
  ["newline normalization refused", "/api/kv/pa\nths", false],
  ["encoded route refused", "/api/kv/%70aths", false],
  ["encoded separator refused", "/api/kv/paths%2f" + id, false],
  ["operation route refused", "/api/kv/operations/" + id, false],
  ["automation refused", "/api/kv/automation", false],
  ["native metadata refused", "/api/kv/native", false],
  ["collection case refused", "/api/kv/PATHS", false],
  ["detail blank query", detail + "?", true],
  ["detail empty fragment", detail + "#", true],
  ["detail fragment refused", detail + "#x", false],
);
for (const [label, input, expected] of cases) test(label, () => assert.equal(isolated()(input), expected));

test("prefix refusal precedes URL construction", () => {
  let calls = 0;
  function FaultURL() { calls++; throw new Error("synthetic constructor"); }
  assert.equal(isolated(FaultURL)("/other"), false);
  assert.equal(calls, 0);
});
test("constructor receives only URL metadata and fixed base", () => {
  const calls: unknown[][] = [];
  function SpyURL(input: string, base: string) { calls.push([input, base]); return new URL(input, base); }
  assert.equal(isolated(SpyURL)("/api/kv/paths"), true);
  assert.deepEqual(calls, [["/api/kv/paths", "https://bortus.invalid"]]);
});
test("constructor fault propagates before split", () => {
  const marker = new Error("synthetic constructor");
  function FaultURL() { throw marker; }
  assert.throws(() => isolated(FaultURL)("/api/kv/paths"), e => e === marker);
});
test("pathname mismatch refuses before hash or queries", () => {
  const events: string[] = [];
  function StubURL() { return { get pathname() { events.push("pathname"); return "/other"; },
    get hash() { throw new Error("unexpected hash"); }, get searchParams() { throw new Error("unexpected params"); } }; }
  assert.equal(isolated(StubURL)("/api/kv/paths"), false);
  assert.deepEqual(events, ["pathname"]);
});
test("hash refusal precedes collection lookup", () => {
  const events: string[] = [];
  function StubURL() { return { get pathname() { events.push("pathname"); return "/api/kv/paths"; },
    get hash() { events.push("hash"); return "#x"; }, get searchParams() { throw new Error("unexpected params"); } }; }
  assert.equal(isolated(StubURL)("/api/kv/paths"), false);
  assert.deepEqual(events, ["pathname", "hash"]);
});
test("collection consumes keys before membership and shortcircuits unknown key", () => {
  const events: string[] = [];
  function StubURL() { return { pathname: "/api/kv/paths", hash: "", searchParams: {
    *keys() { events.push("keys:start"); yield "unknown"; events.push("keys:next"); yield "cursor"; events.push("keys:end"); },
    getAll() { throw new Error("unexpected getAll"); },
  } }; }
  assert.equal(isolated(StubURL)("/api/kv/paths"), false);
  assert.deepEqual(events, ["keys:start", "keys:next", "keys:end"]);
});
test("collection checks each allowed key count in order", () => {
  const events: string[] = [];
  function StubURL() { return { pathname: "/api/kv/paths", hash: "", searchParams: {
    keys() { events.push("keys"); return ["cursor", "mountId"]; },
    getAll(key: string) { events.push(key); return ["inert"]; },
  } }; }
  assert.equal(isolated(StubURL)("/api/kv/paths"), true);
  assert.deepEqual(events, ["keys", "cursor", "mountId"]);
});
test("duplicate count shortcircuits later key checks", () => {
  const events: string[] = [];
  function StubURL() { return { pathname: "/api/kv/paths", hash: "", searchParams: {
    keys() { return ["cursor", "mountId"]; }, getAll(key: string) { events.push(key); return ["a", "b"]; },
  } }; }
  assert.equal(isolated(StubURL)("/api/kv/paths"), false);
  assert.deepEqual(events, ["cursor"]);
});
test("non-detail regex refusal avoids searchParams access", () => {
  function StubURL() { return { pathname: "/api/kv/nope", hash: "", get searchParams() { throw new Error("unexpected params"); } }; }
  assert.equal(isolated(StubURL)("/api/kv/nope"), false);
});
test("detail consumes entries rather than collection methods", () => {
  let consumed = 0;
  function StubURL() { return { pathname: detail, hash: "", searchParams: {
    *[Symbol.iterator]() { consumed++; yield ["inert", "metadata"]; consumed++; },
    keys() { throw new Error("unexpected keys"); }, getAll() { throw new Error("unexpected getAll"); },
  } }; }
  assert.equal(isolated(StubURL)(detail), false);
  assert.equal(consumed, 2);
});
test("fresh calls repeat construction without cached verdict", () => {
  let count = 0;
  function StubURL(input: string, base: string) { count++; return new URL(input, base); }
  const run = isolated(StubURL);
  assert.equal(run("/api/kv/paths"), true); assert.equal(run("/api/kv/paths?secret=x"), false);
  assert.equal(run("/api/kv/paths"), true); assert.equal(count, 3);
});
test("synthetic keys iterator fault is propagated unchanged", () => {
  const marker = new Error("synthetic iterator");
  function StubURL() { return { pathname: "/api/kv/paths", hash: "", searchParams: { *keys() { yield "cursor"; throw marker; } } }; }
  assert.throws(() => isolated(StubURL)("/api/kv/paths"), e => e === marker);
});
test("synthetic getAll fault is propagated unchanged", () => {
  const marker = new Error("synthetic getAll");
  function StubURL() { return { pathname: "/api/kv/paths", hash: "", searchParams: { keys() { return ["cursor"]; }, getAll() { throw marker; } } }; }
  assert.throws(() => isolated(StubURL)("/api/kv/paths"), e => e === marker);
});
