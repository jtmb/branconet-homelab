import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Finite PUBLIC dispatcher-source controls. Schemas, errors and rotations are
// inert substitutes. No credential, ORM, HTTP or native implementation is loaded.
type Value = Record<string, any>;
type Call = { method: string; args: unknown[] };
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const pathId = "11111111-1111-4111-8111-111111111111";
const rotationId = "22222222-2222-4222-8222-222222222222";
const operationId = "33333333-3333-4333-8333-333333333333";
const logicalPath = "public/service/credential";
const prerequisites = { resourceVersion: "public-rv-17", expectedHead: 9, pathRevision: 7 };
const actor = Object.freeze({ id: "public-owner", sessionVersion: 13, identityId: "public-identity" });
const cases = [
  { input: { operation: "status", pathId }, method: "status", args: (i: Value) => [actor, i.pathId] },
  { input: { operation: "capabilities", pathId }, method: "registry.capabilities", args: (i: Value) => [actor, i.pathId] },
  { input: { operation: "versions", pathId }, method: "versions", args: (i: Value) => [actor, i.pathId] },
  { input: { operation: "read", pathId, version: 3 }, method: "read", args: (i: Value) => [actor, i.pathId, i.version] },
  { input: { operation: "update", pathId, ...prerequisites, fields: Object.freeze([{ field: "public", encoding: "utf8", value: "PUBLIC-INERT" }]) }, method: "change", args: (i: Value) => [actor, i.pathId, i] },
  { input: { operation: "delete", pathId, ...prerequisites, confirmPath: logicalPath }, method: "change", args: (i: Value) => [actor, i.pathId, i, "delete"] },
  { input: { operation: "destroy", pathId, ...prerequisites, confirmPath: logicalPath, versions: Object.freeze([2, 4]) }, method: "destroy", args: (i: Value) => [actor, i.pathId, i] },
  { input: { operation: "rollback", pathId, ...prerequisites, version: 5 }, method: "change", args: (i: Value) => [actor, i.pathId, i, "rollback"] },
  { input: { operation: "reconcile", pathId, ...prerequisites }, method: "change", args: (i: Value) => [actor, i.pathId, i, "reconcile"] },
  { input: { operation: "resolve", operationId }, method: "resolve", args: (i: Value) => [actor, i.operationId] },
  { input: { operation: "rotationPrepare", pathId, pathRevision: 7, field: "public", consumer: Object.freeze({ kind: "Deployment", namespace: "public", name: "consumer" }) }, method: "rotation.prepare", args: (i: Value) => [actor, i] },
  { input: { operation: "rotationGenerate", rotationId, ...prerequisites, revision: 11, confirmPath: logicalPath }, method: "rotation.generate", args: (i: Value) => [actor, i.rotationId, i] },
  { input: { operation: "rotationAcknowledge", rotationId, resourceVersion: "public-rv-19", expectedHead: 12, revision: 14, confirmPath: logicalPath, confirmConsumer: "public-consumer", confirmConsumption: true }, method: "rotation.acknowledge", args: (i: Value) => [actor, i.rotationId, i] },
  { input: { operation: "rotationCancel", rotationId, revision: 18, confirmPath: logicalPath }, method: "rotation.cancel", args: (i: Value) => [actor, i.rotationId, i.revision, i.confirmPath] },
  { input: { operation: "rotationResolve", rotationId }, method: "rotation.resolve", args: (i: Value) => [actor, i.rotationId] },
];
function fixture() {
  const calls: Call[] = [], result = deferred(), path = deferred();
  const state: Value = { pathPending: false, pathError: null };
  const record = (method: string, args: unknown[]) => { calls.push({ method, args }); return result.promise; };
  const registry = {
    capabilities: (...args: unknown[]) => record("registry.capabilities", args),
    path: (...args: unknown[]) => {
      calls.push({ method: "registry.path", args });
      if (state.pathError) throw state.pathError;
      return state.pathPending ? path.promise : Promise.resolve({ path: logicalPath });
    },
  };
  const methods = ["status", "versions", "read", "change", "destroy", "resolve"];
  const engine: Value = { registry };
  for (const name of methods) engine[name] = (...args: unknown[]) => record(name, args);
  class InertError extends Error { constructor(readonly status: number, message: string) { super(message); } }
  class InertRotations {
    constructor(e: unknown) { calls.push({ method: "rotation.constructor", args: [e] }); }
    prepare(...args: unknown[]) { return record("rotation.prepare", args); }
    generate(...args: unknown[]) { return record("rotation.generate", args); }
    acknowledge(...args: unknown[]) { return record("rotation.acknowledge", args); }
    cancel(...args: unknown[]) { return record("rotation.cancel", args); }
    resolve(...args: unknown[]) { return record("rotation.resolve", args); }
  }
  const schema: Value = {};
  for (const name of ["uuid", "int", "positive", "optional", "strict", "extend"]) schema[name] = () => schema;
  const z: Value = {};
  for (const name of ["string", "number", "object", "literal", "discriminatedUnion"]) z[name] = () => schema;
  const schemas: Value = { rotationTarget: {} };
  for (const name of ["dataChange", "nativeDelete", "nativeDestroy", "nativeReconcile", "nativeRollback", "rotationAcknowledge", "rotationCancel", "rotationGenerate", "rotationPrepare"]) schemas[name] = schema;
  const dependencies: Value = { zod: { z }, "./kv-contract": { KvError: InertError },
    "./kv-schemas": schemas, "./kv-rotation": { KvRotations: InertRotations } };
  const file = "src/lib/kv-automation.ts", m = { exports: {} as Value }, loaded: string[] = [];
  const output = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  runInNewContext(output, { module: m, exports: m.exports, require: (name: string) => {
    assert(Object.hasOwn(dependencies, name), `Unselected dispatcher dependency: ${name}`);
    loaded.push(name); return dependencies[name];
  } }, { filename: file, timeout: 5000 });
  assert.deepEqual(calls, []);
  const run = (a: Value, input: Value, e = engine) => m.exports.runAutomation(e, a, input);
  return { calls, result, path, state, engine, loaded, InertError, run };
}
const turn = async () => { await Promise.resolve(); await Promise.resolve(); };
function assertCall(actual: Call, method: string, args: unknown[]) {
  assert.equal(actual.method, method); assert.equal(actual.args.length, args.length);
  args.forEach((arg, index) => assert.equal(actual.args[index], arg));
}
function expectedCalls(f: ReturnType<typeof fixture>, input: Value) {
  return input.operation === "delete" ? [{ method: "registry.path", args: [pathId] }]
    : input.operation.startsWith("rotation") ? [{ method: "rotation.constructor", args: [f.engine] }] : [];
}

test("automation dispatcher identity and exact forwarding source contract", async t => {
  await t.test("module loads only inert selected dependencies without backend calls", () => {
    const f = fixture(); assert.deepEqual(f.loaded, ["zod", "./kv-contract", "./kv-schemas", "./kv-rotation"]);
    assert.deepEqual(f.calls, []); assert.equal(cases.length, 15);
  });
  for (const c of cases) {
    await t.test(`${c.input.operation}: missing identity refuses before engine access`, async () => {
      const f = fixture(), deniedActor = { id: actor.id, sessionVersion: actor.sessionVersion };
      const unreadable = new Proxy({}, { get: () => { assert.fail("identity refusal accessed downstream input/engine"); } });
      await assert.rejects(f.run(deniedActor, c.input, unreadable), (e: any) =>
        e instanceof f.InertError && e.status === 401 && e.message === "KV automation identity required");
      assert.deepEqual(f.calls, []);
    });
    await t.test(`${c.input.operation}: forwards exact arguments and pending result without extra calls`, async () => {
      const f = fixture(), input = Object.freeze({ ...c.input }), value = Object.freeze({ public: c.input.operation });
      let settled = false;
      const p = f.run(actor, input).finally(() => { settled = true; }); await turn();
      const prefix = expectedCalls(f, input), args = c.args(input);
      assert.equal(settled, false); assert.equal(f.calls.length, prefix.length + 1);
      prefix.forEach((call, index) => assertCall(f.calls[index], call.method, call.args));
      assertCall(f.calls[prefix.length], c.method, args);
      f.result.resolve(value); assert.equal(await p, value); assert.equal(f.calls.length, prefix.length + 1);
    });
    await t.test(`${c.input.operation}: preserves downstream rejection identity without retry`, async () => {
      const f = fixture(), input = Object.freeze({ ...c.input }), error = new Error("PUBLIC-DOWNSTREAM-REFUSAL");
      const p = f.run(actor, input); await turn(); const count = f.calls.length;
      const prefix = expectedCalls(f, input); assert.equal(count, prefix.length + 1);
      assertCall(f.calls[prefix.length], c.method, c.args(input));
      f.result.reject(error); await assert.rejects(p, e => e === error); assert.equal(f.calls.length, count);
    });
  }
  await t.test("empty identity also refuses before input/engine access", async () => {
    const f = fixture(), unreadable = new Proxy({}, { get: () => assert.fail("empty identity accessed downstream") });
    await assert.rejects(f.run({ ...actor, identityId: "" }, unreadable, unreadable), (e: any) => e instanceof f.InertError && e.status === 401);
    assert.deepEqual(f.calls, []);
  });
  await t.test("read without an explicit version forwards undefined as its third argument", async () => {
    const f = fixture(), input = Object.freeze({ operation: "read", pathId }), value = {};
    const p = f.run(actor, input); assert.equal(f.calls.length, 1);
    assertCall(f.calls[0], "read", [actor, pathId, undefined]);
    f.result.resolve(value); assert.equal(await p, value);
  });
  const deletion = () => ({ ...cases.find(c => c.input.operation === "delete")!.input });
  await t.test("delete waits for exact path confirmation before change", async () => {
    const f = fixture(), input = deletion(); f.state.pathPending = true;
    const p = f.run(actor, input); await turn(); assert.equal(f.calls.length, 1);
    assertCall(f.calls[0], "registry.path", [pathId]);
    f.path.resolve({ path: logicalPath }); await turn(); assert.equal(f.calls.length, 2);
    assertCall(f.calls[1], "change", [actor, pathId, input, "delete"]);
    const value = {}; f.result.resolve(value); assert.equal(await p, value);
  });
  await t.test("delete mismatched exact path refuses with no change", async () => {
    const f = fixture(), input = { ...deletion(), confirmPath: logicalPath + "/other" };
    await assert.rejects(f.run(actor, input), (e: any) => e instanceof f.InertError && e.status === 400 && e.message === "Exact logical path confirmation required");
    assert.equal(f.calls.length, 1); assertCall(f.calls[0], "registry.path", [pathId]);
  });
  await t.test("delete rejected path lookup preserves error and makes no change", async () => {
    const f = fixture(), error = new Error("PUBLIC-PATH-REFUSAL"); f.state.pathPending = true;
    const p = f.run(actor, deletion()); await turn(); f.path.reject(error);
    await assert.rejects(p, e => e === error); assert.equal(f.calls.length, 1);
    assertCall(f.calls[0], "registry.path", [pathId]);
  });
  await t.test("delete thrown path lookup preserves error and makes no change", async () => {
    const f = fixture(), error = new Error("PUBLIC-PATH-THROW"); f.state.pathError = error;
    await assert.rejects(f.run(actor, deletion()), e => e === error);
    assert.equal(f.calls.length, 1); assertCall(f.calls[0], "registry.path", [pathId]);
  });
});
