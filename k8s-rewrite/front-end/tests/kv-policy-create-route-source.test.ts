import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC policy-create POST SOURCE controls. Every actual import is inert.
// Only the selected callback executes: no HTTP/auth/body parsing/schema/registry/native/SQL.
type Model = Record<string, any>;
const path = "src/app/api/kv/policies/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) { return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} read`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } }); }
function deferred() {
  let resolve!: (v: any) => void, reject!: (e: any) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], bodies: Model[] = [], calls: Model[] = [];
  const actor = opaque("actor"), request = opaque("request"), schema = opaque("schema"), legacy = opaque("legacy"), field = opaque("field");
  const result = { public: "RESULT" }, getMarker = opaque("GET marker"), postMarker = opaque("POST marker"), fault = Error("PUBLIC-FAULT");
  const state: Model = { legacy, field, result, faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const input = Object.defineProperties({}, {
    legacyImpact: { enumerable: true, get() { step("legacy"); return state.legacy; } },
    publicField: { enumerable: true, get() { step("field"); return state.field; } }
  });
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); return state.result; };
  const registry = Object.defineProperty({}, "savePolicy", { get() { step("method"); return state.method; } });
  const body = function(this: unknown, ...args: unknown[]) { bodies.push({ receiver: this, args }); step("body"); return state.input; };
  Object.assign(state, { input, method, body, schema });
  const http = { kvHuman(...args: any[]) { wrappers.push(args); return wrappers.length === 1 ? getMarker : postMarker; }, get kvAdminMetadataBody() { step("body-get"); return state.body; } };
  const imports = new Proxy(http, { get(t, k, receiver) { assert.ok(k === "kvHuman" || k === "kvAdminMetadataBody"); return Reflect.get(t, k, receiver); } });
  const schemas = Object.defineProperty({}, "policyCreateRequest", { get() { step("schema-get"); return state.schema; } });
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[1][0];
  return { state, trace, wrappers, bodies, calls, actor, request, schema, legacy, field, input, method, body, registry, result, getMarker, postMarker, fault, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["body-get", "schema-get", "body", "legacy", "field", "method", "call"];
function exact(f: Fixture, registry: unknown = f.registry, actor: unknown = f.actor, request: unknown = f.request, schema: unknown = f.schema, legacy: unknown = f.legacy) {
  const b = f.bodies.at(-1)!, m = f.calls.at(-1)!;
  assert.equal(b.receiver, undefined); assert.equal(b.args.length, 4);
  assert.equal(b.args[0], registry); assert.equal(b.args[1], actor); assert.equal(b.args[2], request); assert.equal(b.args[3], schema);
  assert.equal(m.receiver, registry); assert.equal(m.args.length, 5);
  assert.equal(m.args[0], actor); assert.equal(m.args[2], undefined); assert.equal(m.args[3], undefined); assert.equal(m.args[4], legacy);
  const rest = m.args[1] as Model; assert.notEqual(rest, f.state.input); assert.equal(Object.hasOwn(rest, "legacyImpact"), false);
  return rest;
}
test("human policy-create POST exact asynchronous SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic POST201 and inert default GET wrappers", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.wrappers[0][0], "function"); assert.equal(f.exports.GET, f.getMarker);
    assert.equal(f.wrappers[1].length, 2); assert.equal(typeof f.callback, "function"); assert.equal(f.wrappers[1][1], 201); assert.equal(f.exports.POST, f.postMarker);
  });
  await t.test("body capture schema lookup await destructuring and exact save receiver arguments", async () => {
    const f = fixture(), pending = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.calls.length, 0);
    assert.equal(await pending, f.result); assert.deepEqual(f.trace, order); assert.equal(exact(f).publicField, f.field);
  });
  for (const [i, stage] of order.entries()) await t.test(`${stage} refusal preserves identity and stops later stages`, async () => {
    const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
    assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  for (const value of [undefined, null]) {
    await t.test(`nullish resolved input ${String(value)} refuses before save lookup`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); });
    await t.test(`nullish registry ${String(value)} is delegated to body before post-destructure refusal`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, order.slice(0, 5)); assert.equal(f.bodies[0].args[0], value); assert.equal(f.calls.length, 0); });
  }
  await t.test("missing registry actor request are passed as undefined before method refusal", async () => { const f = fixture(); await assert.rejects(f.callback(), isError); assert.equal(f.bodies[0].args.length, 4); assert.equal(f.bodies[0].args[0], undefined); assert.equal(f.bodies[0].args[1], undefined); assert.equal(f.bodies[0].args[2], undefined); assert.deepEqual(f.trace, order.slice(0, 5)); });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n]) {
    await t.test(`actor ${String(value)} is passed unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, value), f.result); assert.equal(f.bodies[0].args[1], value); assert.equal(f.calls[0].args[0], value); });
    await t.test(`request ${String(value)} is passed unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, value), f.result); assert.equal(f.bodies[0].args[2], value); });
    await t.test(`schema ${String(value)} is captured unchanged`, async () => { const f = fixture(); f.state.schema = value; assert.equal(await f.invoke(), f.result); assert.equal(f.bodies[0].args[3], value); });
    await t.test(`legacyImpact ${String(value)} is captured unchanged and excluded`, async () => { const f = fixture(); f.state.legacy = value; assert.equal(await f.invoke(), f.result); assert.equal(f.calls[0].args[4], value); assert.equal(Object.hasOwn(f.calls[0].args[1], "legacyImpact"), false); });
    await t.test(`save result ${String(value)} is asynchronously adopted`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  }
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable body ${String(value)} evaluates schema before refusal`, async () => { const f = fixture(); f.state.body = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); assert.equal(f.bodies.length, 0); });
    await t.test(`noncallable save ${String(value)} refuses only after destructuring`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.calls.length, 0); });
  }
  await t.test("schema refusal wins over noncallable captured body", async () => { const f = fixture(); f.state.body = null; f.state.faults["schema-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 2)); });
  await t.test("legacy refusal wins over nullish registry", async () => { const f = fixture(); f.state.faults.legacy = f.fault; await assert.rejects(f.invoke(null), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("rest getter refusal wins over noncallable save", async () => { const f = fixture(); f.state.method = null; f.state.faults.field = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 5)); });
  for (const stage of ["schema-get", "body"]) await t.test(`${stage} mutation cannot replace captured body`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.body = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("body getter can replace schema before schema lookup", async () => { const f = fixture(), replacement = opaque("fresh schema"); f.state.hooks["body-get"] = () => { f.state.schema = replacement; }; assert.equal(await f.invoke(), f.result); assert.equal(f.bodies[0].args[3], replacement); });
  for (const stage of ["legacy", "field"]) await t.test(`${stage} getter can replace save before its lookup`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.method = function(this: unknown, ...args: unknown[]) { f.calls.push({ receiver: this, args }); f.trace.push("replacement-call"); return f.result; }; }; assert.equal(await f.invoke(), f.result); assert.equal(f.trace.at(-1), "replacement-call"); exact(f); });
  await t.test("save getter captures method before later binding replacement", async () => { const f = fixture(); f.state.method = function(this: unknown, ...args: unknown[]) { f.state.method = null; f.calls.push({ receiver: this, args }); return f.result; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("legacy captured before rest getter changes current legacy", async () => { const f = fixture(); f.state.hooks.field = () => { f.state.legacy = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("inherited save method retains original registry receiver", async () => { const f = fixture(), r = Object.create(f.registry); assert.equal(await f.invoke(r), f.result); exact(f, r); });
  await t.test("inherited save getter observes original receiver", async () => { const f = fixture(); const proto = Object.defineProperty({}, "savePolicy", { get() { assert.equal(this, r); f.trace.push("method"); return f.method; } }); const r = Object.create(proto); assert.equal(await f.invoke(r), f.result); exact(f, r); });
  await t.test("registry proxy reads only savePolicy after rest", async () => { const f = fixture(); const r = new Proxy({}, { get(_t, k) { assert.equal(k, "savePolicy"); f.trace.push("method"); return f.method; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(r), f.result); exact(f, r); assert.deepEqual(f.trace, order); });
  await t.test("missing save property refuses after rest without fallback", async () => { const f = fixture(); await assert.rejects(f.invoke(Object.create(null)), isError); assert.deepEqual(f.trace, order.slice(0, 5)); });
  for (const value of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`primitive registry ${String(value)} is not normalized`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.equal(f.bodies[0].args[0], value); assert.deepEqual(f.trace, order.slice(0, 5)); });
  await t.test("inherited legacy is captured while inherited fields are excluded from rest", async () => { const f = fixture(); f.state.input = Object.assign(Object.create({ legacyImpact: f.legacy, inherited: f.field }), { own: f.field }); assert.equal(await f.invoke(), f.result); const rest = exact(f); assert.deepEqual(Reflect.ownKeys(rest), ["own"]); assert.equal(rest.own, f.field); });
  await t.test("missing legacy is passed undefined with a fresh empty rest", async () => { const f = fixture(); f.state.input = Object.create(null); assert.equal(await f.invoke(), f.result); assert.equal(f.calls[0].args[4], undefined); assert.deepEqual(Reflect.ownKeys(f.calls[0].args[1]), []); });
  await t.test("nonenumerable legacy is read but nonenumerable field is excluded", async () => { const f = fixture(); f.state.input = Object.defineProperties({}, { legacyImpact: { value: f.legacy }, hidden: { get() { throw f.fault; } } }); assert.equal(await f.invoke(), f.result); assert.deepEqual(Reflect.ownKeys(exact(f)), []); });
  await t.test("own enumerable strings symbols and integer keys retain order and value identity", async () => { const f = fixture(), symbol = Symbol("PUBLIC-field"), hidden = Symbol("PUBLIC-hidden"); const input = Object.create({ inherited: f.field }); Object.assign(input, { 2: f.field, 1: f.legacy, legacyImpact: f.legacy, plain: f.field, [symbol]: f.legacy }); Object.defineProperty(input, hidden, { get() { throw f.fault; } }); f.state.input = input; assert.equal(await f.invoke(), f.result); const rest = exact(f); assert.deepEqual(Reflect.ownKeys(rest), ["1", "2", "plain", symbol]); assert.equal(rest[symbol as any], f.legacy); assert.equal(rest.plain, f.field); });
  await t.test("rest uses data properties without retaining source accessors", async () => { const f = fixture(); assert.equal(await f.invoke(), f.result); const rest = exact(f), d = Object.getOwnPropertyDescriptor(rest, "publicField")!; assert.equal(d.value, f.field); assert.equal(d.get, undefined); assert.equal(d.writable, true); assert.equal(d.enumerable, true); assert.equal(d.configurable, true); assert.equal(Object.getPrototypeOf(Object.getPrototypeOf(rest)), null); });
  await t.test("own __proto__ copies as data without prototype mutation", async () => { const f = fixture(); const input = Object.create(null); Object.defineProperty(input, "__proto__", { value: f.field, enumerable: true }); input.legacyImpact = f.legacy; f.state.input = input; assert.equal(await f.invoke(), f.result); const rest = exact(f); assert.equal(Object.getOwnPropertyDescriptor(rest, "__proto__")!.value, f.field); assert.notEqual(Object.getPrototypeOf(rest), f.field); });
  await t.test("rest proxy observes legacy then ownKeys descriptors and enumerable getters", async () => { const f = fixture(), s = Symbol("PUBLIC"); const source = { legacyImpact: f.legacy, item: f.field, [s]: f.field }; const seen: PropertyKey[] = []; f.state.input = new Proxy(source, { get(t, k, r) { seen.push(k); return Reflect.get(t, k, r); }, ownKeys(t) { seen.push("OWNKEYS"); return Reflect.ownKeys(t); }, getOwnPropertyDescriptor(t, k) { seen.push(`DESC:${String(k)}`); return Reflect.getOwnPropertyDescriptor(t, k); } }); assert.equal(await f.invoke(), f.result); assert.deepEqual(seen, ["then", "legacyImpact", "OWNKEYS", "DESC:item", "item", "DESC:Symbol(PUBLIC)", s]); const rest = exact(f); assert.equal(rest.item, f.field); assert.equal(rest[s as any], f.field); });
  for (const stage of ["ownKeys", "descriptor", "get"]) await t.test(`rest proxy ${stage} refusal prevents save lookup`, async () => { const f = fixture(); f.state.input = new Proxy({ legacyImpact: f.legacy, item: f.field }, { get(t, k, r) { if (k === "item" && stage === "get") throw f.fault; return Reflect.get(t, k, r); }, ownKeys(t) { if (stage === "ownKeys") throw f.fault; return Reflect.ownKeys(t); }, getOwnPropertyDescriptor(t, k) { if (k === "item" && stage === "descriptor") throw f.fault; return Reflect.getOwnPropertyDescriptor(t, k); } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.calls.length, 0); });
  for (const value of [false, 0, 7, 3n, Symbol("PUBLIC"), "", "PUBLIC"]) await t.test(`resolved primitive input ${String(value)} retains object-rest semantics`, async () => { const f = fixture(); f.state.input = value; assert.equal(await f.invoke(), f.result); const rest = f.calls[0].args[1]; assert.equal(f.calls[0].args[4], undefined); const expected = Object.keys(Object(value)); assert.deepEqual(Reflect.ownKeys(rest), expected); for (const k of expected) assert.equal(rest[k], Object(value)[k]); });
  await t.test("pending body prevents legacy rest and save access until fulfilled", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 3)); d.resolve(f.input); assert.equal(await p, f.result); assert.equal(f.calls[0].args[4], f.legacy); assert.deepEqual(f.trace, order); });
  await t.test("rejected body prevents every input and save access", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("body then getter refusal is adopted without save lookup", async () => { const f = fixture(); f.state.input = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("body thenable resolves exact object before destructuring", async () => { const f = fixture(); const input = { legacyImpact: f.legacy, item: f.field }; f.state.input = { then(resolve: (v: any) => void) { resolve(input); } }; assert.equal(await f.invoke(), f.result); assert.equal(exact(f).item, f.field); });
  await t.test("legacy promise is passed raw without awaiting it", async () => { const f = fixture(), d = deferred(); f.state.legacy = d.promise; assert.equal(await f.invoke(), f.result); assert.equal(f.calls[0].args[4], d.promise); d.resolve(null); await d.promise; });
  await t.test("save result pending promise adopts exact resolved identity", async () => { const f = fixture(), d = deferred(), target = { public: "ADOPTED" }; f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 1); d.resolve(target); assert.equal(await p, target); });
  await t.test("save result rejection preserves exact reason", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); });
  await t.test("save thenable is adopted with its receiver", async () => { const f = fixture(), target = { public: "THENABLE" }; const v = { then(this: unknown, yes: (v: any) => void) { assert.equal(this, v); yes(target); } }; f.state.result = v; assert.equal(await f.invoke(), target); });
  await t.test("save result throwing then getter rejects with exact reason", async () => { const f = fixture(); f.state.result = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  await t.test("extra arguments and callback this are ignored", async () => { const f = fixture(); assert.equal(await f.callback.call(opaque("callback this"), f.registry, f.actor, f.request, opaque("extra")), f.result); exact(f); });
  await t.test("fresh calls reread body schema input legacy save and result without rest reuse", async () => { const f = fixture(); assert.equal(await f.invoke(), f.result); const first = f.calls[0].args[1]; const actor = opaque("fresh actor"), request = opaque("fresh request"), schema = opaque("fresh schema"), legacy = opaque("fresh legacy"), value = opaque("fresh field"), result = { public: "FRESH" }; const r = { savePolicy: f.method }; Object.assign(f.state, { schema, input: { legacyImpact: legacy, fresh: value }, result }); assert.equal(await f.invoke(r, actor, request), result); const rest = exact(f, r, actor, request, schema, legacy); assert.notEqual(rest, first); assert.equal(rest.fresh, value); assert.equal(f.bodies.length, 2); });
  for (const stage of order) await t.test(`refused ${stage} does not poison a fresh call`, async () => { const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults[stage]; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("interleaved pending bodies retain each actor request schema and own rest", async () => { const f = fixture(), first = deferred(), second = deferred(); f.state.input = first.promise; const p = f.invoke(); const actor = opaque("second actor"), request = opaque("second request"), schema = opaque("second schema"), legacy = opaque("second legacy"), value = opaque("second field"); const r = { savePolicy: f.method }; f.state.input = second.promise; f.state.schema = schema; const q = f.invoke(r, actor, request); second.resolve({ legacyImpact: legacy, item: value }); assert.equal(await q, f.result); assert.equal(f.calls[0].receiver, r); assert.equal(f.calls[0].args[0], actor); assert.equal(f.calls[0].args[4], legacy); first.resolve(f.input); assert.equal(await p, f.result); assert.equal(f.calls[1].receiver, f.registry); assert.equal(f.calls[1].args[0], f.actor); assert.equal(f.calls[1].args[4], f.legacy); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); assert.equal(f.bodies[0].args[3], f.schema); assert.equal(f.bodies[1].args[3], schema); });
  await t.test("interleaved pending save results preserve each resolved identity", async () => { const f = fixture(), first = deferred(), second = deferred(), a = { public: "FIRST" }, b = { public: "SECOND" }; f.state.result = first.promise; const p = f.invoke(); await Promise.resolve(); f.state.result = second.promise; const q = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 2); second.resolve(b); assert.equal(await q, b); first.resolve(a); assert.equal(await p, a); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); });
});
