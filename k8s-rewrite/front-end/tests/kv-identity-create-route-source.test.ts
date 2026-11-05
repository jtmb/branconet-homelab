import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC identity-create POST SOURCE controls; every actual import is inert.
// Date is a modeled constructor. No real date parsing, HTTP, schema, registry or SQL executes.
type Model = Record<string, any>;
const path = "src/app/api/kv/identities/route.ts";
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
  const trace: string[] = [], wrappers: any[][] = [], bodies: Model[] = [], calls: Model[] = [], dates: Model[] = [];
  const actor = opaque("actor"), request = opaque("request"), schema = opaque("schema"), expiry = opaque("expiry"), field = opaque("field"), constructed = opaque("constructed date");
  const result = { public: "RESULT" }, getMarker = opaque("GET marker"), postMarker = opaque("POST marker"), fault = Error("PUBLIC-FAULT");
  const state: Model = { expiry, field, constructed, result, faults: {}, hooks: {}, reads: 0 };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const input = Object.defineProperties({}, {
    expiresAt: { enumerable: true, get() { step(state.reads++ % 2 === 0 ? "spread-expiry" : "expiry"); return state.expiry; } },
    publicField: { enumerable: true, get() { step("field"); return state.field; } }
  });
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); return state.result; };
  const registry = Object.defineProperty({}, "issueIdentity", { get() { step("method"); return state.method; } });
  const body = function(this: unknown, ...args: unknown[]) { bodies.push({ receiver: this, args }); step("body"); return state.input; };
  const DateModel = function(this: unknown, ...args: unknown[]) { dates.push({ args, target: new.target }); step("date-new"); return state.constructed; };
  Object.assign(state, { input, method, body, schema, date: DateModel });
  const http = { kvHuman(...args: any[]) { wrappers.push(args); return wrappers.length === 1 ? getMarker : postMarker; }, get kvBody() { step("body-get"); return state.body; } };
  const imports = new Proxy(http, { get(t, k, receiver) { assert.ok(k === "kvHuman" || k === "kvBody"); return Reflect.get(t, k, receiver); } });
  const schemas = Object.defineProperty({}, "identityCreate", { get() { step("schema-get"); return state.schema; } });
  const m = { exports: {} as Model };
  const context = { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } };
  Object.defineProperty(context, "Date", { get() { step("date-get"); return state.date; } });
  runInNewContext(compiled, context, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[1][0];
  return { state, trace, wrappers, bodies, calls, dates, actor, request, schema, expiry, field, input, method, body, DateModel, registry, constructed, result, getMarker, postMarker, fault, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["body-get", "schema-get", "body", "method", "spread-expiry", "field", "date-get", "expiry", "date-new", "call"];
function exact(f: Fixture, ...values: unknown[]) {
  const registry = values.length > 0 ? values[0] : f.registry, actor = values.length > 1 ? values[1] : f.actor;
  const request = values.length > 2 ? values[2] : f.request, schema = values.length > 3 ? values[3] : f.schema, expiry = values.length > 4 ? values[4] : f.expiry;
  const b = f.bodies.at(-1)!, m = f.calls.at(-1)!, d = f.dates.at(-1)!;
  assert.equal(b.receiver, undefined); assert.equal(b.args.length, 2); assert.equal(b.args[0], request); assert.equal(b.args[1], schema);
  assert.equal(m.receiver, registry); assert.equal(m.args.length, 2); assert.equal(m.args[0], actor);
  assert.equal(d.args.length, 1); assert.equal(d.args[0], expiry); assert.equal(d.target, f.DateModel);
  const output = m.args[1] as Model; assert.notEqual(output, f.state.input); assert.equal(output.expiresAt, f.state.constructed);
  return output;
}
test("human identity-create POST exact asynchronous SOURCE delegation", async t => {
  await t.test("exact nodejs force-dynamic inert default GET and POST201 wrappers", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.wrappers[0][0], "function"); assert.equal(f.exports.GET, f.getMarker);
    assert.equal(f.wrappers[1].length, 2); assert.equal(typeof f.callback, "function"); assert.equal(f.wrappers[1][1], 201); assert.equal(f.exports.POST, f.postMarker);
  });
  await t.test("body schema await method spread Date expiry construction call exact order", async () => {
    const f = fixture(), p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.calls.length, 0);
    assert.equal(await p, f.result); assert.deepEqual(f.trace, order); assert.equal(exact(f).publicField, f.field);
  });
  for (const [i, stage] of order.entries()) await t.test(`${stage} refusal retains exact reason and stops later work`, async () => {
    const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
    assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n]) {
    await t.test(`actor ${String(value)} passes unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, value), f.result); exact(f, f.registry, value); });
    await t.test(`request ${String(value)} passes unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, value), f.result); exact(f, f.registry, f.actor, value); });
    await t.test(`schema ${String(value)} is captured unchanged`, async () => { const f = fixture(); f.state.schema = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, value); });
    await t.test(`expiry ${String(value)} is passed to modeled Date without parsing`, async () => { const f = fixture(); f.state.expiry = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, value); });
    await t.test(`issue result ${String(value)} is adopted unchanged`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  }
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable body ${String(value)} still evaluates schema first`, async () => { const f = fixture(); f.state.body = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); assert.equal(f.bodies.length, 0); });
    await t.test(`noncallable method ${String(value)} refuses after spread and modeled Date`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 9)); assert.equal(f.calls.length, 0); });
    await t.test(`nonconstructor Date ${String(value)} evaluates expiry before refusal`, async () => { const f = fixture(); f.state.date = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 8)); assert.equal(f.dates.length, 0); });
  }
  for (const value of [undefined, null]) {
    await t.test(`nullish registry ${String(value)} refuses after body await before spread`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.dates.length, 0); });
    await t.test(`nullish input ${String(value)} spreads empty then refuses expiry after Date lookup`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, ["body-get", "schema-get", "body", "method", "date-get"]); assert.equal(f.dates.length, 0); });
  }
  await t.test("missing arguments preserve undefined request actor and registry refusal", async () => { const f = fixture(); await assert.rejects(f.callback(), isError); assert.equal(f.bodies[0].args.length, 2); assert.equal(f.bodies[0].args[0], undefined); assert.equal(f.bodies[0].args[1], f.schema); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("schema refusal wins over noncallable captured body", async () => { const f = fixture(); f.state.body = null; f.state.faults["schema-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 2)); });
  await t.test("method getter refusal wins over spread getter refusal", async () => { const f = fixture(); f.state.faults.method = f.fault; f.state.faults["spread-expiry"] = Error("PUBLIC-later"); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("spread refusal wins over noncallable captured method", async () => { const f = fixture(); f.state.method = null; f.state.faults.field = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 6)); });
  await t.test("expiry refusal wins over nonconstructor Date", async () => { const f = fixture(); f.state.date = null; f.state.faults.expiry = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 8)); });
  for (const stage of ["schema-get", "body"]) await t.test(`${stage} cannot replace captured body`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.body = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("body getter may replace schema before its lookup", async () => { const f = fixture(), s = opaque("new schema"); f.state.hooks["body-get"] = () => { f.state.schema = s; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, s); });
  for (const stage of ["spread-expiry", "field", "date-get", "expiry", "date-new"]) await t.test(`${stage} cannot replace already captured issue method`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.method = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("spread getter mutation affects later expiry read and only fresh expiresAt is overridden", async () => { const f = fixture(), later = opaque("later expiry"); f.state.hooks.field = () => { f.state.expiry = later; }; assert.equal(await f.invoke(), f.result); const output = exact(f, f.registry, f.actor, f.request, f.schema, later); assert.equal(output.publicField, f.field); assert.equal(f.state.reads, 2); });
  await t.test("Date lookup can mutate expiry before its second read", async () => { const f = fixture(), later = opaque("Date lookup expiry"); f.state.hooks["date-get"] = () => { f.state.expiry = later; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, later); });
  await t.test("expiry getter cannot replace captured Date constructor", async () => { const f = fixture(); f.state.hooks.expiry = () => { f.state.date = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("arrow Date model refuses construction after expiry read without execution", async () => { const f = fixture(); f.state.date = () => { throw f.fault; }; await assert.rejects(f.invoke(), e => isError(e) && e !== f.fault); assert.deepEqual(f.trace, order.slice(0, 8)); });
  await t.test("inherited issue getter observes original registry receiver", async () => { const f = fixture(); const proto = Object.defineProperty({}, "issueIdentity", { get() { assert.equal(this, r); f.trace.push("method"); return f.method; } }); const r = Object.create(proto); assert.equal(await f.invoke(r), f.result); exact(f, r); });
  await t.test("registry proxy reads only issueIdentity", async () => { const f = fixture(); const r = new Proxy({}, { get(_t, k) { assert.equal(k, "issueIdentity"); f.trace.push("method"); return f.method; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(r), f.result); exact(f, r); });
  await t.test("missing method still spreads and constructs before call refusal", async () => { const f = fixture(); await assert.rejects(f.invoke(Object.create(null)), isError); assert.deepEqual(f.trace, order.filter(x => x !== "method" && x !== "call")); assert.equal(f.dates.length, 1); });
  for (const value of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`primitive registry ${String(value)} is not normalized`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.equal(f.dates.length, 1); assert.equal(f.calls.length, 0); });
  await t.test("inherited expiry is read once after spread and inherited siblings remain unread", async () => { const f = fixture(); const proto = Object.defineProperties({}, { expiresAt: { get() { f.trace.push("inherited-expiry"); return f.expiry; } }, inherited: { get() { throw f.fault; } } }); f.state.input = Object.assign(Object.create(proto), { own: f.field }); assert.equal(await f.invoke(), f.result); const output = exact(f); assert.deepEqual(Reflect.ownKeys(output), ["own", "expiresAt"]); assert.equal(output.own, f.field); });
  await t.test("missing expiry passes undefined to Date and adds fresh own expiresAt", async () => { const f = fixture(); f.state.input = Object.create(null); assert.equal(await f.invoke(), f.result); assert.deepEqual(Reflect.ownKeys(exact(f, f.registry, f.actor, f.request, f.schema, undefined)), ["expiresAt"]); });
  await t.test("nonenumerable expiry is still read while hidden unrelated fields stay unread", async () => { const f = fixture(); f.state.input = Object.defineProperties({}, { expiresAt: { value: f.expiry }, hidden: { get() { throw f.fault; } } }); assert.equal(await f.invoke(), f.result); assert.deepEqual(Reflect.ownKeys(exact(f)), ["expiresAt"]); });
  await t.test("own enumerable integer string and symbol fields retain order and raw identity", async () => { const f = fixture(), symbol = Symbol("PUBLIC-field"), hidden = Symbol("PUBLIC-hidden"); const input = Object.create({ inherited: f.field }); Object.assign(input, { 2: f.field, 1: f.expiry, expiresAt: f.expiry, plain: f.field, [symbol]: f.expiry }); Object.defineProperty(input, hidden, { get() { throw f.fault; } }); f.state.input = input; assert.equal(await f.invoke(), f.result); const output = exact(f); assert.deepEqual(Reflect.ownKeys(output), ["1", "2", "expiresAt", "plain", symbol]); assert.equal(output[symbol as any], f.expiry); assert.equal(output.plain, f.field); });
  await t.test("spread produces fresh data properties without retaining accessors", async () => { const f = fixture(); assert.equal(await f.invoke(), f.result); const output = exact(f); for (const key of ["publicField", "expiresAt"]) { const d = Object.getOwnPropertyDescriptor(output, key)!; assert.equal(d.get, undefined); assert.equal(d.writable, true); assert.equal(d.enumerable, true); assert.equal(d.configurable, true); } assert.equal(Object.getPrototypeOf(Object.getPrototypeOf(output)), null); assert.notEqual(Object.getPrototypeOf(output), Object.getPrototypeOf(f.input)); });
  await t.test("own __proto__ is copied as data without prototype mutation", async () => { const f = fixture(); const input = Object.create(null); Object.defineProperty(input, "__proto__", { value: f.field, enumerable: true }); input.expiresAt = f.expiry; f.state.input = input; assert.equal(await f.invoke(), f.result); const output = exact(f); assert.equal(Object.getOwnPropertyDescriptor(output, "__proto__")!.value, f.field); assert.notEqual(Object.getPrototypeOf(output), f.field); });
  await t.test("proxy observes await then ownKeys descriptors getters then a second expiry read", async () => { const f = fixture(), symbol = Symbol("PUBLIC"), seen: PropertyKey[] = []; const source = { expiresAt: f.expiry, item: f.field, [symbol]: f.field }; f.state.input = new Proxy(source, { get(t, k, r) { seen.push(k); return Reflect.get(t, k, r); }, ownKeys(t) { seen.push("OWNKEYS"); return Reflect.ownKeys(t); }, getOwnPropertyDescriptor(t, k) { seen.push(`DESC:${String(k)}`); return Reflect.getOwnPropertyDescriptor(t, k); } }); assert.equal(await f.invoke(), f.result); assert.deepEqual(seen, ["then", "OWNKEYS", "DESC:expiresAt", "expiresAt", "DESC:item", "item", "DESC:Symbol(PUBLIC)", symbol, "expiresAt"]); assert.equal(exact(f).item, f.field); });
  for (const stage of ["ownKeys", "descriptor", "get"]) await t.test(`spread proxy ${stage} refusal occurs after method capture before Date`, async () => { const f = fixture(); f.state.input = new Proxy({ expiresAt: f.expiry, item: f.field }, { get(t, k, r) { if (k === "item" && stage === "get") throw f.fault; return Reflect.get(t, k, r); }, ownKeys(t) { if (stage === "ownKeys") throw f.fault; return Reflect.ownKeys(t); }, getOwnPropertyDescriptor(t, k) { if (k === "item" && stage === "descriptor") throw f.fault; return Reflect.getOwnPropertyDescriptor(t, k); } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.dates.length, 0); });
  for (const value of [false, 0, 7, 3n, Symbol("PUBLIC"), "", "PUBLIC"]) await t.test(`primitive input ${String(value)} preserves spread semantics with undefined expiry`, async () => { const f = fixture(); f.state.input = value; assert.equal(await f.invoke(), f.result); const output = exact(f, f.registry, f.actor, f.request, f.schema, undefined); assert.deepEqual(Reflect.ownKeys(output), [...Object.keys(Object(value)), "expiresAt"]); for (const k of Object.keys(Object(value))) assert.equal(output[k], Object(value)[k]); });
  await t.test("pending body forbids issue lookup spread and Date until resolution", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 3)); d.resolve(f.input); assert.equal(await p, f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("rejected body prevents issue lookup spread and Date", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("throwing body then getter rejects before issue lookup", async () => { const f = fixture(); f.state.input = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("body thenable resolves exact input before issue lookup", async () => { const f = fixture(); const input = { expiresAt: f.expiry, item: f.field }; f.state.input = { then(resolve: (v: any) => void) { resolve(input); } }; assert.equal(await f.invoke(), f.result); assert.equal(exact(f).item, f.field); });
  await t.test("expiry promise remains raw at modeled Date constructor", async () => { const f = fixture(), d = deferred(); f.state.expiry = d.promise; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, d.promise); d.resolve(null); await d.promise; });
  await t.test("issue pending promise adopts exact resolved identity", async () => { const f = fixture(), d = deferred(), target = { public: "ADOPTED" }; f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 1); d.resolve(target); assert.equal(await p, target); });
  await t.test("issue promise rejection preserves exact reason", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); });
  await t.test("issue thenable is adopted with original receiver", async () => { const f = fixture(), target = { public: "THENABLE" }; const v = { then(this: unknown, yes: (v: any) => void) { assert.equal(this, v); yes(target); } }; f.state.result = v; assert.equal(await f.invoke(), target); });
  await t.test("issue throwing then getter rejects after exactly one issue call", async () => { const f = fixture(); f.state.result = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  await t.test("extra arguments and callback this stay unread", async () => { const f = fixture(); assert.equal(await f.callback.call(opaque("callback this"), f.registry, f.actor, f.request, opaque("extra")), f.result); exact(f); });
  await t.test("fresh calls capture fresh body schema actor request method input and Date output", async () => { const f = fixture(); assert.equal(await f.invoke(), f.result); const first = f.calls[0].args[1], actor = opaque("fresh actor"), request = opaque("fresh request"), schema = opaque("fresh schema"), expiry = opaque("fresh expiry"), value = opaque("fresh field"), constructed = opaque("fresh Date"), result = { public: "FRESH" }; const r = { issueIdentity: f.method }; Object.assign(f.state, { schema, input: { expiresAt: expiry, fresh: value }, constructed, result }); assert.equal(await f.invoke(r, actor, request), result); const output = exact(f, r, actor, request, schema, expiry); assert.notEqual(output, first); assert.equal(output.fresh, value); assert.equal(first.expiresAt, f.constructed); });
  for (const stage of order) await t.test(`refused ${stage} leaves a later fresh call usable`, async () => { const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults[stage]; f.state.reads = 0; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("interleaved body waits preserve each actor request schema registry input and fresh output", async () => { const f = fixture(), first = deferred(), second = deferred(); f.state.input = first.promise; const p = f.invoke(); const actor = opaque("second actor"), request = opaque("second request"), schema = opaque("second schema"), expiry = opaque("second expiry"), value = opaque("second field"); const r = { issueIdentity: f.method }; f.state.input = second.promise; f.state.schema = schema; const q = f.invoke(r, actor, request); second.resolve({ expiresAt: expiry, item: value }); assert.equal(await q, f.result); assert.equal(f.calls[0].receiver, r); assert.equal(f.calls[0].args[0], actor); assert.equal(f.dates[0].args[0], expiry); first.resolve(f.input); assert.equal(await p, f.result); assert.equal(f.calls[1].receiver, f.registry); assert.equal(f.calls[1].args[0], f.actor); assert.equal(f.dates[1].args[0], f.expiry); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); assert.equal(f.bodies[0].args[0], f.request); assert.equal(f.bodies[0].args[1], f.schema); assert.equal(f.bodies[1].args[0], request); assert.equal(f.bodies[1].args[1], schema); });
  await t.test("interleaved issue waits adopt each resolved identity independently", async () => { const f = fixture(), first = deferred(), second = deferred(), a = { public: "FIRST" }, b = { public: "SECOND" }; f.state.result = first.promise; const p = f.invoke(); await Promise.resolve(); f.state.result = second.promise; const q = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 2); second.resolve(b); assert.equal(await q, b); first.resolve(a); assert.equal(await p, a); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); });
});
