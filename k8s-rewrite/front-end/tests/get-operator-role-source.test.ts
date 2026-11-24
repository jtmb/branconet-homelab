import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";

// Exact selected declaration only; account/provider metadata are inert.
// Malformed values and thenables characterize JavaScript, not supported DB data.
const requireTool = createRequire(import.meta.url);
const ts: typeof import("typescript") = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript");
const filename = path.resolve(import.meta.dirname, "../src/lib/permissions.ts");
const text = readFileSync(filename, "utf8");
const file = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const nodes = file.statements.filter((node): node is import("typescript").FunctionDeclaration => ts.isFunctionDeclaration(node) && node.name?.text === "getOperatorRole");
assert.equal(nodes.length, 1);
const declaration = nodes[0].getText(file).replace(/^export\s+/, "");
const javascript = ts.transpileModule('"use strict";\n' + declaration + "\ngetOperatorRole;", { compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None } }).outputText;
type Operator = (...args: unknown[]) => Promise<unknown>;
function shell(sandbox: Record<string, unknown>): Operator {
  return new vm.Script(javascript, { filename: "selected-get-operator-role-inert.js" }).runInContext(vm.createContext(sandbox, { codeGeneration: { strings: false, wasm: false } }), { timeout: 1000 }) as Operator;
}
function account(role = "write", engineAdmin = true) { return { role, engineAdmin }; }
function lift(value: unknown) { return shell({ getSessionAccount: () => value }); }
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function fault(run: () => Promise<unknown>, reason: unknown) { await assert.rejects(run(), error => error === reason); }

test("supported writer administrator receives write", async () => { assert.equal(await lift(account())(), "write"); });
test("supported writer without administration receives readonly", async () => { assert.equal(await lift(account("write", false))(), "readonly"); });
test("supported readonly account stays readonly with administrator flag", async () => { assert.equal(await lift(account("readonly", true))(), "readonly"); });
test("supported readonly account without administration stays readonly", async () => { assert.equal(await lift(account("readonly", false))(), "readonly"); });
test("absent supported account returns null", async () => { assert.equal(await lift(null)(), null); });

test("provider is called once detached with zero arguments", async () => {
  let calls = 0;
  const run = shell({ getSessionAccount: function (this: unknown, ...args: unknown[]) { calls++; assert.equal(this, undefined); assert.equal(args.length, 0); return account(); } });
  assert.equal(await run(), "write"); assert.equal(calls, 1);
});
test("caller receiver and extra argument metadata remain unread", async () => {
  const opaque = new Proxy({}, { get(): never { return assert.fail("caller metadata read"); }, ownKeys(): never { return assert.fail("caller metadata enumerated"); } });
  let calls = 0;
  const run = shell({ getSessionAccount: (...args: unknown[]) => { calls++; assert.equal(args.length, 0); return account(); } });
  assert.equal(await run.call(opaque, opaque), "write"); assert.equal(calls, 1);
});
test("plain provider result still crosses the await decision fence", async () => {
  const events: string[] = [];
  const value = { get role() { events.push("role"); return "write"; }, get engineAdmin() { events.push("admin"); return true; } };
  const result = shell({ getSessionAccount: () => { events.push("provider"); return value; } })();
  assert.equal(events.join(","), "provider");
  assert.equal(await result, "write"); assert.equal(events.join(","), "provider,role,admin");
});
test("pending provider prevents account decision reads", async () => {
  const pending = deferred(); let reads = 0;
  const value = { get role() { reads++; return "write"; }, engineAdmin: true };
  const result = lift(pending.promise)(); await Promise.resolve(); assert.equal(reads, 0);
  pending.resolve(value); assert.equal(await result, "write"); assert.equal(reads, 1);
});
test("provider Promise rejection preserves the exact reason without retry", async () => {
  const reason = {}; let calls = 0;
  const run = shell({ getSessionAccount: () => { calls++; return Promise.reject(reason); } });
  await fault(() => run(), reason); assert.equal(calls, 1);
});
test("provider synchronous failure becomes the exact rejection without retry", async () => {
  const reason = {}; let calls = 0;
  const run = shell({ getSessionAccount: () => { calls++; throw reason; } });
  await fault(() => run(), reason); assert.equal(calls, 1);
});
test("synthetic provider thenable is awaited once with its receiver", async () => {
  let calls = 0;
  const value = { then(this: unknown, yes: (value: unknown) => void) { assert.equal(this, value); calls++; yes(account()); } };
  assert.equal(await lift(value)(), "write"); assert.equal(calls, 1);
});
test("synthetic provider then getter failure preserves its reason", async () => {
  const reason = {};
  await fault(() => lift({ get then(): never { throw reason; } })(), reason);
});
test("synthetic provider thenable first settlement controls the decision", async () => {
  let calls = 0;
  const value = { then(yes: (value: unknown) => void) { calls++; yes(account("readonly", true)); yes(account()); } };
  assert.equal(await lift(value)(), "readonly"); assert.equal(calls, 1);
});

test("wrong exact role shortcircuits administration access", async () => {
  let reads = 0;
  const value = { role: "readonly", get engineAdmin(): never { reads++; return assert.fail("admin reached"); } };
  assert.equal(await lift(value)(), "readonly"); assert.equal(reads, 0);
});
test("unknown case and padded role spellings do not grant write", async () => {
  for (const role of ["admin", "WRITE", " write", "write "]) {
    const value = { role, get engineAdmin(): never { return assert.fail("admin reached"); } };
    assert.equal(await lift(value)(), "readonly");
  }
});
test("synthetic role objects are compared without coercion", async () => {
  const role = { [Symbol.toPrimitive](): never { return assert.fail("role coerced"); }, toString(): never { return assert.fail("role stringified"); } };
  assert.equal(await lift({ role, get engineAdmin(): never { return assert.fail("admin reached"); } })(), "readonly");
});
test("synthetic nullish role metadata does not reach administration", async () => {
  for (const role of [null, undefined]) assert.equal(await lift({ role, get engineAdmin(): never { return assert.fail("admin reached"); } })(), "readonly");
});
test("decision reads role and reached administration exactly once in order", async () => {
  const events: string[] = [];
  const value = { get role() { events.push("role"); return "write"; }, get engineAdmin() { events.push("admin"); return true; } };
  assert.equal(await lift(value)(), "write"); assert.equal(events.join(","), "role,admin");
});
test("role getter failure propagates before administration", async () => {
  const reason = {};
  const value = { get role(): never { throw reason; }, get engineAdmin(): never { return assert.fail("admin reached"); } };
  await fault(() => lift(value)(), reason);
});
test("reached administration getter failure preserves its reason", async () => {
  const reason = {}; let reads = 0;
  await fault(() => lift({ role: "write", get engineAdmin(): never { reads++; throw reason; } })(), reason);
  assert.equal(reads, 1);
});
test("unused account credential and session metadata remain inert", async () => {
  const value = { ...account(), get passwordHash(): never { return assert.fail("credential reached"); }, get sessionVersion(): never { return assert.fail("session reached"); }, get id(): never { return assert.fail("id reached"); } };
  assert.equal(await lift(value)(), "write");
});
test("original module and database bindings remain inert", async () => {
  const env = { getSessionAccount: () => account() };
  for (const name of ["prisma", "getSession", "NextResponse", "requireAccess"]) Object.defineProperty(env, name, { get(): never { return assert.fail("original binding reached"); } });
  assert.equal(await shell(env)(), "write");
});

test("synthetic falsy account values return null", async () => {
  for (const value of [undefined, false, 0, -0, "", NaN, 0n]) assert.equal(await lift(value)(), null);
});
test("synthetic truthy primitives without role return readonly", async () => {
  for (const value of [true, 1, "inert", 1n, Symbol("inert")]) assert.equal(await lift(value)(), "readonly");
});
test("synthetic falsy administration values return readonly", async () => {
  for (const value of [undefined, null, 0, -0, "", NaN, 0n]) assert.equal(await lift({ role: "write", engineAdmin: value })(), "readonly");
});
test("synthetic truthy administration stays a primitive write decision", async () => {
  const flag = { get then(): never { return assert.fail("flag then inspected"); }, [Symbol.toPrimitive](): never { return assert.fail("flag coerced"); }, toJSON(): never { return assert.fail("flag serialized"); } };
  assert.equal(await lift({ role: "write", engineAdmin: flag })(), "write");
});
test("synthetic administration Promise is not adopted as the return value", async () => {
  assert.equal(await lift({ role: "write", engineAdmin: Promise.resolve(false) })(), "write");
});

test("role withdrawal after provider call is observed after await", async () => {
  const value = account(); const result = lift(value)(); value.role = "readonly";
  assert.equal(await result, "readonly");
});
test("administration withdrawal after provider call is observed after await", async () => {
  const value = account(); const result = lift(value)(); value.engineAdmin = false;
  assert.equal(await result, "readonly");
});
test("successive calls perform fresh provider decisions without cache", async () => {
  let calls = 0; let current = account();
  const run = shell({ getSessionAccount: () => { calls++; return current; } });
  assert.equal(await run(), "write"); current = account("readonly", true);
  assert.equal(await run(), "readonly"); current = account();
  assert.equal(await run(), "write"); assert.equal(calls, 3);
});
test("concurrent reversed provider settlements keep independent results", async () => {
  const first = deferred(); const second = deferred(); let calls = 0;
  const run = shell({ getSessionAccount: () => (++calls === 1 ? first.promise : second.promise) });
  const one = run(); const two = run(); assert.notEqual(one, two);
  second.resolve(account("readonly", true)); assert.equal(await two, "readonly");
  first.resolve(account()); assert.equal(await one, "write"); assert.equal(calls, 2);
});
test("a provider failure does not cache later refusal or success", async () => {
  const reason = {}; let calls = 0;
  const run = shell({ getSessionAccount: () => { calls++; if (calls === 1) throw reason; return calls === 2 ? null : account(); } });
  await fault(() => run(), reason); assert.equal(await run(), null); assert.equal(await run(), "write"); assert.equal(calls, 3);
});
test("provider replacement is resolved afresh on the next call", async () => {
  const env = { getSessionAccount: () => account("readonly", true) }; const run = shell(env);
  assert.equal(await run(), "readonly"); env.getSessionAccount = () => account();
  assert.equal(await run(), "write");
});
test("separate inert shells do not share account decisions", async () => {
  assert.equal(await lift(account())(), "write"); assert.equal(await lift(account("write", false))(), "readonly"); assert.equal(await lift(null)(), null);
});
test("noncallable provider rejects with a TypeError", async () => {
  await assert.rejects(shell({ getSessionAccount: {} })(), error => (error as { name?: string }).name === "TypeError");
});
