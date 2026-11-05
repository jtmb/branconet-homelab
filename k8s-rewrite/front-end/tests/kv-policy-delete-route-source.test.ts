import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC DELETE SOURCE controls; actual imports and sibling PATCH stay inert.
type Model = Record<string, any>;
const path = "src/app/api/kv/policies/[id]/route.ts";
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
  const id = opaque("id"), revision = opaque("revision"), actor = opaque("actor"), request = opaque("request"), schema = opaque("schema"), legacy = opaque("legacy");
  const result = { public: "RESULT" }, patchMarker = opaque("PATCH marker"), deleteMarker = opaque("DELETE marker"), fault = Error("PUBLIC-FAULT");
  const state: Model = { id, revision, legacy, result, faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const params = Object.defineProperty({}, "id", { get() { step("id"); return state.id; } });
  const input = Object.defineProperties({}, {
    revision: { enumerable: true, get() { step("revision"); return state.revision; } },
    legacyImpact: { enumerable: true, get() { step("legacy"); return state.legacy; } },
    publicUnused: { enumerable: true, get() { throw fault; } },
    [Symbol("PUBLIC-unused")]: { enumerable: true, get() { throw fault; } }
  });
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); return state.result; };
  const registry = Object.defineProperty({}, "deletePolicy", { get() { step("method"); return state.method; } });
  const body = function(this: unknown, ...args: unknown[]) { bodies.push({ receiver: this, args }); step("body"); return state.input; };
  Object.assign(state, { input, method, body, schema });
  const http = { kvHuman(...args: any[]) { wrappers.push(args); return wrappers.length === 1 ? patchMarker : deleteMarker; }, get kvAdminMetadataBody() { step("body-get"); return state.body; } };
  const imports = new Proxy(http, { get(t, k, receiver) { assert.ok(k === "kvHuman" || k === "kvAdminMetadataBody"); return Reflect.get(t, k, receiver); } });
  const schemas = Object.defineProperty({}, "policyRemove", { get() { step("schema-get"); return state.schema; } });
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[1][0];
  return { id, revision, params, state, trace, wrappers, bodies, calls, actor, request, schema, legacy, input, method, body, registry, result, patchMarker, deleteMarker, fault, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["id", "body-get", "schema-get", "body", "revision", "legacy", "method", "call"];
function exact(f: Fixture, ...overrides: unknown[]) {
  const [registry, actor, request, schema, id, revision, legacy] = [f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.legacy].map((v, i) => i < overrides.length ? overrides[i] : v);
  const b = f.bodies.at(-1)!, m = f.calls.at(-1)!;
  assert.equal(b.receiver, undefined); assert.equal(b.args.length, 4);
  assert.equal(b.args[0], registry); assert.equal(b.args[1], actor); assert.equal(b.args[2], request); assert.equal(b.args[3], schema);
  assert.equal(m.receiver, registry); assert.equal(m.args.length, 4);
  assert.equal(m.args[0], actor); assert.equal(m.args[1], id); assert.equal(m.args[2], revision); assert.equal(m.args[3], legacy);
}
test("human policy-delete DELETE exact asynchronous SOURCE delegation", async t => {
  await t.test("nodejs default DELETE and inert PATCH wrappers without dynamic export", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "PATCH", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(Object.hasOwn(f.exports, "dynamic"), false);
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.wrappers[0][0], "function"); assert.equal(f.exports.PATCH, f.patchMarker);
    assert.equal(f.wrappers[1].length, 1); assert.equal(typeof f.callback, "function"); assert.equal(f.exports.DELETE, f.deleteMarker);
  });
  await t.test("entry capture body schema await selected fields and exact delete delegation", async () => {
    const f = fixture(), p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.calls.length, 0);
    assert.equal(await p, f.result); assert.deepEqual(f.trace, order); exact(f);
  });
  for (const [i, stage] of order.entries()) await t.test(`${stage} refusal preserves identity and stops later stages`, async () => {
    const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
    assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  for (const value of [undefined, null]) {
    await t.test(`nullish params ${String(value)} refuses before body access`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, value), isError); assert.deepEqual(f.trace, [] as string[]); });
    await t.test(`nullish input ${String(value)} refuses before delete lookup`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 4)); });
    await t.test(`nullish registry ${String(value)} reaches body before refusal`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.bodies[0].args[0], value); });
  }
  await t.test("missing fourth argument refuses before imports", async () => { const f = fixture(); await assert.rejects(f.callback(), isError); assert.deepEqual(f.trace, [] as string[]); });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n]) {
    await t.test(`actor ${String(value)} passes unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, value), f.result); exact(f, f.registry, value); });
    await t.test(`request ${String(value)} passes unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, value), f.result); exact(f, f.registry, f.actor, value); });
    await t.test(`schema ${String(value)} captured unchanged`, async () => { const f = fixture(); f.state.schema = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, value); });
    await t.test(`id ${String(value)} captured unread`, async () => { const f = fixture(); f.state.id = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, value); });
    await t.test(`revision ${String(value)} captured unread`, async () => { const f = fixture(); f.state.revision = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, value); });
    await t.test(`legacy ${String(value)} captured unread`, async () => { const f = fixture(); f.state.legacy = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, value); });
    await t.test(`result ${String(value)} asynchronously adopted`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  }
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable body ${String(value)} reads schema before refusal`, async () => { const f = fixture(); f.state.body = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.bodies.length, 0); });
    await t.test(`noncallable delete ${String(value)} refuses after selected destructuring`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 7)); assert.equal(f.calls.length, 0); });
  }
  await t.test("schema refusal wins over noncallable captured body", async () => { const f = fixture(); f.state.body = null; f.state.faults["schema-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("revision refusal wins over legacy and null registry", async () => { const f = fixture(); f.state.faults.revision = f.fault; f.state.faults.legacy = Error("PUBLIC-LATER"); await assert.rejects(f.invoke(null), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 5)); });
  await t.test("legacy refusal wins over noncallable delete", async () => { const f = fixture(); f.state.faults.legacy = f.fault; f.state.method = null; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 6)); });
  for (const stage of ["schema-get", "body"]) await t.test(`${stage} cannot replace captured body`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.body = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("body getter can replace schema before lookup", async () => { const f = fixture(), schema = opaque("replacement schema"); f.state.hooks["body-get"] = () => { f.state.schema = schema; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, schema); });
  await t.test("id getter can replace body before capture", async () => { const f = fixture(); f.state.hooks.id = () => { f.state.body = function(...args: unknown[]) { f.bodies.push({ receiver: undefined, args }); f.trace.push("body"); return f.input; }; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const stage of ["body-get", "schema-get", "body", "revision", "legacy", "method"]) await t.test(`${stage} cannot replace already captured id`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.id = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const stage of ["revision", "legacy"]) await t.test(`${stage} can replace delete before lookup`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.method = function(this: unknown, ...args: unknown[]) { f.calls.push({ receiver: this, args }); f.trace.push("replacement-call"); return f.result; }; }; assert.equal(await f.invoke(), f.result); exact(f); assert.equal(f.trace.at(-1), "replacement-call"); });
  await t.test("legacy mutation cannot replace captured revision", async () => { const f = fixture(); f.state.hooks.legacy = () => { f.state.revision = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("method lookup mutation cannot replace captured revision or legacy", async () => { const f = fixture(); f.state.hooks.method = () => { f.state.revision = null; f.state.legacy = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("delete method is captured before replacement on call", async () => { const f = fixture(); f.state.method = function(this: unknown, ...args: unknown[]) { f.state.method = null; f.calls.push({ receiver: this, args }); return f.result; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("inherited method retains registry receiver", async () => { const f = fixture(), registry = Object.create(f.registry); assert.equal(await f.invoke(registry), f.result); exact(f, registry); });
  await t.test("inherited method getter sees original registry", async () => { const f = fixture(); const proto = Object.defineProperty({}, "deletePolicy", { get() { assert.equal(this, registry); return f.method; } }); const registry = Object.create(proto); assert.equal(await f.invoke(registry), f.result); exact(f, registry); });
  await t.test("registry proxy reads only deletePolicy without enumeration", async () => { const f = fixture(); const registry = new Proxy({}, { get(_t, key) { assert.equal(key, "deletePolicy"); return f.method; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(registry), f.result); exact(f, registry); });
  await t.test("missing method refuses without fallback", async () => { const f = fixture(); await assert.rejects(f.invoke(Object.create(null)), isError); assert.deepEqual(f.trace, order.slice(0, 6)); });
  for (const value of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`primitive registry ${String(value)} is not normalized`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.bodies[0].args[0], value); });
  for (const params of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n, {}, Object.create(null)]) await t.test(`missing id on ${Object.prototype.toString.call(params)} passes undefined`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f, f.registry, f.actor, f.request, f.schema, undefined); assert.deepEqual(f.trace, order.slice(1)); });
  await t.test("inherited id getter sees params receiver", async () => { const f = fixture(); let receiver: unknown; const params = Object.create(Object.defineProperty({}, "id", { get() { receiver = this; return f.id; } })); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); assert.equal(receiver, params); exact(f); });
  await t.test("params proxy reads exactly id and never enumerates", async () => { const f = fixture(); const params = new Proxy({}, { get(_t, k) { assert.equal(k, "id"); return f.id; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f); });
  await t.test("id refusal wins over body refusal", async () => { const f = fixture(); f.state.faults.id = f.fault; f.state.faults["body-get"] = Error("PUBLIC-LATER"); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, ["id"]); });
  await t.test("inherited selected fields retain identities", async () => { const f = fixture(); f.state.input = Object.create({ revision: f.revision, legacyImpact: f.legacy }); assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("nonenumerable selected fields are read", async () => { const f = fixture(); f.state.input = Object.defineProperties({}, { revision: { value: f.revision }, legacyImpact: { value: f.legacy } }); assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("missing fields pass undefined without normalization", async () => { const f = fixture(); f.state.input = Object.create(null); assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, undefined, undefined); });
  await t.test("inherited selected getters receive original input", async () => { const f = fixture(); const input = Object.create(Object.defineProperties({}, { revision: { get() { assert.equal(this, input); return f.revision; } }, legacyImpact: { get() { assert.equal(this, input); return f.legacy; } } })); f.state.input = input; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("input proxy reads then revision legacy only and never enumerates or reads symbols", async () => {
    const f = fixture(), seen: PropertyKey[] = [];
    f.state.input = new Proxy({}, { get(_t, key) { seen.push(key); if (key === "then") return undefined; if (key === "revision") return f.revision; if (key === "legacyImpact") return f.legacy; throw f.fault; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } });
    assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(seen, ["then", "revision", "legacyImpact"]);
  });
  for (const value of [false, 0, 7, 3n, Symbol("PUBLIC"), "", "PUBLIC"]) await t.test(`primitive input ${String(value)} selects missing fields`, async () => { const f = fixture(); f.state.input = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, undefined, undefined); });
  await t.test("pending body prevents field and method reads", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 4)); d.resolve(f.input); assert.equal(await p, f.result); exact(f); });
  await t.test("body rejection preserves reason without field or method reads", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("body throwing then getter refuses before field reads", async () => { const f = fixture(); f.state.input = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("body thenable resolves exact input with receiver preserved", async () => { const f = fixture(); const v = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, v); yes(f.input); } }; f.state.input = v; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const key of ["id", "revision", "legacy"] as const) await t.test(`${key} promise is passed raw without awaiting`, async () => { const f = fixture(), d = deferred(); f.state[key] = d.promise; assert.equal(await f.invoke(), f.result); const index = { id: 1, revision: 2, legacy: 3 }[key]; assert.equal(f.calls[0].args[index], d.promise); d.resolve(null); await d.promise; });
  await t.test("pending delete result adopts exact resolved identity", async () => { const f = fixture(), d = deferred(), target = { public: "ADOPTED" }; f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 1); d.resolve(target); assert.equal(await p, target); });
  await t.test("delete result rejection preserves reason", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); });
  await t.test("result thenable receiver and identity adopted", async () => { const f = fixture(), target = { public: "THENABLE" }; const v = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, v); yes(target); } }; f.state.result = v; assert.equal(await f.invoke(), target); });
  await t.test("result throwing then getter preserves reason", async () => { const f = fixture(); f.state.result = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  await t.test("extra arguments and callback this stay unread", async () => { const f = fixture(); assert.equal(await f.callback.call(opaque("this"), f.registry, f.actor, f.request, f.params, opaque("extra")), f.result); exact(f); });
  await t.test("fresh calls reread body schema method and selected fields", async () => { const f = fixture(); await f.invoke(); const id = opaque("new id"), revision = opaque("new revision"), legacy = opaque("new legacy"), actor = opaque("new actor"), request = opaque("new request"), schema = opaque("new schema"), result = { public: "NEW" }, registry = { deletePolicy: f.method }; Object.assign(f.state, { input: { revision, legacyImpact: legacy }, schema, result }); assert.equal(await f.invoke(registry, actor, request, { id }), result); exact(f, registry, actor, request, schema, id, revision, legacy); assert.equal(f.bodies.length, 2); });
  for (const stage of order) await t.test(`refused ${stage} does not poison fresh call`, async () => { const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults[stage]; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("interleaved bodies retain independent receivers actors requests schemas ids and fields", async () => { const f = fixture(), one = deferred(), two = deferred(); f.state.input = one.promise; const p = f.invoke(); const actor = opaque("two actor"), request = opaque("two request"), schema = opaque("two schema"), id = opaque("two id"), revision = opaque("two revision"), legacy = opaque("two legacy"), registry = { deletePolicy: f.method }; Object.assign(f.state, { input: two.promise, schema }); const q = f.invoke(registry, actor, request, { id }); two.resolve({ revision, legacyImpact: legacy }); assert.equal(await q, f.result); exact(f, registry, actor, request, schema, id, revision, legacy); one.resolve(f.input); assert.equal(await p, f.result); assert.equal(f.calls[1].receiver, f.registry); assert.deepEqual(f.calls[1].args, [f.actor, f.id, f.revision, f.legacy]); assert.equal(f.bodies[0].args[3], f.schema); assert.equal(f.bodies[1].args[3], schema); });
  await t.test("interleaved results preserve independent adopted identities", async () => { const f = fixture(), one = deferred(), two = deferred(), a = { public: "ONE" }, b = { public: "TWO" }; f.state.result = one.promise; const p = f.invoke(); await Promise.resolve(); f.state.result = two.promise; const q = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 2); two.resolve(b); assert.equal(await q, b); one.resolve(a); assert.equal(await p, a); });
});
