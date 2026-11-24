import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC GET SOURCE controls. No actual parser/schema/import runs.
// POST/PATCH are captured and never called; all imported implementations inert.
type Model = Record<string, any>;
const path = "src/app/api/kv/rotations/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
function opaque(label: string) {
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} read`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], markers: unknown[] = [], urls: Model[] = [], gets: Model[] = [], all: Model[] = [], strings: Model[] = [], uuids: Model[] = [], parses: Model[] = [], engines: unknown[][] = [], constructions: Model[] = [], cursors: unknown[][] = [], calls: Model[] = [], errors: Model[] = [];
  const fault = Error("PUBLIC-FAULT"), registry = opaque("registry"), actor = opaque("actor"), extra = opaque("context"), engine = opaque("engine"), url = opaque("url-input");
  const pathId = Object.freeze({ public: "PATH" }), cursor = Object.freeze({ public: "CURSOR" }), result = Object.freeze({ public: "RESULT" }), refused = Object.freeze({ public: "REFUSED" });
  const state: Model = { pathId, cursor, result, engine, keys: ["pathId", "cursor"], length: 1, success: true, faults: {}, hooks: {}, url, ctor: null, engineFn: null, method: null, rotation: null, cursorFn: null, URL: null, params: null, getFn: null, keysFn: null, allFn: null, z: null, stringFn: null, uuidFn: null, parseFn: null, schema: null, uuidSchema: null, parsed: null, errorCtor: null };
  function stage(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  function method(this: unknown, ...args: unknown[]) { stage("list"); calls.push({ receiver: this, args }); return state.result; }
  const rotation = Object.defineProperty({}, "list", { get() { stage("list-get"); return state.method; } });
  function Rotations(this: unknown, ...args: unknown[]) { stage("construct"); constructions.push({ receiver: this, newTarget: new.target, args }); return state.rotation; }
  const params = {
    get get() { stage("get-get"); return state.getFn; },
    get keys() { stage("keys-get"); return state.keysFn; },
    get getAll() { stage("all-get"); return state.allFn; }
  };
  const request = Object.defineProperty({}, "url", { get() { stage("request-url"); return state.url; } });
  const urlObject = Object.defineProperty({}, "searchParams", { get() { stage("params"); return state.params; } });
  function URLModel(this: unknown, ...args: unknown[]) { stage("URL"); urls.push({ receiver: this, newTarget: new.target, args }); return state.urlObject; }
  const schema = Object.defineProperty({}, "uuid", { get() { stage("uuid-get"); return state.uuidFn; } });
  const uuidSchema = Object.defineProperty({}, "safeParse", { get() { stage("parse-get"); return state.parseFn; } });
  const parsed = Object.defineProperty({}, "success", { get() { stage("success"); return state.success; } });
  const z = Object.defineProperty({}, "string", { get() { stage("string-get"); return state.stringFn; } });
  function ErrorModel(this: unknown, ...args: unknown[]) { stage("error"); errors.push({ receiver: this, newTarget: new.target, args }); return state.refused; }
  Object.assign(state, { ctor: Rotations, method, rotation, URL: URLModel, urlObject, params, schema, uuidSchema, parsed, z, errorCtor: ErrorModel, refused });
  state.getFn = function(this: unknown, ...args: unknown[]) { stage("get"); gets.push({ receiver: this, args }); return state.pathId; };
  state.keysFn = function(this: unknown, ...args: unknown[]) { stage("keys"); state.keysCall = { receiver: this, args }; return state.iterable; };
  state.iterable = { [Symbol.iterator]() { stage("iterator"); const values = state.keys.slice(); let i = 0; return { next() { stage("next"); return i < values.length ? { value: values[i++], done: false } : { done: true }; } }; } };
  state.allFn = function(this: unknown, ...args: unknown[]) { stage("all"); all.push({ receiver: this, args }); return state.allResult; };
  state.allResult = Object.defineProperty({}, "length", { get() { stage("length"); return state.length; } });
  state.stringFn = function(this: unknown, ...args: unknown[]) { stage("string"); strings.push({ receiver: this, args }); return state.schema; };
  state.uuidFn = function(this: unknown, ...args: unknown[]) { stage("uuid"); uuids.push({ receiver: this, args }); return state.uuidSchema; };
  state.parseFn = function(this: unknown, ...args: unknown[]) { stage("parse"); parses.push({ receiver: this, args }); return state.parsed; };
  state.engineFn = (...args: unknown[]) => { stage("engine"); engines.push(args); return state.engine; };
  state.cursorFn = (...args: unknown[]) => { stage("cursor"); cursors.push(args); return state.cursor; };
  const inert = opaque("unselected import");
  const http = { kvHuman(...args: any[]) { wrappers.push(args); const marker = Object.freeze({ public: `WRAPPER-${markers.length}` }); markers.push(marker); return marker; },
    get kvEngine() { stage("engine-get"); return state.engineFn; }, get metadataCursor() { stage("cursor-get"); return state.cursorFn; }, get kvBody() { throw fault; } };
  const imports: Model = { zod: { get z() { stage("z"); return state.z; } }, "@/lib/kv-contract": { get KvError() { stage("error-get"); return state.errorCtor; } }, "@/lib/kv-http": http,
    "@/lib/kv-rotation": { get KvRotations() { stage("ctor-get"); return state.ctor; } }, "@/lib/kv-schemas": inert, "@/lib/kv-rotation-consumer": inert, "@/lib/k8s": inert };
  const m = { exports: {} as Model }, sandbox = { module: m, exports: m.exports, require: (id: string) => {
      // Canonical inert dependency name; application uses the supported v3 export.
      id = id === "zod/v3" ? "zod" : id; assert.ok(Object.hasOwn(imports, id)); return imports[id]; } };
  Object.defineProperty(sandbox, "URL", { get() { stage("URL-get"); return state.URL; } });
  runInNewContext(compiled, sandbox, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 3); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { state, trace, wrappers, markers, urls, gets, all, strings, uuids, parses, engines, constructions, cursors, calls, errors, fault, refused, registry, actor, request, extra, engine, url, pathId, cursor, result, rotation, Rotations, URLModel, params, schema, uuidSchema, z, method, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : extra) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const prefix = ["URL-get", "request-url", "URL", "params", "get-get", "get", "keys-get", "keys", "iterator", "next", "next", "next", "all-get", "all", "length", "all-get", "all", "length"];
const validation = ["z", "string-get", "string", "uuid-get", "uuid", "parse-get", "parse", "success"];
const suffix = ["ctor-get", "engine-get", "engine", "construct", "list-get", "cursor-get", "cursor", "list"];
const order = [...prefix, ...validation, ...suffix];
function exact(f: Fixture, actor: unknown = f.actor, pathId: unknown = f.pathId, cursor: unknown = f.cursor, rotation: unknown = f.rotation) {
  const c = f.calls.at(-1)!; assert.equal(c.receiver, rotation); assert.equal(c.args.length, 3); assert.equal(c.args[0], actor); assert.equal(c.args[1], pathId); assert.equal(c.args[2], cursor);
}
async function refused(f: Fixture) {
  await assert.rejects(f.invoke(), e => e === f.refused); assert.equal(f.errors.length, 1); assert.deepEqual(f.errors[0].args, [400, "Explicit path and valid rotation metadata filters required"]); assert.equal(f.constructions.length, 0); assert.equal(f.cursors.length, 0); assert.equal(f.calls.length, 0);
}

test("human rotation metadata GET exact SOURCE delegation", async t => {
  await t.test("exact nodejs force-dynamic default GET wrapper and inert POST201 PATCH", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "PATCH", "POST", "dynamic", "runtime"]); assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, name] of ["GET", "POST", "PATCH"].entries()) { assert.equal(f.exports[name], f.markers[i]); assert.equal(typeof f.wrappers[i][0], "function"); assert.equal(f.wrappers[i].length, i === 1 ? 2 : 1); } assert.equal(f.wrappers[1][1], 201); assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("exact URL filter schema constructor cursor and receiver order", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); assert.deepEqual(f.trace, order); exact(f);
    assert.equal(f.urls[0].args.length, 1); assert.equal(f.urls[0].args[0], f.url); assert.equal(f.urls[0].newTarget, f.URLModel);
    assert.equal(f.gets[0].receiver, f.params); assert.deepEqual(f.gets[0].args, ["pathId"]); assert.equal(f.state.keysCall.receiver, f.params); assert.deepEqual(f.state.keysCall.args, []);
    assert.deepEqual(f.all.map(x => x.args), [["pathId"], ["cursor"]]); assert.ok(f.all.every(x => x.receiver === f.params));
    for (const [calls, receiver] of [[f.strings, f.z], [f.uuids, f.schema], [f.parses, f.uuidSchema]] as [Model[], unknown][]) { assert.equal(calls.length, 1); assert.equal(calls[0].receiver, receiver); }
    assert.deepEqual(f.strings[0].args, []); assert.deepEqual(f.uuids[0].args, []); assert.equal(f.parses[0].args.length, 1); assert.equal(f.parses[0].args[0], f.pathId);
    assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry); assert.equal(f.constructions[0].args.length, 1); assert.equal(f.constructions[0].args[0], f.engine); assert.equal(f.constructions[0].newTarget, f.Rotations); assert.equal(f.cursors[0].length, 1); assert.equal(f.cursors[0][0], f.request);
  });
  for (const name of [...new Set(order)]) await t.test(`throwing ${name} stops exactly at source stage`, async () => {
    const f = fixture(); f.state.faults[name] = f.fault; await assert.rejects(f.invoke(), e => name === "URL-get" ? isError(e) && (e as Error).name === "ReferenceError" && (e as Error).message === "URL is not defined" : e === f.fault); assert.deepEqual(f.trace, order.slice(0, order.indexOf(name) + 1)); assert.equal(f.calls.length, 0);
  });
  for (const keys of [[], ["pathId"], ["cursor"], ["cursor", "pathId"], ["pathId", "pathId"]]) await t.test(`finite modeled keys ${JSON.stringify(keys)} delegate in source order`, async () => {
    const f = fixture(); f.state.keys = keys; await f.invoke(); exact(f); assert.deepEqual(f.all.map(x => x.args[0]), keys); assert.equal(f.parses[0].args[0], f.pathId);
  });
  for (const key of ["extra", "PathId", "", null, undefined, 0, Symbol("PUBLIC-KEY")]) await t.test(`unknown key ${String(key)} refuses before getAll and schema`, async () => {
    const f = fixture(); f.state.keys = [key, "pathId"]; await refused(f); assert.equal(f.all.length, 0); assert.equal(f.strings.length, 0); assert.ok(!f.trace.includes("z")); assert.deepEqual(f.trace.slice(-2), ["error-get", "error"]);
  });
  await t.test("spread completes finite iteration before first filter and short circuits later keys", async () => {
    const f = fixture(); f.state.keys = ["pathId", "unknown", "cursor"]; await refused(f); assert.equal(f.trace.filter(x => x === "next").length, 4); assert.deepEqual(f.all.map(x => x.args), [["pathId"]]); assert.equal(f.parses.length, 0);
  });
  for (const length of [0, 2, -1, "1", null, undefined, NaN]) await t.test(`duplicate length model ${String(length)} uses strict one check`, async () => { const f = fixture(); f.state.length = length; await refused(f); assert.equal(f.all.length, 1); assert.equal(f.parses.length, 0); });
  for (const success of [false, 0, "", null, undefined]) await t.test(`falsy UUID model success ${String(success)} refuses`, async () => { const f = fixture(); f.state.success = success; await refused(f); assert.equal(f.parses.length, 1); assert.ok(!f.trace.includes("ctor-get")); });
  for (const success of [true, 1, "PUBLIC", opaque("truthy success")]) await t.test(`truthy schema result ${typeof success} proceeds without inspection`, async () => { const f = fixture(); f.state.success = success; await f.invoke(); exact(f); });
  for (const name of ["error-get", "error"]) await t.test(`invalid filters ${name} fault preserves exact refusal`, async () => { const f = fixture(); f.state.keys = ["unknown"]; f.state.faults[name] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 0); assert.equal(f.parses.length, 0); assert.equal(f.trace.at(-1), name); });
  for (const value of [null, undefined, 7, {}, () => {}]) await t.test(`nonconstructible URL ${String(value)} still reads original url`, async () => { const f = fixture(); f.state.URL = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); });
  for (const [field, stage] of [["getFn", "get-get"], ["keysFn", "keys-get"], ["allFn", "all-get"], ["stringFn", "string-get"], ["uuidFn", "uuid-get"], ["parseFn", "parse-get"], ["engineFn", "engine-get"]]) await t.test(`noncallable ${field} refuses without later work`, async () => { const f = fixture(); f.state[field] = null; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, order.indexOf(stage) + 1)); });
  for (const [field, last] of [["params", "params"], ["z", "z"], ["schema", "string"], ["uuidSchema", "uuid"], ["parsed", "parse"], ["allResult", "all"]]) await t.test(`nullish ${field} stops before next property`, async () => { const f = fixture(); f.state[field] = null; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, order.indexOf(last) + 1)); });
  for (const value of [null, undefined, 9, {}, () => {}]) await t.test(`nonconstructible rotation ${String(value)} evaluates engine only`, async () => { const f = fixture(); f.state.ctor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, order.indexOf("engine") + 1)); assert.equal(f.cursors.length, 0); });
  for (const value of [null, undefined, 9, {}]) await t.test(`noncallable list ${String(value)} evaluates cursor before refusal`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, -1)); assert.equal(f.cursors.length, 1); });
  for (const value of [null, undefined, 9, {}]) await t.test(`noncallable cursor ${String(value)} prevents list call`, async () => { const f = fixture(); f.state.cursorFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, order.indexOf("cursor-get") + 1)); assert.equal(f.calls.length, 0); });
  await t.test("cursor fault wins over noncallable captured list", async () => { const f = fixture(); f.state.method = null; f.state.faults.cursor = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.trace.at(-1), "cursor"); });
  await t.test("engine fault wins over nonconstructible captured rotation", async () => { const f = fixture(); f.state.ctor = null; f.state.faults.engine = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.trace.at(-1), "engine"); });
  await t.test("pathId captured before key iteration and forwarded without reading parser data", async () => { const f = fixture(); f.state.hooks.keys = () => { f.state.pathId = opaque("replacement path"); }; Object.defineProperty(f.state.parsed, "data", { get() { throw f.fault; } }); await f.invoke(); exact(f); assert.equal(f.parses[0].args[0], f.pathId); });
  await t.test("constructor captured before engine side effect", async () => { const f = fixture(); f.state.hooks.engine = () => { f.state.ctor = null; }; await f.invoke(); exact(f); assert.equal(f.constructions[0].newTarget, f.Rotations); });
  await t.test("list captured before cursor side effect and original receiver retained", async () => { const f = fixture(); f.state.hooks.cursor = () => { f.state.method = null; f.state.rotation = null; }; await f.invoke(); exact(f); });
  await t.test("cursor getter can select fresh cursor function", async () => { const f = fixture(), cursor = opaque("fresh cursor"); f.state.hooks["cursor-get"] = () => { f.state.cursorFn = (...args: unknown[]) => { assert.equal(args.length, 1); assert.equal(args[0], f.request); return cursor; }; }; await f.invoke(); exact(f, f.actor, f.pathId, cursor); });
  await t.test("inherited list preserves constructed receiver", async () => { const f = fixture(), rotation = Object.create({ list: f.method }); Object.defineProperty(rotation, "then", { get() { throw f.fault; } }); f.state.rotation = rotation; await f.invoke(); exact(f, f.actor, f.pathId, f.cursor, rotation); });
  await t.test("inherited request url and params methods retain receivers", async () => { const f = fixture(), request = Object.create(f.request), params = Object.create(f.params); f.state.params = params; await f.invoke(f.registry, f.actor, request); exact(f); assert.equal(f.gets[0].receiver, params); assert.equal(f.state.keysCall.receiver, params); assert.equal(f.cursors[0][0], request); });
  for (const value of [null, undefined, false, 0, "", Symbol("PUBLIC")]) await t.test(`path and cursor modeled ${String(value)} pass unchanged without validation claim`, async () => { const f = fixture(); f.state.pathId = value; f.state.cursor = value; await f.invoke(); const c = f.calls[0]; assert.equal(c.args[1], value); assert.equal(c.args[2], value); assert.equal(f.parses[0].args[0], value); });
  for (const value of [null, undefined, false, 0, "", Symbol("PUBLIC")]) await t.test(`engine ${String(value)} passed as sole constructor argument`, async () => { const f = fixture(); f.state.engine = value; await f.invoke(); assert.equal(f.constructions[0].args.length, 1); assert.equal(f.constructions[0].args[0], value); });
  for (const value of [null, undefined, false, 0, "", Symbol("PUBLIC")]) await t.test(`primitive rotation return ${String(value)} uses new receiver`, async () => { const f = fixture(); f.state.rotation = value; Object.defineProperty(f.Rotations.prototype, "list", { value: f.method }); await f.invoke(); exact(f, f.actor, f.pathId, f.cursor, f.constructions[0].receiver); });
  await t.test("function returned rotation retains receiver", async () => { const f = fixture(), rotation = Object.assign(() => { throw f.fault; }, { list: f.method }); f.state.rotation = rotation; await f.invoke(); exact(f, f.actor, f.pathId, f.cursor, rotation); });
  await t.test("list rejection identity adopted by async callback", async () => { const f = fixture(); f.state.result = Promise.reject(f.fault); await assert.rejects(f.invoke(), e => e === f.fault); exact(f); });
  await t.test("held list result stays pending then adopts resolved identity", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; let settled = false; const pending = f.invoke().then(v => { settled = true; return v; }); await turns(); assert.equal(settled, false); exact(f); d.resolve(f.result); assert.equal(await pending, f.result); });
  await t.test("held rejection remains same public fault", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const check = assert.rejects(f.invoke(), e => e === f.fault); await turns(); d.reject(f.fault); await check; exact(f); });
  await t.test("thenable list result adopts resolved identity only", async () => { const f = fixture(); f.state.result = { then(resolve: (x: unknown) => void) { resolve(f.result); } }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("fresh same-fixture calls reread request path cursor registry and actor", async () => {
    const f = fixture(); await f.invoke(); const pathId = opaque("next path"), cursor = opaque("next cursor"), actor = opaque("next actor"), registry = opaque("next registry"), url = opaque("next url"), request = { url };
    Object.assign(f.state, { pathId, cursor }); await f.invoke(registry, actor, request); exact(f, actor, pathId, cursor); assert.equal(f.urls[1].args[0], url); assert.equal(f.engines[1][0], registry); assert.equal(f.cursors[1][0], request); assert.equal(f.calls.length, 2);
  });
  await t.test("interleaved held calls keep each captured receiver path cursor and result", async () => {
    const f = fixture(), a = deferred(), b = deferred(); f.state.result = a.promise; const first = f.invoke(); const pathId = opaque("second path"), cursor = opaque("second cursor"), actor = opaque("second actor"), rotation = { list: f.method };
    Object.assign(f.state, { pathId, cursor, result: b.promise, rotation }); const second = f.invoke(f.registry, actor); exact(f, actor, pathId, cursor, rotation); b.resolve(f.refused); assert.equal(await second, f.refused); a.resolve(f.result); assert.equal(await first, f.result); assert.equal(f.calls[0].receiver, f.rotation); assert.equal(f.calls[0].args[1], f.pathId); assert.equal(f.calls[0].args[2], f.cursor);
  });
  await t.test("invalid call never consumes earlier accepted held result", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const first = f.invoke(); f.state.keys = ["unknown"]; await assert.rejects(f.invoke(), e => e === f.refused); assert.equal(f.calls.length, 1); d.resolve(f.result); assert.equal(await first, f.result); });
});
