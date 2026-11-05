import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE only. Tool configuration locates the compiler; the selected
// function receives an inert process binding, never the real process environment.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth-server.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.equal(createHash("sha256").update(source).digest("hex"), "ed932ca6285e1e0ddb73f7269cb846ddd44e2c457bae821cb9bfe0c6da22be56");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
const ast = ts.createSourceFile("auth-server.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "ensureJwtSecret");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
assert.equal(createHash("sha256").update(declaration).digest("hex"), "a45addc05383ad6569b1e4205dc1ab547d7651b3897f7b8ccdc3501d37f0cf53");
const javascript = ts.transpileModule(declaration.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText.trim();
assert.equal(javascript, 'async function ensureJwtSecret() {\n    if (!process.env.BOTRUS_JWT_SECRET)\n        throw new Error("BOTRUS_JWT_SECRET must be supplied by the operator");\n}');
type Selected = (...args: unknown[]) => Promise<void>;
const message = "BOTRUS_JWT_SECRET must be supplied by the operator";
function load(binding: unknown, ErrorBinding: unknown = Error): Selected {
  return vm.runInNewContext("(" + javascript + ")", { process: binding, Error: ErrorBinding });
}
const binding = (value: unknown) => ({ env: { BOTRUS_JWT_SECRET: value } });
const metadata = () => Object.freeze({ publicInputIdentity: Symbol("inert signing-input metadata") });

test("exact selected async declaration has no parameters and one pinned presence check", () => {
  assert.equal(load(binding(metadata())).length, 0);
  assert.equal(load(binding(metadata())).name, "ensureJwtSecret");
  assert.equal(declarations[0].parameters.length, 0);
  assert.equal(declarations[0].body.statements.length, 1);
});
const falsy = [["undefined", undefined], ["null", null], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n], ["empty text", ""]] as const;
for (const [name, value] of falsy) test("falsy inert metadata rejects with fixed operator message: " + name, async () => {
  await assert.rejects(load(binding(value))(), (error: unknown) => error instanceof Error && error.message === message);
});
const truthy = [["public text", "PUBLIC METADATA ONLY"], ["whitespace", " "], ["zero text", "0"], ["false text", "false"], ["one", 1], ["negative one", -1], ["bigint", 1n], ["symbol", Symbol("public")], ["object", metadata()], ["array", []], ["function", () => undefined]] as const;
for (const [name, value] of truthy) test("truthy inert metadata fulfills void without validating material: " + name, async () => {
  assert.equal(await load(binding(value))(), undefined);
});
test("reads process env then selected property exactly once without writes or enumeration", async () => {
  const events: string[] = [];
  const env = new Proxy({}, { get(_target, key) { events.push(String(key)); assert.equal(key, "BOTRUS_JWT_SECRET"); return metadata(); }, set() { assert.fail("env write"); }, ownKeys() { assert.fail("env enumeration"); } });
  const processBinding = new Proxy({}, { get(_target, key) { events.push(String(key)); assert.equal(key, "env"); return env; }, set() { assert.fail("process write"); }, ownKeys() { assert.fail("process enumeration"); } });
  assert.equal(await load(processBinding)(), undefined);
  assert.deepEqual(events, ["env", "BOTRUS_JWT_SECRET"]);
});
test("env getter fault becomes identical rejected value without synchronous throw", async () => {
  const fault = Object.freeze({ publicFault: "env" });
  const selected = load(Object.defineProperty({}, "env", { get() { throw fault; } }));
  let result!: Promise<void>;
  assert.doesNotThrow(() => { result = selected(); });
  await assert.rejects(result, (error: unknown) => error === fault);
});
test("selected property getter fault becomes identical rejected value", async () => {
  const fault = Symbol("public property fault");
  const env = Object.defineProperty({}, "BOTRUS_JWT_SECRET", { get() { throw fault; } });
  await assert.rejects(load({ env })(), (error: unknown) => error === fault);
});
test("null inert env refuses through ordinary async TypeError", async () => {
  await assert.rejects(load({ env: null })(), (error: unknown) => Object.getPrototypeOf(error).name === "TypeError");
});
test("undefined inert process refuses without consulting a real environment", async () => {
  await assert.rejects(load(undefined)(), (error: unknown) => Object.getPrototypeOf(error).name === "TypeError");
});
test("truthiness never reads thenable coercion iterator or metadata members", async () => {
  const value = new Proxy({}, { get() { assert.fail("metadata get"); }, getPrototypeOf() { assert.fail("metadata prototype"); }, ownKeys() { assert.fail("metadata keys"); }, getOwnPropertyDescriptor() { assert.fail("metadata descriptor"); } });
  assert.equal(await load(binding(value))(), undefined);
});
test("revoked metadata proxy stays truthy and is never inspected", async () => {
  const { proxy, revoke } = Proxy.revocable({}, {}); revoke();
  assert.equal(await load(binding(proxy))(), undefined);
});
test("fresh property value is read on every call without cached acceptance", async () => {
  const env = { BOTRUS_JWT_SECRET: metadata() as unknown }; const selected = load({ env });
  assert.equal(await selected(), undefined); env.BOTRUS_JWT_SECRET = undefined;
  await assert.rejects(selected(), { message }); env.BOTRUS_JWT_SECRET = metadata();
  assert.equal(await selected(), undefined);
});
test("fresh env object is resolved on every call", async () => {
  let env = binding(metadata()).env; let reads = 0;
  const selected = load({ get env() { reads++; return env; } });
  await selected(); env = binding("").env; await assert.rejects(selected(), { message });
  assert.equal(reads, 2);
});
test("truthy path never resolves the injected Error constructor", async () => {
  const selected: Selected = vm.runInNewContext("(" + javascript + ")", Object.defineProperty({ process: binding(metadata()) }, "Error", { get() { assert.fail("Error read"); } }));
  assert.equal(await selected(), undefined);
});
test("falsy path constructs only the fixed public message and rejects its exact instance", async () => {
  const events: unknown[] = []; const fault = Object.freeze({ publicFault: "constructed" });
  const ErrorBinding = new Proxy(function PublicError() {}, { construct(_target, args) { events.push(args); return fault; } });
  await assert.rejects(load(binding(""), ErrorBinding)(), (error: unknown) => error === fault);
  assert.equal(events.length, 1);
  const args = events[0] as unknown[];
  assert.equal(args.length, 1);
  assert.equal(args[0], message);
});
test("Error constructor fault becomes identical Promise rejection", async () => {
  const fault = Object.freeze({ publicFault: "constructor" });
  const ErrorBinding = new Proxy(function PublicError() {}, { construct() { throw fault; } });
  await assert.rejects(load(binding(false), ErrorBinding)(), (error: unknown) => error === fault);
});
test("this and extra arguments remain unobserved", async () => {
  const opaque = new Proxy({}, { get() { assert.fail("unused metadata read"); } });
  assert.equal(await load(binding(metadata())).call(opaque, opaque), undefined);
});
test("each invocation returns a separate Promise that fulfills undefined", async () => {
  const selected = load(binding(metadata())); const first = selected(); const second = selected();
  assert.notEqual(first, second); assert.deepEqual(await Promise.all([first, second]), [undefined, undefined]);
});
test("frozen public env and metadata are accepted without mutation", async () => {
  const env = Object.freeze({ BOTRUS_JWT_SECRET: metadata() }); const processBinding = Object.freeze({ env });
  assert.equal(await load(processBinding)(), undefined);
  assert.deepEqual(Reflect.ownKeys(env), ["BOTRUS_JWT_SECRET"]);
});
test("presence reads happen synchronously before asynchronous fulfillment observation", async () => {
  const events: string[] = [];
  const selected = load({ get env() { events.push("env"); return { get BOTRUS_JWT_SECRET() { events.push("input"); return metadata(); } }; } });
  const result = selected(); events.push("returned");
  assert.deepEqual(events, ["env", "input", "returned"]);
  assert.equal(await result, undefined);
});
