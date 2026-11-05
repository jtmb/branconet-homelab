import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const source = readFileSync(fileURLToPath(new URL("../src/lib/accounts.ts", import.meta.url)), "utf8").replaceAll("\r\n", "\n");
const expectedHash = "5a858a0c7072ab0583dea19be4b9f01c49b87f7b77a3e125716d56ad8b0a8e21";
assert.equal(createHash("sha256").update(source).digest("hex"), expectedHash);
const ast = ts.createSourceFile("accounts.ts", source, ts.ScriptTarget.Latest, true);
const declaration = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "accountFailure");
assert.equal(declaration.length, 1);
const selected = declaration[0].getText(ast);
assert.match(selected, /^export function accountFailure\(error: unknown\)/);
const javascript = ts.transpileModule(selected.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText.trim();
type Failure = (error: unknown) => unknown;
const load = (NextResponse: unknown, AccountError: unknown): Failure => vm.runInNewContext("(" + javascript + ")", { NextResponse, AccountError });
type Event = [string, ...unknown[]];
function fixture(match: unknown, ...outputs: unknown[]) {
  const result = outputs.length ? outputs[0] : Object.freeze({ publicResponse: true });
  const events: Event[] = [];
  const error = Object.defineProperties({}, {
    message: { configurable: true, get() { events.push(["message"]); return "Synthetic public error"; } },
    status: { configurable: true, get() { events.push(["status"]); return 409; } },
  });
  const candidate = Object.defineProperty({}, Symbol.hasInstance, { configurable: true, get() {
    events.push(["hasInstance.get"]);
    return function(this: unknown, received: unknown) { events.push(["hasInstance.call", this, received]); return match; };
  } });
  const response = Object.defineProperty({}, "json", { configurable: true, get() {
    events.push(["json.get"]);
    return function(this: unknown, body: unknown, options: unknown) { events.push(["json.call", this, body, options]); return result; };
  } });
  return { events, error, candidate, response, result, run: () => load(response, candidate)(error) };
}
const labels = (events: Event[]) => events.map(e => e[0]);
function assertCall(f: ReturnType<typeof fixture>, matched: boolean, result: unknown = f.result) {
  assert.equal(f.run(), result);
  assert.deepEqual(labels(f.events), matched ? ["hasInstance.get", "hasInstance.call", "json.get", "message", "status", "json.call"] : ["hasInstance.get", "hasInstance.call", "json.get", "json.call"]);
  assert.equal(f.events[1][1], f.candidate);
  assert.equal(f.events[1][2], f.error);
  const call = f.events.at(-1)!;
  assert.equal(call[1], f.response);
  assert.equal(JSON.stringify(call[2]), JSON.stringify({ error: matched ? "Synthetic public error" : "Account operation unavailable" }));
  assert.equal(JSON.stringify(call[3]), JSON.stringify({ status: matched ? 409 : 503 }));
}

test("true branch evaluates member before message/status and preserves immediate receivers", () => assertCall(fixture(true), true));
test("false branch returns fixed unavailable response without input property reads", () => assertCall(fixture(false), false));

for (const [name, value, truth] of [
  ["undefined", undefined, false], ["null", null, false], ["false", false, false],
  ["zero", 0, false], ["empty", "", false], ["NaN", NaN, false],
  ["true", true, true], ["one", 1, true], ["text", "public", true],
  ["object", {}, true], ["array", [], true],
] as const) test("instance hook result uses ordinary truthiness: " + name, () => assertCall(fixture(value), truth));

for (const [name, error] of [
  ["undefined", undefined], ["null", null], ["false", false], ["true", true],
  ["zero", 0], ["number", 12], ["NaN", NaN], ["empty", ""],
  ["text", "public"], ["bigint", 7n], ["symbol", Symbol("public")],
] as const) test("false branch handles synthetic unknown input: " + name, () => {
  const f = fixture(false); const result = load(f.response, f.candidate)(error);
  assert.equal(result, f.result); assert.equal(f.events[1][2], error);
  assert.deepEqual(labels(f.events), ["hasInstance.get", "hasInstance.call", "json.get", "json.call"]);
  assert.equal(JSON.stringify(f.events.at(-1)![2]), '{"error":"Account operation unavailable"}');
  assert.equal(JSON.stringify(f.events.at(-1)![3]), '{"status":503}');
});

for (const matched of [true, false]) for (const [name, result] of [
  ["undefined", undefined], ["null", null], ["false", false], ["zero", 0],
  ["text", "public response"], ["symbol", Symbol("response")], ["object", Object.freeze({ response: "public" })],
] as const) test("immediate JSON result identity " + matched + "/" + name, () => assertCall(fixture(matched, result), matched, result));

for (const matched of [true, false]) test("returned thenable is not assimilated " + matched, () => {
  const result = Object.defineProperty({}, "then", { get() { assert.fail("synchronous declaration must not read then"); } });
  assertCall(fixture(matched, result), matched, result);
});

for (const field of ["message", "status"] as const) test("true branch forwards exact synthetic " + field + " metadata", () => {
  const f = fixture(true); const marker = Object.freeze({ synthetic: field });
  Object.defineProperty(f.error, field, { get() { f.events.push([field]); return marker; } });
  assert.equal(f.run(), f.result); const call = f.events.at(-1)!;
  assert.equal((call[field === "message" ? 2 : 3] as Record<string, unknown>)[field === "message" ? "error" : "status"], marker);
  assert.deepEqual(labels(f.events), ["hasInstance.get", "hasInstance.call", "json.get", "message", "status", "json.call"]);
});

for (const [stage, matched, expected] of [
  ["instance-get", true, ["hasInstance.get"]],
  ["instance-call", true, ["hasInstance.get", "hasInstance.call"]],
  ["json-get", true, ["hasInstance.get", "hasInstance.call", "json.get"]],
  ["json-get", false, ["hasInstance.get", "hasInstance.call", "json.get"]],
  ["message", true, ["hasInstance.get", "hasInstance.call", "json.get", "message"]],
  ["status", true, ["hasInstance.get", "hasInstance.call", "json.get", "message", "status"]],
  ["json-call", true, ["hasInstance.get", "hasInstance.call", "json.get", "message", "status", "json.call"]],
  ["json-call", false, ["hasInstance.get", "hasInstance.call", "json.get", "json.call"]],
] as const) test("exact synchronous fault propagates without retry: " + stage + "/" + matched, () => {
  const f = fixture(matched); const sentinel = Object.freeze({ syntheticFault: stage });
  if (stage === "instance-get") Object.defineProperty(f.candidate, Symbol.hasInstance, { get() { f.events.push(["hasInstance.get"]); throw sentinel; } });
  if (stage === "instance-call") Object.defineProperty(f.candidate, Symbol.hasInstance, { get() { f.events.push(["hasInstance.get"]); return function() { f.events.push(["hasInstance.call"]); throw sentinel; }; } });
  if (stage === "json-get") Object.defineProperty(f.response, "json", { get() { f.events.push(["json.get"]); throw sentinel; } });
  if (stage === "message" || stage === "status") Object.defineProperty(f.error, stage, { get() { f.events.push([stage]); throw sentinel; } });
  if (stage === "json-call") Object.defineProperty(f.response, "json", { get() { f.events.push(["json.get"]); return function() { f.events.push(["json.call"]); throw sentinel; }; } });
  assert.throws(f.run, e => e === sentinel); assert.deepEqual(labels(f.events), [...expected]);
});

test("JSON member is captured before message getter can replace it", () => {
  const f = fixture(true);
  Object.defineProperty(f.error, "message", { get() { f.events.push(["message"]); Object.defineProperty(f.response, "json", { value() { assert.fail("replacement must not run"); } }); return "Synthetic public error"; } });
  assertCall(f, true);
});
test("message getter runs before current status getter", () => {
  const f = fixture(true);
  Object.defineProperty(f.error, "message", { get() { f.events.push(["message"]); Object.defineProperty(f.error, "status", { get() { f.events.push(["status"]); return 418; } }); return "Synthetic public error"; } });
  assert.equal(f.run(), f.result); assert.equal(JSON.stringify(f.events.at(-1)![3]), '{"status":418}');
});
test("each call supplies new separate body and options objects", () => {
  const f = fixture(true); f.run(); f.run();
  const calls = f.events.filter(e => e[0] === "json.call");
  assert.equal(calls.length, 2); assert.notEqual(calls[0][2], calls[1][2]); assert.notEqual(calls[0][3], calls[1][3]); assert.notEqual(calls[0][2], calls[0][3]);
});
test("ordinary instanceof uses only inert synthetic class and instance", () => {
  class SyntheticError { message = "Synthetic public error"; status = 409; }
  const calls: unknown[][] = []; const response = { json(...args: unknown[]) { calls.push(args); return response; } };
  assert.equal(load(response, SyntheticError)(new SyntheticError()), response);
  assert.equal(JSON.stringify(calls), '[[{"error":"Synthetic public error"},{"status":409}]]');
});
test("ordinary instanceof rejects structural lookalike without forwarding fields", () => {
  class SyntheticError {}
  const calls: unknown[][] = []; const response = { json(...args: unknown[]) { calls.push(args); return response; } };
  assert.equal(load(response, SyntheticError)({ message: "PUBLIC UNSELECTED", status: 409 }), response);
  assert.equal(JSON.stringify(calls), '[[{"error":"Account operation unavailable"},{"status":503}]]');
});
