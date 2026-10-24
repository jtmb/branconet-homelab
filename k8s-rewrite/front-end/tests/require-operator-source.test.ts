import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";

// Only the selected declaration executes. Authorization, accounts and responses
// are inert metadata; synthetic malformed values characterize JavaScript only.
const requireTool = createRequire(import.meta.url);
const ts: typeof import("typescript") = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript");
const filename = path.resolve(import.meta.dirname, "../src/lib/permissions.ts");
const text = readFileSync(filename, "utf8");
const file = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const selected = file.statements.filter((node): node is import("typescript").FunctionDeclaration => ts.isFunctionDeclaration(node) && node.name?.text === "requireOperator");
assert.equal(selected.length, 1);
const declaration = selected[0].getText(file).replace(/^export\s+/, "");
const javascript = ts.transpileModule(`"use strict";\n${declaration}\nrequireOperator;`, { compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None } }).outputText;
type Operator = (...args: unknown[]) => unknown;
function shell(sandbox: Record<string, unknown>): Operator {
  const context = vm.createContext(sandbox, { codeGeneration: { strings: false, wasm: false } });
  return new vm.Script(javascript, { filename: "selected-require-operator-inert.js" }).runInContext(context, { timeout: 1000 }) as Operator;
}
function lift(dependency: unknown): Operator { return shell({ requireAccess: dependency }); }
function capture(run: () => unknown): unknown { try { run(); } catch (error) { return error; } assert.fail("expected synchronous fault"); }
function typeFault(run: () => unknown) { const error = capture(run) as { name?: string }; assert.equal(error.name, "TypeError"); }

test("selected declaration has only the literal true authorization call", () => {
  const node = selected[0]; assert.equal(node.parameters.length, 0); assert.equal(node.asteriskToken, undefined);
  assert.equal(node.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword), false);
  assert.equal(node.body?.statements.length, 1); const statement = node.body!.statements[0]; assert.ok(ts.isReturnStatement(statement));
  const call = statement.expression; assert.ok(call && ts.isCallExpression(call)); assert.ok(ts.isIdentifier(call.expression));
  assert.equal(call.expression.text, "requireAccess"); assert.equal(call.arguments.length, 1); assert.equal(call.arguments[0].kind, ts.SyntaxKind.TrueKeyword);
});
test("ordinary metadata result returns with identical reference", () => { const result = {}; assert.equal(lift(() => result)(), result); });
test("dependency receiver is undefined in strict evaluation", () => { lift(function (this: unknown) { assert.equal(this, undefined); })(); });
test("dependency receives exactly one Boolean true", () => { lift(function (...args: unknown[]) { assert.equal(args.length, 1); assert.equal(args[0], true); })(); });
test("caller arguments cannot replace the operator flag", () => { lift((flag: unknown) => assert.equal(flag, true))(false, "readonly", { engineAdmin: false }); });
test("forged caller receiver cannot replace the operator flag", () => { lift(function (this: unknown, flag: unknown) { assert.equal(this, undefined); assert.equal(flag, true); }).call({ engineAdmin: true }); });
test("caller argument properties remain unread", () => { const value = new Proxy({}, { get() { assert.fail("argument property read"); }, ownKeys() { assert.fail("argument enumeration"); } }); lift(() => 1)(value); });
test("caller receiver properties remain unread", () => { const receiver = new Proxy({}, { get() { assert.fail("receiver read"); } }); lift(() => 1).call(receiver); });
test("one invocation calls authorization once", () => { let calls = 0; lift(() => { calls++; return {}; })(); assert.equal(calls, 1); });
test("successive invocations obtain fresh results", () => { let calls = 0; const run = lift(() => ({ call: ++calls })); const a = run(); const b = run(); assert.notEqual(a, b); assert.equal(calls, 2); });
test("each invocation resolves the current binding", () => { const sandbox = { requireAccess: () => "first" }; const run = shell(sandbox); assert.equal(run(), "first"); sandbox.requireAccess = () => "second"; assert.equal(run(), "second"); });
test("call argument lists are distinct per invocation", () => { const arrays: unknown[][] = []; const run = lift(new Proxy(() => 0, { apply(_target, _receiver, args) { arrays.push(args); return 0; } })); run(); run(); assert.equal(arrays.length, 2); assert.notEqual(arrays[0], arrays[1]); assert.equal(arrays[0][0], true); assert.equal(arrays[1][0], true); });
test("callable proxy sees exact receiver and argument", () => { lift(new Proxy(() => 0, { apply(_target, receiver, args) { assert.equal(receiver, undefined); assert.equal(args.length, 1); assert.equal(args[0], true); return 0; } }))(); });
test("authorization properties are not inspected", () => { const dependency = new Proxy(() => 7, { get() { assert.fail("dependency property read"); } }); assert.equal(lift(dependency)(), 7); });
test("Function call receiver and extra arguments are ignored", () => { let count = 0; const run = lift(function (this: unknown, ...args: unknown[]) { count++; assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], true); }); run.call({ role: "write" }, false, 3); assert.equal(count, 1); });
test("detached operator alias keeps the exact dependency call", () => { const result = {}; const alias = lift(() => result); assert.equal(alias(), result); });
test("then getter on metadata result is never read", () => { const result = { get then(): never { return assert.fail("then inspected"); } }; assert.equal(lift(() => result)(), result); });
test("fulfilled synthetic Promise is returned without adoption", () => { const result = Promise.resolve({ synthetic: true }); assert.equal(lift(() => result)(), result); });
test("synthetic thenable is not invoked", () => { let called = false; const result = { then() { called = true; } }; assert.equal(lift(() => result)(), result); assert.equal(called, false); });
test("cyclic metadata is not traversed", () => { const result: { self?: unknown } = {}; result.self = result; assert.equal(lift(() => result)(), result); });
test("response metadata members remain inert", () => { const result = { get status(): never { return assert.fail("status"); }, get json(): never { return assert.fail("json"); } }; assert.equal(lift(() => result)(), result); });
test("account metadata members remain inert", () => { const result = { get role(): never { return assert.fail("role"); }, get sessionVersion(): never { return assert.fail("version"); }, get engineAdmin(): never { return assert.fail("admin"); } }; assert.equal(lift(() => result)(), result); });
test("synthetic null result remains null", () => { assert.equal(lift(() => null)(), null); });
test("synthetic undefined result remains undefined", () => { assert.equal(lift(() => undefined)(), undefined); });
test("synthetic false result remains false", () => { assert.equal(lift(() => false)(), false); });
test("synthetic zero result remains zero", () => { assert.equal(lift(() => 0)(), 0); });
test("synthetic empty string remains unchanged", () => { assert.equal(lift(() => "")(), ""); });
test("synthetic NaN remains NaN", () => { assert.ok(Number.isNaN(lift(() => NaN)())); });
test("synthetic negative zero keeps its sign", () => { assert.ok(Object.is(lift(() => -0)(), -0)); });
test("synthetic symbol preserves identity", () => { const result = Symbol("inert"); assert.equal(lift(() => result)(), result); });
test("synthetic bigint preserves value", () => { assert.equal(lift(() => 17n)(), 17n); });
test("synthetic nonempty string preserves value", () => { assert.equal(lift(() => "inert refusal metadata")(), "inert refusal metadata"); });
test("function result is not invoked", () => { const result = () => assert.fail("result invoked"); assert.equal(lift(() => result)(), result); });
test("proxy result is not inspected", () => { const result = new Proxy({}, { get() { assert.fail("result property"); }, getPrototypeOf() { assert.fail("result prototype"); } }); assert.equal(lift(() => result)(), result); });
test("revoked proxy result is returned without inspection", () => { const result = Proxy.revocable({}, {}); result.revoke(); assert.equal(lift(() => result.proxy)(), result.proxy); });
test("synchronous Error identity propagates", () => { const error = new Error("synthetic"); assert.equal(capture(lift(() => { throw error; })), error); });
test("synchronous null throw is not transformed", () => { assert.equal(capture(lift(() => { throw null; })), null); });
test("synchronous symbol throw is not transformed", () => { const error = Symbol("synthetic"); assert.equal(capture(lift(() => { throw error; })), error); });
test("noncallable binding throws before returning a result", () => { typeFault(lift(null)); });
test("revoked callable binding propagates TypeError", () => { const dependency = Proxy.revocable(() => 0, {}); dependency.revoke(); typeFault(lift(dependency.proxy)); });
test("authorization uses call rather than construct", () => { let applied = false; const dependency = new Proxy(() => 3, { construct() { assert.fail("construct"); }, apply(_target, receiver, args) { applied = true; assert.equal(receiver, undefined); assert.equal(args[0], true); return 3; } }); assert.equal(lift(dependency)(), 3); assert.equal(applied, true); });
test("a property-held callable is detached after binding resolution", () => { const object = { dependency(this: unknown) { assert.equal(this, undefined); return 8; } }; assert.equal(lift(object.dependency)(), 8); });
test("reentrant calls have independent results and literal flags", () => { let depth = 0; let run: Operator; run = lift((flag: unknown) => { assert.equal(flag, true); if (depth++ === 0) { const inner = run(); assert.equal(inner, "inner"); return "outer"; } return "inner"; }); assert.equal(run(), "outer"); assert.equal(depth, 2); });
test("separate inert shells do not share authorization state", () => { assert.equal(lift(() => "a")(), "a"); assert.equal(lift(() => "b")(), "b"); });
test("dependency settles synchronously before caller continuation", () => { const events: string[] = []; const run = lift(() => { events.push("dependency"); return 1; }); events.push("before"); assert.equal(run(), 1); events.push("after"); assert.equal(events.join(","), "before,dependency,after"); });
test("metadata serialization hooks remain unread", () => { const result = { toJSON(): never { return assert.fail("serialization"); }, [Symbol.toPrimitive](): never { return assert.fail("coercion"); } }; assert.equal(lift(() => result)(), result); });
test("later synchronous fault is not hidden by earlier success", () => { const error = {}; let calls = 0; const run = lift(() => { if (++calls === 2) throw error; return 1; }); assert.equal(run(), 1); assert.equal(capture(run), error); assert.equal(calls, 2); });
test("rejected synthetic Promise retains identity and rejection", async () => { const reason = {}; const result = Promise.reject(reason); assert.equal(lift(() => result)(), result); await assert.rejects(result, error => error === reason); });
test("binding accessor is read once per invocation", () => { let reads = 0; const sandbox = Object.defineProperty({}, "requireAccess", { get() { reads++; return () => reads; } }); const run = shell(sandbox); assert.equal(run(), 1); assert.equal(run(), 2); assert.equal(reads, 2); });
test("VM global accessor fault yields ReferenceError after one getter read", () => { let reads = 0; const injected = {}; const sandbox = Object.defineProperty({}, "requireAccess", { get() { reads++; throw injected; } }); const run = shell(sandbox); const observed = capture(run) as { name: string; message: string }; assert.equal(reads, 1); assert.equal(observed.name, "ReferenceError"); assert.equal(observed.message, "requireAccess is not defined"); assert.notEqual(observed, injected); });
test("two pending synthetic results stay separate and return immediately", async () => { const resolvers: ((x: number) => void)[] = []; const results: Promise<number>[] = []; const run = lift(() => { const p = new Promise<number>(resolve => resolvers.push(resolve)); results.push(p); return p; }); const first = run(); const second = run(); assert.equal(first, results[0]); assert.equal(second, results[1]); assert.notEqual(first, second); resolvers[1](2); resolvers[0](1); assert.equal(await first, 1); assert.equal(await second, 2); });
test("a throwing proxy apply trap propagates its exact fault once", () => { const error = {}; let calls = 0; const run = lift(new Proxy(() => 0, { apply() { calls++; throw error; } })); assert.equal(capture(run), error); assert.equal(calls, 1); });
