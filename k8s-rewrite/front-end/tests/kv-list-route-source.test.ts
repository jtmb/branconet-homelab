import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. POST operations never execute.
// Plain request/URL/searchParams models; imported implementations stay inert.
type Model = Record<string, any>;
type Kind = "mounts" | "paths";
const routes = { mounts: "src/app/api/kv/mounts/route.ts", paths: "src/app/api/kv/paths/route.ts" };
const compiled = Object.fromEntries(Object.entries(routes).map(([kind, file]) => [kind,
  ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText]));
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function fixture(kind: Kind) {
  const calls: string[] = [], seen: Model = { wrappers: [], invocations: [], receivers: [], cursors: [], urls: [], gets: [] };
  const actor = new Proxy({}, { get() { throw Error("PUBLIC: actor inspection forbidden"); } });
  const result = Object.freeze({ public: "RESULT" }), fault = new Error("PUBLIC-FAULT");
  const state: Model = { result, cursor: "PUBLIC-CURSOR", mount: "PUBLIC-MOUNT", url: "PUBLIC-URL", faults: {} };
  const step = (name: string) => { calls.push(name); if (Object.hasOwn(state.faults, name)) throw state.faults[name]; };
  const request = new Proxy({}, { get(_target, key) {
    assert.equal(key, "url"); step("request.url"); return state.url;
  }, ownKeys() { throw Error("PUBLIC: request enumeration forbidden"); } });
  const params = new Proxy({}, { get() { throw Error("PUBLIC: params forbidden"); }, ownKeys() { throw Error("PUBLIC: params enumeration forbidden"); } });
  const selected = kind === "mounts" ? "listMounts" : "listPaths";
  const registry = new Proxy({}, { get(_target, key) {
    assert.equal(key, selected); step("method");
    return function(this: unknown, ...args: unknown[]) {
      step("invoke"); seen.invocations.push(args); seen.receivers.push(this); return state.result;
    };
  }, ownKeys() { throw Error("PUBLIC: registry enumeration forbidden"); } });
  const searchParams = Object.defineProperty({}, "get", { get() {
    step("getMethod"); return function(this: unknown, ...args: unknown[]) {
      step("get"); seen.gets.push({ receiver: this, args }); return state.mount;
    };
  } });
  const urlModel = Object.defineProperty({}, "searchParams", { get() { step("searchParams"); return searchParams; } });
  function URLModel(...args: unknown[]) { step("url"); seen.urls.push(args); return urlModel; }
  const wrapped = [() => { throw Error("PUBLIC: GET wrapper is inert"); }, () => { throw Error("PUBLIC: POST wrapper is inert"); }];
  const http = {
    kvHuman(...args: any[]) { seen.wrappers.push(args); return wrapped[seen.wrappers.length - 1]; },
    metadataCursor(...args: unknown[]) { step("cursor"); seen.cursors.push(args); return state.cursor; },
    kvBody() { throw Error("PUBLIC: POST body forbidden"); },
  };
  const schemas = new Proxy({}, { get() { throw Error("PUBLIC: schema access forbidden"); } });
  const m = { exports: {} as Model };
  runInNewContext(compiled[kind], { module: m, exports: m.exports, URL: URLModel, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: routes[kind], timeout: 5000 });
  assert.deepEqual(calls, []);
  return { calls, seen, actor, registry, request, params, state, result, fault, wrapped, searchParams, exports: m.exports,
    invoke: (a: unknown = actor, q: unknown = request, p: unknown = params) => seen.wrappers[0][0](registry, a, q, p) };
}
const sequence = (kind: Kind) => kind === "mounts" ? ["method", "cursor", "invoke"] :
  ["method", "request.url", "url", "searchParams", "getMethod", "get", "cursor", "invoke"];
for (const kind of ["mounts", "paths"] as const) test(`${kind} GET exact SOURCE delegation`, async t => {
  await t.test("exports exact GET and inert POST wrapper registrations, statuses and runtime settings", () => {
    const f = fixture(kind); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.GET, f.wrapped[0]); assert.equal(f.exports.POST, f.wrapped[1]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.seen.wrappers.length, 2); assert.equal(f.seen.wrappers[0].length, 1);
    assert.equal(f.seen.wrappers[1].length, 2); assert.equal(f.seen.wrappers[1][1], 201);
    assert.equal(typeof f.seen.wrappers[0][0], "function"); assert.equal(typeof f.seen.wrappers[1][0], "function");
    assert.deepEqual(f.seen.invocations, []); assert.deepEqual(f.calls, []);
  });
  await t.test("forwards exact actor, cursor and mount arguments with registry receiver and raw result", () => {
    const f = fixture(kind); assert.equal(f.invoke(), f.result); assert.deepEqual(f.calls, sequence(kind));
    assert.deepEqual(f.seen.invocations, [kind === "mounts" ? [f.actor, "PUBLIC-CURSOR"] : [f.actor, "PUBLIC-MOUNT", "PUBLIC-CURSOR"]]);
    assert.equal(f.seen.receivers[0], f.registry); assert.deepEqual(f.seen.cursors, [[f.request]]);
    if (kind === "paths") {
      assert.deepEqual(f.seen.urls, [["PUBLIC-URL"]]); assert.equal(f.seen.gets[0].receiver, f.searchParams);
      assert.deepEqual(f.seen.gets[0].args, ["mountId"]);
    } else { assert.deepEqual(f.seen.urls, []); assert.deepEqual(f.seen.gets, []); }
  });
  await t.test("does not inspect actor, context parameters, body, signal or schemas", () => {
    const f = fixture(kind); assert.equal(f.invoke(), f.result); assert.deepEqual(f.calls, sequence(kind));
    if (kind === "mounts") assert.equal(f.invoke(f.actor, new Proxy({}, { get() { throw Error("PUBLIC: request inspected"); } })), f.result);
  });
  for (const stage of sequence(kind)) for (const label of ["error", "object"] as const)
    await t.test(`exact ${stage} ${label} refusal stops subsequent source work`, () => {
      const f = fixture(kind), error = label === "error" ? f.fault : Object.freeze({ public: "REFUSAL" });
      f.state.faults[stage] = error; assert.throws(() => f.invoke(), e => e === error);
      assert.deepEqual(f.calls, sequence(kind).slice(0, sequence(kind).indexOf(stage) + 1));
      assert.equal(f.seen.invocations.length, 0);
    });
  for (const value of [undefined, null, false, 0, ""]) await t.test(`raw result ${String(value)} remains unchanged`, () => {
    const f = fixture(kind); f.state.result = value; assert.equal(f.invoke(), value); assert.deepEqual(f.calls, sequence(kind));
  });
  for (const cursor of [undefined, "", "PUBLIC-CURSOR-NEXT"]) await t.test(`cursor model ${String(cursor)} is forwarded exactly`, () => {
    const f = fixture(kind); f.state.cursor = cursor; f.invoke(); assert.equal(f.seen.invocations[0].at(-1), cursor);
  });
  await t.test("returns frozen nested result identities without cloning or mutation", () => {
    const f = fixture(kind), rows = Object.freeze([Object.freeze({ public: "ROW" })]);
    f.state.result = Object.freeze({ rows }); assert.equal(f.invoke(), f.state.result); assert.equal(f.state.result.rows, rows);
  });
  await t.test("returns the exact rejected method promise without retry or error mapping", async () => {
    const f = fixture(kind), promise = Promise.reject(f.fault); f.state.result = promise;
    const refused = assert.rejects(promise, e => e === f.fault); assert.equal(f.invoke(), promise); await refused;
    assert.deepEqual(f.calls, sequence(kind)); assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("held method promise preserves identity and eventual fulfillment", async () => {
    const f = fixture(kind), hold = deferred(); f.state.result = hold.promise; let settled = false;
    const returned = f.invoke(); assert.equal(returned, hold.promise); const observed = returned.then((v: unknown) => { settled = true; return v; });
    await turns(); assert.equal(settled, false); hold.resolve(f.result); assert.equal(await observed, f.result);
    assert.deepEqual(f.calls, sequence(kind));
  });
  await t.test("held rejection propagates exact identity with no subsequent source access", async () => {
    const f = fixture(kind), hold = deferred(); f.state.result = hold.promise;
    const returned = f.invoke(), refused = assert.rejects(returned, e => e === f.fault);
    assert.equal(returned, hold.promise); await turns(); hold.reject(f.fault); await refused; assert.deepEqual(f.calls, sequence(kind));
  });
  await t.test("fresh repeated calls after refusal reacquire cursor, actor, query and result", () => {
    const f = fixture(kind); f.invoke(); f.state.faults.cursor = f.fault; assert.throws(() => f.invoke(), e => e === f.fault);
    delete f.state.faults.cursor; f.state.cursor = "PUBLIC-SECOND"; f.state.mount = "PUBLIC-MOUNT-SECOND"; f.state.url = "PUBLIC-URL-SECOND";
    const actor = Object.freeze({ public: "SECOND-ACTOR" }), result = Object.freeze({ public: "SECOND-RESULT" });
    f.state.result = result; assert.equal(f.invoke(actor), result);
    assert.deepEqual(f.seen.invocations[1], kind === "mounts" ? [actor, "PUBLIC-SECOND"] : [actor, "PUBLIC-MOUNT-SECOND", "PUBLIC-SECOND"]);
    assert.equal(f.seen.cursors.length, 2); assert.equal(f.seen.receivers[1], f.registry);
    if (kind === "paths") assert.deepEqual(f.seen.urls.at(-1), ["PUBLIC-URL-SECOND"]);
  });
  await t.test("interleaved results retain captured arguments and independent settlements", async () => {
    const f = fixture(kind), a = deferred(), b = deferred(), secondActor = { public: "SECOND" };
    f.state.result = a.promise; const first = f.invoke(); f.state.cursor = "PUBLIC-SECOND"; f.state.mount = "PUBLIC-MOUNT-SECOND";
    f.state.result = b.promise; const second = f.invoke(secondActor); assert.equal(first, a.promise); assert.equal(second, b.promise);
    b.resolve(f.result); assert.equal(await second, f.result); let firstSettled = false;
    const observed = first.then((v: unknown) => { firstSettled = true; return v; }); await turns(); assert.equal(firstSettled, false);
    a.resolve("PUBLIC-FIRST-RESULT"); assert.equal(await observed, "PUBLIC-FIRST-RESULT");
    assert.deepEqual(f.seen.invocations, kind === "mounts" ? [[f.actor, "PUBLIC-CURSOR"], [secondActor, "PUBLIC-SECOND"]] :
      [[f.actor, "PUBLIC-MOUNT", "PUBLIC-CURSOR"], [secondActor, "PUBLIC-MOUNT-SECOND", "PUBLIC-SECOND"]]);
    assert.deepEqual(f.calls, [...sequence(kind), ...sequence(kind)]);
  });
  if (kind === "paths") for (const mount of [null, "", "0", " ", "PUBLIC-MOUNT-NEXT"])
    await t.test(`mountId model ${String(mount)} uses exact absent-or-empty normalization`, () => {
      const f = fixture(kind); f.state.mount = mount; f.invoke(); assert.equal(f.seen.invocations[0][1], mount || undefined);
      assert.deepEqual(f.calls, sequence(kind)); assert.equal(f.seen.gets.length, 1);
    });
});
