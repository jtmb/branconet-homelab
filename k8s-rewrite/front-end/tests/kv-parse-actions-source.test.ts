// Exact parseActions SOURCE controls. Synthetic raw strings and inert immediate bindings only.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
import type * as TypeScript from "typescript";

const requireTool = createRequire(import.meta.url);
const ts = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT!) as typeof TypeScript;
const source = fs.readFileSync(path.resolve("src/lib/kv-contract.ts"), "utf8");
const file = ts.createSourceFile("kv-contract.ts", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const declaration = file.statements.find(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === "parseActions");
assert.ok(declaration && ts.isFunctionDeclaration(declaration));
assert.equal(declaration.parameters.length, 1);
assert.equal(declaration.parameters[0].type?.getText(file), "string");
assert.equal(declaration.type?.getText(file), "KvAction[]");
const selected = declaration.getText(file);
const compiled = ts.transpileModule(selected.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
const ACTIONS = ["list", "read", "create", "update", "delete", "rollback", "reconcile", "destroy", "export", "rotate"] as const;
const FIXED = "KV policy metadata unavailable";
class InertError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
function load(bindings: Record<string, unknown> = {}) {
  const context = vm.createContext({ JSON, Array, Set, KV_ACTIONS: ACTIONS, KvError: InertError, ...bindings });
  return vm.runInContext(compiled + "\nparseActions", context, { timeout: 1000 }) as (raw: string) => unknown;
}
function refuses(raw: string) {
  assert.throws(() => load()(raw), error => error instanceof InertError && error.status === 503 && error.message === FIXED);
}
for (const raw of ["", "[", "[\"read\",]", "undefined", "NaN", "null trailing", "{", "\uFEFF[]"])
  test(`malformed JSON refuses fixed503: ${JSON.stringify(raw)}`, () => refuses(raw));
for (const raw of ["null", "true", "false", "0", "1", '"read"', "{}", '{"0":"read","length":1}'])
  test(`nonarray refuses: ${raw}`, () => refuses(raw));
test("empty array refuses", () => refuses("[]"));
for (const entry of ["unknown", "READ", " read", "read ", "", null, {}, [], 1, true])
  test(`nonallowlisted item refuses: ${JSON.stringify(entry)}`, () => refuses(JSON.stringify([entry])));
test("adjacent duplicate refuses", () => refuses('["read","read"]'));
test("distant duplicate refuses", () => refuses('["read","list","read"]'));
test("eleven entries refuse", () => refuses(JSON.stringify([...ACTIONS, "list"])));
for (const action of ACTIONS)
  test(`singleton permits ${action}`, () => assert.equal(JSON.stringify(load()(JSON.stringify([action]))), JSON.stringify([action])));
for (const actions of [ACTIONS, [...ACTIONS].reverse(), ["rotate", "read", "list"]])
  test(`ordered valid result ${actions.join(",")}`, () => assert.equal(JSON.stringify(load()(JSON.stringify(actions))), JSON.stringify(actions)));
test("JSON whitespace and escaped spelling preserve parsed meaning", () => assert.equal(JSON.stringify(load()(' \n ["r\\u0065ad"] \t')), '["read"]'));
test("supported JSON arrays produce fresh results on separate calls", () => {
  const run = load(); const a = run('["read"]') as string[]; const b = run('["read"]') as string[];
  assert.notEqual(a, b); a.push("list"); assert.deepEqual(Array.from(b), ["read"]);
});
test("parse exception is replaced and its text is withheld", () => {
  const marker = new Error("synthetic parse detail");
  assert.throws(() => load({ JSON: { parse: () => { throw marker; } } })("synthetic raw"), error => error !== marker && error instanceof InertError && error.status === 503 && error.message === FIXED);
});
test("raw string is forwarded once; parsed identity is returned", () => {
  const result = ["read"]; const calls: string[] = [];
  const run = load({ JSON: { parse: (raw: string) => { calls.push(raw); return result; } } });
  assert.equal(run("synthetic raw"), result); assert.deepEqual(calls, ["synthetic raw"]);
});
function trace(value: unknown, include: (item: unknown) => boolean = item => ACTIONS.includes(item as typeof ACTIONS[number])) {
  const events: string[] = [];
  const wrapped = Array.isArray(value) ? new Proxy(value, { get(target, property, receiver) { events.push(`value.${String(property)}`); return Reflect.get(target, property, receiver); } }) : value;
  class ObservedSet extends Set<unknown> {
    constructor(items: Iterable<unknown>) { events.push("Set"); super(items); }
  }
  const allowlist = new Proxy(ACTIONS, { get(target, property, receiver) {
    events.push(`allowlist.${String(property)}`);
    if (property === "includes") return (item: unknown) => { events.push(`includes:${String(item)}`); return include(item); };
    return Reflect.get(target, property, receiver);
  } });
  const run = load({ JSON: { parse: (raw: string) => { events.push(`parse:${raw}`); return wrapped; } }, Array: { isArray: (item: unknown) => { events.push("isArray"); return Array.isArray(item); } }, Set: ObservedSet, KV_ACTIONS: allowlist });
  return { run: () => run("synthetic"), events, wrapped };
}
test("nonarray short-circuits every array and allowlist operation", () => {
  const t = trace({}); assert.throws(t.run, InertError); assert.deepEqual(t.events, ["parse:synthetic", "isArray"]);
});
test("empty array short-circuits after first length", () => {
  const t = trace([]); assert.throws(t.run, InertError); assert.deepEqual(t.events, ["parse:synthetic", "isArray", "value.length"]);
});
test("overflow short-circuits before some and Set", () => {
  const t = trace(Array(11).fill("read")); assert.throws(t.run, InertError);
  assert.deepEqual(t.events, ["parse:synthetic", "isArray", "value.length", "value.length", "allowlist.length"]);
});
test("allowlist completes before Set and parsed identity returns", () => {
  const t = trace(["read", "list"]); assert.equal(t.run(), t.wrapped);
  const seen = t.events.filter(e => e.startsWith("includes:")); assert.deepEqual(seen, ["includes:read", "includes:list"]);
  assert.ok(t.events.indexOf("Set") > t.events.indexOf("includes:list")); assert.equal(t.events.at(-1), "value.length");
});
test("unknown first item stops some and prevents Set", () => {
  const t = trace(["bad", "read"]); assert.throws(t.run, InertError);
  assert.deepEqual(t.events.filter(e => e.startsWith("includes:")), ["includes:bad"]); assert.ok(!t.events.includes("Set"));
});
test("duplicates complete allowlist before cardinality refusal", () => {
  const t = trace(["read", "read"]); assert.throws(t.run, InertError);
  assert.deepEqual(t.events.filter(e => e.startsWith("includes:")), ["includes:read", "includes:read"]); assert.ok(t.events.includes("Set"));
});
test("postparse includes exception propagates unchanged", () => {
  const marker = new Error("synthetic includes"); const t = trace(["read"], () => { throw marker; });
  assert.throws(t.run, error => error === marker); assert.ok(!t.events.includes("Set"));
});
test("postparse array guard exception propagates unchanged", () => {
  const marker = new Error("synthetic array guard");
  assert.throws(() => load({ JSON: { parse: () => ["read"] }, Array: { isArray: () => { throw marker; } } })("synthetic"), error => error === marker);
});
test("postparse Set exception propagates unchanged", () => {
  const marker = new Error("synthetic Set");
  class FailingSet { constructor() { throw marker; } }
  assert.throws(() => load({ JSON: { parse: () => ["read"] }, Set: FailingSet })("synthetic"), error => error === marker);
});
test("postparse element getter exception propagates unchanged", () => {
  const marker = new Error("synthetic getter"); const items: unknown[] = [];
  Object.defineProperty(items, "0", { get() { throw marker; } });
  assert.throws(() => load({ JSON: { parse: () => items } })("synthetic"), error => error === marker);
});
test("sparse inert parser result refuses through Set cardinality", () => {
  // JSON.parse cannot yield a hole; this characterizes JavaScript with an inert parser.
  const t = trace(new Array(2)); assert.throws(t.run, InertError); assert.ok(t.events.includes("Set"));
});
test("a failed call does not poison a later valid call", () => {
  const run = load(); assert.throws(() => run('["bad"]'), InertError); assert.equal(JSON.stringify(run('["read"]')), '["read"]');
});
test("refusals allocate distinct fixed error objects", () => {
  const run = load(); const errors: unknown[] = [];
  for (let n = 0; n < 2; n++) { try { run("[]"); } catch (error) { errors.push(error); } }
  assert.equal(errors.length, 2); assert.notEqual(errors[0], errors[1]);
});
