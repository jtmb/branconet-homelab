import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";

// Only the selected method executes. All client/process metadata are inert.
// Malformed metadata and thenables characterize JavaScript only.
const requireTool = createRequire(import.meta.url);
const ts: typeof import("typescript") = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript");
const filename = path.resolve(import.meta.dirname, "../src/lib/account-store.ts");
const source = readFileSync(filename, "utf8");
const file = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const classes = file.statements.filter((node): node is import("typescript").ClassDeclaration => ts.isClassDeclaration(node) && node.name?.text === "AccountStore");
assert.equal(classes.length, 1);
const methods = classes[0].members.filter((node): node is import("typescript").MethodDeclaration => ts.isMethodDeclaration(node) && node.name.getText(file) === "registrationOpen");
assert.equal(methods.length, 1);
const selected = methods[0].getText(file);
const javascript = ts.transpileModule('"use strict";\n({' + selected + "}).registrationOpen;", { compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None } }).outputText;
type Method = (this: unknown, ...args: unknown[]) => Promise<unknown>;
function shell(metadata: Record<string, unknown>): Method {
  return new vm.Script(javascript, { filename: "selected-registration-open-inert.js" }).runInContext(vm.createContext(metadata, { codeGeneration: { strings: false, wasm: false } }), { timeout: 1000 }) as Method;
}
function client(count: unknown = 1, setting: unknown = null) {
  return { user: { count: () => count }, appSetting: { findUnique: () => setting } };
}
function lift(count: unknown = 1, value: unknown = null, environment: unknown = undefined) {
  const db = client(count, value);
  const method = shell({ process: { env: { ALLOW_REGISTRATION: environment } } });
  return () => method.call({ db });
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function fault(result: Promise<unknown>, reason: unknown) { await assert.rejects(result, error => error === reason); }
function blocked(): never { return assert.fail("unselected metadata reached"); }

test("supported empty account store opens registration", async () => { assert.equal(await lift(0)(), true); });
test("supported nonempty store without flags closes registration", async () => { assert.equal(await lift(1)(), false); });
test("supported environment true opens nonempty store", async () => { assert.equal(await lift(2, null, "true")(), true); });
test("supported stored true opens nonempty store", async () => { assert.equal(await lift(1, { value: "true" })(), true); });
test("supported stored false closes nonempty store", async () => { assert.equal(await lift(1, { value: "false" }, "false")(), false); });
test("supported absent setting closes nonempty store", async () => { assert.equal(await lift(3, null, "false")(), false); });

test("default client reads receiver db once before count call", async () => {
  const events: string[] = []; const db = client(0);
  const receiver = { get db() { events.push("db"); return db; } };
  const run = shell({ get process(): never { return blocked(); } });
  const result = run.call(receiver); assert.equal(events.join(","), "db");
  assert.equal(await result, true); assert.equal(events.length, 1);
});
test("explicit undefined selects default client", async () => {
  const run = shell({}); assert.equal(await run.call({ db: client(0) }, undefined), true);
});
test("explicit client avoids receiver db and retains its own decision", async () => {
  const run = shell({}); const receiver = { get db(): never { return blocked(); } };
  assert.equal(await run.call(receiver, client(0)), true);
});
test("explicit client permits absent receiver", async () => { assert.equal(await shell({}).call(undefined, client(0)), true); });
test("default db getter failure rejects with exact reason", async () => {
  const reason = {}; await fault(shell({}).call({ get db(): never { throw reason; } }), reason);
});
test("missing default receiver rejects without process access", async () => {
  await assert.rejects(shell({ get process(): never { return blocked(); } }).call(undefined), error => (error as Error).name === "TypeError");
});
test("explicit null client rejects rather than using default", async () => {
  await assert.rejects(shell({}).call({ get db(): never { return blocked(); } }, null), error => (error as Error).name === "TypeError");
});
test("count member resolution receiver and zero arguments are exact", async () => {
  const events: string[] = [];
  const user = { get count() { events.push("count"); return function (this: unknown, ...args: unknown[]) { events.push("call"); assert.equal(this, user); assert.equal(args.length, 0); return 0; }; } };
  const db = { get user() { events.push("user"); return user; }, get appSetting(): never { return blocked(); } };
  assert.equal(await shell({}).call(undefined, db), true); assert.equal(events.join(","), "user,count,call");
});
test("count zero shortcircuits all process and setting access", async () => {
  const db = { user: { count: () => 0 }, get appSetting(): never { return blocked(); } };
  assert.equal(await shell({ get process(): never { return blocked(); } }).call(undefined, db), true);
});
test("count await fences environment and settings reads", async () => {
  const events: string[] = []; const pending = deferred();
  const db = { user: { count: () => { events.push("count"); return pending.promise; } }, appSetting: { findUnique: () => { events.push("setting"); return null; } } };
  const run = shell({ process: { env: { get ALLOW_REGISTRATION() { events.push("env"); return "false"; } } } });
  const result = run.call(undefined, db); await Promise.resolve(); assert.equal(events.join(","), "count");
  pending.resolve(1); assert.equal(await result, false); assert.equal(events.join(","), "count,env,setting");
});
test("immediate count still yields before environment read", async () => {
  let reads = 0; const result = shell({ process: { env: { get ALLOW_REGISTRATION() { reads++; return "true"; } } } }).call(undefined, client(1));
  assert.equal(reads, 0); assert.equal(await result, true); assert.equal(reads, 1);
});
test("count synchronous fault rejects without later reads or retry", async () => {
  const reason = {}; let calls = 0;
  const db = { user: { count: () => { calls++; throw reason; } }, get appSetting(): never { return blocked(); } };
  await fault(shell({ get process(): never { return blocked(); } }).call(undefined, db), reason); assert.equal(calls, 1);
});
test("count rejected promise retains exact failure", async () => {
  const reason = {}; await fault(shell({ get process(): never { return blocked(); } }).call(undefined, client(Promise.reject(reason))), reason);
});
test("user and count getter faults preserve exact failure", async () => {
  const reason = {};
  for (const db of [{ get user(): never { throw reason; } }, { user: { get count(): never { throw reason; } } }]) await fault(shell({}).call(undefined, db), reason);
});
test("synthetic count thenable uses its own receiver and first settlement", async () => {
  let calls = 0; const value = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, value); calls++; yes(0); yes(1); } };
  assert.equal(await shell({}).call(undefined, client(value)), true); assert.equal(calls, 1);
});
test("synthetic count comparison is strict without coercion", async () => {
  const opaque = { [Symbol.toPrimitive]: blocked, valueOf: blocked, toString: blocked };
  for (const count of ["0", false, null, undefined, NaN, 0n, opaque]) assert.equal(await lift(count, null, "false")(), false);
});
test("synthetic negative zero uses numeric zero branch", async () => { assert.equal(await shell({}).call(undefined, client(-0)), true); });
test("environment lookup order is process then env then flag", async () => {
  const events: string[] = [];
  const metadata = { get process() { events.push("process"); return { get env() { events.push("env"); return { get ALLOW_REGISTRATION() { events.push("flag"); return "true"; } }; } }; } };
  assert.equal(await shell(metadata).call(undefined, client()), true); assert.equal(events.join(","), "process,env,flag");
});
test("environment true shortcircuits settings lookup", async () => {
  const db = { user: { count: () => 1 }, get appSetting(): never { return blocked(); } };
  assert.equal(await shell({ process: { env: { ALLOW_REGISTRATION: "true" } } }).call(undefined, db), true);
});
test("environment flag uses exact string comparison without coercion", async () => {
  const opaque = { [Symbol.toPrimitive]: blocked, toString: blocked };
  for (const value of [true, 1, "TRUE", " true", "true ", "false", "", null, opaque]) assert.equal(await lift(1, null, value)(), false);
});
test("environment getter fault propagates before settings", async () => {
  const reason = {}; const db = { user: { count: () => 1 }, get appSetting(): never { return blocked(); } };
  await fault(shell({ process: { env: { get ALLOW_REGISTRATION(): never { throw reason; } } } }).call(undefined, db), reason);
});
test("flag changed while count is pending is read after settlement", async () => {
  const pending = deferred(); const env = { ALLOW_REGISTRATION: "false" }; const result = shell({ process: { env } }).call(undefined, client(pending.promise));
  env.ALLOW_REGISTRATION = "true"; pending.resolve(1); assert.equal(await result, true);
});
test("settings lookup uses exact receiver and fresh nested literal argument", async () => {
  const args: object[] = []; const events: string[] = [];
  const settings = { get findUnique() { events.push("find"); return function (this: unknown, ...values: unknown[]) { assert.equal(this, settings); assert.equal(values.length, 1); const arg = values[0] as { where: { key: string } }; assert.equal(JSON.stringify(arg), '{"where":{"key":"allow_registration"}}'); args.push(arg); return null; }; } };
  const db = { user: { count: () => 1 }, get appSetting() { events.push("settings"); return settings; } };
  const run = shell({ process: { env: {} } }); assert.equal(await run.call(undefined, db), false); assert.equal(await run.call(undefined, db), false);
  assert.notEqual(args[0], args[1]); assert.notEqual((args[0] as { where: object }).where, (args[1] as { where: object }).where); assert.equal(events.join(","), "settings,find,settings,find");
});
test("pending setting prevents value reads until awaited", async () => {
  const pending = deferred(); let reads = 0; const result = lift(1, pending.promise)(); await Promise.resolve(); assert.equal(reads, 0);
  pending.resolve({ get value() { reads++; return "true"; } }); assert.equal(await result, true); assert.equal(reads, 1);
});
test("immediate setting still yields before value access", async () => {
  let reads = 0; const result = lift(1, { get value() { reads++; return "true"; } })(); await Promise.resolve(); assert.equal(reads, 0);
  assert.equal(await result, true); assert.equal(reads, 1);
});
test("nullish setting results close registration", async () => {
  for (const value of [null, undefined]) assert.equal(await lift(1, value)(), false);
});
test("setting value must be exact string true", async () => {
  const opaque = { [Symbol.toPrimitive]: blocked, toString: blocked };
  for (const value of [true, 1, "TRUE", " true", "true ", false, null, undefined, opaque, Promise.resolve("true")]) assert.equal(await lift(1, { value })(), false);
});
test("value getter is read once and primitive Boolean is returned", async () => {
  let reads = 0; const result = await lift(1, { get value() { reads++; return "true"; } })(); assert.equal(result, true); assert.equal(typeof result, "boolean"); assert.equal(reads, 1);
});
test("setting rejected promise preserves exact failure", async () => {
  const reason = {}; const pending = deferred(); const result = lift(1, pending.promise)(); const checked = fault(result, reason); pending.reject(reason); await checked;
});
test("settings access and lookup call faults preserve exact reason", async () => {
  const reason = {};
  for (const db of [{ user: { count: () => 1 }, get appSetting(): never { throw reason; } }, { user: { count: () => 1 }, appSetting: { get findUnique(): never { throw reason; } } }, { user: { count: () => 1 }, appSetting: { findUnique: () => { throw reason; } } }]) await fault(shell({ process: { env: {} } }).call(undefined, db), reason);
});
test("value getter failure propagates without retry", async () => {
  const reason = {}; let reads = 0; await fault(lift(1, { get value(): never { reads++; throw reason; } })(), reason); assert.equal(reads, 1);
});
test("synthetic setting thenable is adopted once before value read", async () => {
  const events: string[] = []; const setting = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, setting); events.push("then"); yes({ get value() { events.push("value"); return "true"; } }); } };
  assert.equal(await lift(1, setting)(), true); assert.equal(events.join(","), "then,value");
});
test("synthetic setting then getter failure preserves exact reason", async () => {
  const reason = {}; await fault(lift(1, { get then(): never { throw reason; } })(), reason);
});
test("successive calls read fresh client count and setting metadata", async () => {
  let count = 0; let setting = { value: "false" }; let calls = 0;
  const db = { user: { count: () => { calls++; return count; } }, appSetting: { findUnique: () => setting } }; const run = shell({ process: { env: {} } });
  assert.equal(await run.call(undefined, db), true); count = 1; assert.equal(await run.call(undefined, db), false); setting = { value: "true" }; assert.equal(await run.call(undefined, db), true); assert.equal(calls, 3);
});
test("concurrent reversed count settlements keep separate decisions", async () => {
  const one = deferred(); const two = deferred(); const run = shell({ process: { env: {} } });
  const first = run.call(undefined, client(one.promise, { value: "false" })); const second = run.call(undefined, client(two.promise)); assert.notEqual(first, second);
  two.resolve(0); assert.equal(await second, true); one.resolve(1); assert.equal(await first, false);
});
test("failure does not cache later registration decisions", async () => {
  const reason = {}; let calls = 0; const db = { user: { count: () => { if (++calls === 1) throw reason; return 0; } } }; const run = shell({});
  await fault(run.call(undefined, db), reason); assert.equal(await run.call(undefined, db), true); assert.equal(calls, 2);
});
test("unused original bindings and client metadata remain inert", async () => {
  const metadata: Record<string, unknown> = {}; for (const name of ["Prisma", "PrismaClient", "AccountStore", "accountChangeQueue", "isAccountQueueBusy", "AccountError", "publicUser"]) Object.defineProperty(metadata, name, { get: blocked });
  const db = { user: { count: () => 0, get create(): never { return blocked(); } }, get $transaction(): never { return blocked(); }, get appSetting(): never { return blocked(); } };
  assert.equal(await shell(metadata).call(undefined, db, new Proxy({}, { get: blocked })), true);
});
