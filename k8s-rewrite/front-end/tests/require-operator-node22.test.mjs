// DISTINCT NEW PUBLIC52 controls; historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
// Only the selected declaration executes. Authorization, accounts and responses
// are inert metadata; synthetic malformed values characterize JavaScript only.
const requireTool = createRequire(import.meta.url);
const ts = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript");
const filename = path.resolve(import.meta.dirname, "../src/lib/permissions.ts");
const text = readFileSync(filename, "utf8");
const file = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const selected = file.statements.filter((node) => ts.isFunctionDeclaration(node) && node.name?.text === "requireOperator");
assert.equal(selected.length, 1);
const declaration = selected[0].getText(file).replace(/^export\s+/, "");
const javascript = ts.transpileModule(`"use strict";\n${declaration}\nrequireOperator;`, { compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None } }).outputText;
function shell(sandbox) {
    const context = vm.createContext(sandbox, { codeGeneration: { strings: false, wasm: false } });
    return new vm.Script(javascript, { filename: "selected-require-operator-inert.js" }).runInContext(context, { timeout: 1000 });
}
function lift(dependency) { return shell({ requireAccess: dependency }); }
function capture(run) { try {
    run();
}
catch (error) {
    return error;
} assert.fail("expected synchronous fault"); }
function typeFault(run) { const error = capture(run); assert.equal(error.name, "TypeError"); }
control("selected declaration has only the literal true authorization call", () => {
    const node = selected[0];
    assert.equal(node.parameters.length, 0);
    assert.equal(node.asteriskToken, undefined);
    assert.equal(node.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword), false);
    assert.equal(node.body?.statements.length, 1);
    const statement = node.body.statements[0];
    assert.ok(ts.isReturnStatement(statement));
    const call = statement.expression;
    assert.ok(call && ts.isCallExpression(call));
    assert.ok(ts.isIdentifier(call.expression));
    assert.equal(call.expression.text, "requireAccess");
    assert.equal(call.arguments.length, 1);
    assert.equal(call.arguments[0].kind, ts.SyntaxKind.TrueKeyword);
});
control("ordinary metadata result returns with identical reference", () => { const result = {}; assert.equal(lift(() => result)(), result); });
control("dependency receiver is undefined in strict evaluation", () => { lift(function () { assert.equal(this, undefined); })(); });
control("dependency receives exactly one Boolean true", () => { lift(function (...args) { assert.equal(args.length, 1); assert.equal(args[0], true); })(); });
control("caller arguments cannot replace the operator flag", () => { lift((flag) => assert.equal(flag, true))(false, "readonly", { engineAdmin: false }); });
control("forged caller receiver cannot replace the operator flag", () => { lift(function (flag) { assert.equal(this, undefined); assert.equal(flag, true); }).call({ engineAdmin: true }); });
control("caller argument properties remain unread", () => { const value = new Proxy({}, { get() { assert.fail("argument property read"); }, ownKeys() { assert.fail("argument enumeration"); } }); lift(() => 1)(value); });
control("caller receiver properties remain unread", () => { const receiver = new Proxy({}, { get() { assert.fail("receiver read"); } }); lift(() => 1).call(receiver); });
control("one invocation calls authorization once", () => { let calls = 0; lift(() => { calls++; return {}; })(); assert.equal(calls, 1); });
control("successive invocations obtain fresh results", () => { let calls = 0; const run = lift(() => ({ call: ++calls })); const a = run(); const b = run(); assert.notEqual(a, b); assert.equal(calls, 2); });
control("each invocation resolves the current binding", () => { const sandbox = { requireAccess: () => "first" }; const run = shell(sandbox); assert.equal(run(), "first"); sandbox.requireAccess = () => "second"; assert.equal(run(), "second"); });
control("call argument lists are distinct per invocation", () => { const arrays = []; const run = lift(new Proxy(() => 0, { apply(_target, _receiver, args) { arrays.push(args); return 0; } })); run(); run(); assert.equal(arrays.length, 2); assert.notEqual(arrays[0], arrays[1]); assert.equal(arrays[0][0], true); assert.equal(arrays[1][0], true); });
control("callable proxy sees exact receiver and argument", () => { lift(new Proxy(() => 0, { apply(_target, receiver, args) { assert.equal(receiver, undefined); assert.equal(args.length, 1); assert.equal(args[0], true); return 0; } }))(); });
control("authorization properties are not inspected", () => { const dependency = new Proxy(() => 7, { get() { assert.fail("dependency property read"); } }); assert.equal(lift(dependency)(), 7); });
control("Function call receiver and extra arguments are ignored", () => { let count = 0; const run = lift(function (...args) { count++; assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], true); }); run.call({ role: "write" }, false, 3); assert.equal(count, 1); });
control("detached operator alias keeps the exact dependency call", () => { const result = {}; const alias = lift(() => result); assert.equal(alias(), result); });
control("then getter on metadata result is never read", () => { const result = { get then() { return assert.fail("then inspected"); } }; assert.equal(lift(() => result)(), result); });
control("fulfilled synthetic Promise is returned without adoption", () => { const result = Promise.resolve({ synthetic: true }); assert.equal(lift(() => result)(), result); });
control("synthetic thenable is not invoked", () => { let called = false; const result = { then() { called = true; } }; assert.equal(lift(() => result)(), result); assert.equal(called, false); });
control("cyclic metadata is not traversed", () => { const result = {}; result.self = result; assert.equal(lift(() => result)(), result); });
control("response metadata members remain inert", () => { const result = { get status() { return assert.fail("status"); }, get json() { return assert.fail("json"); } }; assert.equal(lift(() => result)(), result); });
control("account metadata members remain inert", () => { const result = { get role() { return assert.fail("role"); }, get sessionVersion() { return assert.fail("version"); }, get engineAdmin() { return assert.fail("admin"); } }; assert.equal(lift(() => result)(), result); });
control("synthetic null result remains null", () => { assert.equal(lift(() => null)(), null); });
control("synthetic undefined result remains undefined", () => { assert.equal(lift(() => undefined)(), undefined); });
control("synthetic false result remains false", () => { assert.equal(lift(() => false)(), false); });
control("synthetic zero result remains zero", () => { assert.equal(lift(() => 0)(), 0); });
control("synthetic empty string remains unchanged", () => { assert.equal(lift(() => "")(), ""); });
control("synthetic NaN remains NaN", () => { assert.ok(Number.isNaN(lift(() => NaN)())); });
control("synthetic negative zero keeps its sign", () => { assert.ok(Object.is(lift(() => -0)(), -0)); });
control("synthetic symbol preserves identity", () => { const result = Symbol("inert"); assert.equal(lift(() => result)(), result); });
control("synthetic bigint preserves value", () => { assert.equal(lift(() => 17n)(), 17n); });
control("synthetic nonempty string preserves value", () => { assert.equal(lift(() => "inert refusal metadata")(), "inert refusal metadata"); });
control("function result is not invoked", () => { const result = () => assert.fail("result invoked"); assert.equal(lift(() => result)(), result); });
control("proxy result is not inspected", () => { const result = new Proxy({}, { get() { assert.fail("result property"); }, getPrototypeOf() { assert.fail("result prototype"); } }); assert.equal(lift(() => result)(), result); });
control("revoked proxy result is returned without inspection", () => { const result = Proxy.revocable({}, {}); result.revoke(); assert.equal(lift(() => result.proxy)(), result.proxy); });
control("synchronous Error identity propagates", () => { const error = new Error("synthetic"); assert.equal(capture(lift(() => { throw error; })), error); });
control("synchronous null throw is not transformed", () => { assert.equal(capture(lift(() => { throw null; })), null); });
control("synchronous symbol throw is not transformed", () => { const error = Symbol("synthetic"); assert.equal(capture(lift(() => { throw error; })), error); });
control("noncallable binding throws before returning a result", () => { typeFault(lift(null)); });
control("revoked callable binding propagates TypeError", () => { const dependency = Proxy.revocable(() => 0, {}); dependency.revoke(); typeFault(lift(dependency.proxy)); });
control("authorization uses call rather than construct", () => { let applied = false; const dependency = new Proxy(() => 3, { construct() { assert.fail("construct"); }, apply(_target, receiver, args) { applied = true; assert.equal(receiver, undefined); assert.equal(args[0], true); return 3; } }); assert.equal(lift(dependency)(), 3); assert.equal(applied, true); });
control("a property-held callable is detached after binding resolution", () => { const object = { dependency() { assert.equal(this, undefined); return 8; } }; assert.equal(lift(object.dependency)(), 8); });
control("reentrant calls have independent results and literal flags", () => { let depth = 0; let run; run = lift((flag) => { assert.equal(flag, true); if (depth++ === 0) {
    const inner = run();
    assert.equal(inner, "inner");
    return "outer";
} return "inner"; }); assert.equal(run(), "outer"); assert.equal(depth, 2); });
control("separate inert shells do not share authorization state", () => { assert.equal(lift(() => "a")(), "a"); assert.equal(lift(() => "b")(), "b"); });
control("dependency settles synchronously before caller continuation", () => { const events = []; const run = lift(() => { events.push("dependency"); return 1; }); events.push("before"); assert.equal(run(), 1); events.push("after"); assert.equal(events.join(","), "before,dependency,after"); });
control("metadata serialization hooks remain unread", () => { const result = { toJSON() { return assert.fail("serialization"); }, [Symbol.toPrimitive]() { return assert.fail("coercion"); } }; assert.equal(lift(() => result)(), result); });
control("later synchronous fault is not hidden by earlier success", () => { const error = {}; let calls = 0; const run = lift(() => { if (++calls === 2)
    throw error; return 1; }); assert.equal(run(), 1); assert.equal(capture(run), error); assert.equal(calls, 2); });
control("rejected synthetic Promise retains identity and rejection", async () => { const reason = {}; const result = Promise.reject(reason); assert.equal(lift(() => result)(), result); await assert.rejects(result, error => error === reason); });
control("binding accessor is read once per invocation", () => { let reads = 0; const sandbox = Object.defineProperty({}, "requireAccess", { get() { reads++; return () => reads; } }); const run = shell(sandbox); assert.equal(run(), 1); assert.equal(run(), 2); assert.equal(reads, 2); });
control("VM global accessor fault yields ReferenceError after one getter read", () => { let reads = 0; const injected = {}; const sandbox = Object.defineProperty({}, "requireAccess", { get() { reads++; throw injected; } }); const run = shell(sandbox); const observed = capture(run); assert.equal(reads, 1); assert.equal(observed.name, "ReferenceError"); assert.equal(observed.message, "requireAccess is not defined"); assert.notEqual(observed, injected); });
control("two pending synthetic results stay separate and return immediately", async () => { const resolvers = []; const results = []; const run = lift(() => { const p = new Promise(resolve => resolvers.push(resolve)); results.push(p); return p; }); const first = run(); const second = run(); assert.equal(first, results[0]); assert.equal(second, results[1]); assert.notEqual(first, second); resolvers[1](2); resolvers[0](1); assert.equal(await first, 1); assert.equal(await second, 2); });
control("a throwing proxy apply trap propagates its exact fault once", () => { const error = {}; let calls = 0; const run = lift(new Proxy(() => 0, { apply() { calls++; throw error; } })); assert.equal(capture(run), error); assert.equal(calls, 1); });
assert.equal(count, 52);
assert.equal(process.version, "v22.23.3");
assert.equal(ts.version, "5.9.3");
