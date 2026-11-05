import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct PUBLIC selected-declaration controls; historical36 remain frozen.
// Module/imports/initializers/neighbours/Kubernetes/HTTP/backend/recovery stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/lib/auth-server.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), 'ed932ca6285e1e0ddb73f7269cb846ddd44e2c457bae821cb9bfe0c6da22be56');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '79498931d610baef9c31648591cb952e8d2e9d70f8ad3cfe4f33e6cb30d6e544');
const ast = ts.createSourceFile('auth-server.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'ensureJwtSecret');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
assert.deepEqual(node.parameters.map(node => node.getText(ast)), []);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function ensureJwtSecret(): Promise<void> {\n  if (!process.env.BOTRUS_JWT_SECRET)\n    throw new Error(\"BOTRUS_JWT_SECRET must be supplied by the operator\");\n}");
assert.equal(digest(declaration), 'a45addc05383ad6569b1e4205dc1ab547d7651b3897f7b8ccdc3501d37f0cf53');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '4a6ff30cdfbc13454112ca4616526e127cd4289e098f203464741a0f1fc0185b');
const selected = declaration.replace(/^export\s+/, '');
const compiled = ts.transpileModule(selected, { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const javascript = compiled.outputText.trim();
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
assert.equal(javascript, 'async function ensureJwtSecret() {\n    if (!process.env.BOTRUS_JWT_SECRET)\n        throw new Error("BOTRUS_JWT_SECRET must be supplied by the operator");\n}');
let count = 0;
const control = (...args) => { count++; return test(...args); };
const message = "BOTRUS_JWT_SECRET must be supplied by the operator";
function load(binding, ErrorBinding = Error) {
    return vm.runInNewContext("(" + javascript + ")", { process: binding, Error: ErrorBinding });
}
const binding = (value) => ({ env: { BOTRUS_JWT_SECRET: value } });
const metadata = () => Object.freeze({ publicInputIdentity: Symbol("inert signing-input metadata") });
control("exact selected async declaration has no parameters and one pinned presence check", () => {
    assert.equal(load(binding(metadata())).length, 0);
    assert.equal(load(binding(metadata())).name, "ensureJwtSecret");
    assert.equal(declarations[0].parameters.length, 0);
    assert.equal(declarations[0].body.statements.length, 1);
});
const falsy = [["undefined", undefined], ["null", null], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n], ["empty text", ""]];
for (const [name, value] of falsy)
    control("falsy inert metadata rejects with fixed operator message: " + name, async () => {
        await assert.rejects(load(binding(value))(), (error) => error instanceof Error && error.message === message);
    });
const truthy = [["public text", "PUBLIC METADATA ONLY"], ["whitespace", " "], ["zero text", "0"], ["false text", "false"], ["one", 1], ["negative one", -1], ["bigint", 1n], ["symbol", Symbol("public")], ["object", metadata()], ["array", []], ["function", () => undefined]];
for (const [name, value] of truthy)
    control("truthy inert metadata fulfills void without validating material: " + name, async () => {
        assert.equal(await load(binding(value))(), undefined);
    });
control("reads process env then selected property exactly once without writes or enumeration", async () => {
    const events = [];
    const env = new Proxy({}, { get(_target, key) { events.push(String(key)); assert.equal(key, "BOTRUS_JWT_SECRET"); return metadata(); }, set() { assert.fail("env write"); }, ownKeys() { assert.fail("env enumeration"); } });
    const processBinding = new Proxy({}, { get(_target, key) { events.push(String(key)); assert.equal(key, "env"); return env; }, set() { assert.fail("process write"); }, ownKeys() { assert.fail("process enumeration"); } });
    assert.equal(await load(processBinding)(), undefined);
    assert.deepEqual(events, ["env", "BOTRUS_JWT_SECRET"]);
});
control("env getter fault becomes identical rejected value without synchronous throw", async () => {
    const fault = Object.freeze({ publicFault: "env" });
    const selected = load(Object.defineProperty({}, "env", { get() { throw fault; } }));
    let result;
    assert.doesNotThrow(() => { result = selected(); });
    await assert.rejects(result, (error) => error === fault);
});
control("selected property getter fault becomes identical rejected value", async () => {
    const fault = Symbol("public property fault");
    const env = Object.defineProperty({}, "BOTRUS_JWT_SECRET", { get() { throw fault; } });
    await assert.rejects(load({ env })(), (error) => error === fault);
});
control("null inert env refuses through ordinary async TypeError", async () => {
    await assert.rejects(load({ env: null })(), (error) => Object.getPrototypeOf(error).name === "TypeError");
});
control("undefined inert process refuses without consulting a real environment", async () => {
    await assert.rejects(load(undefined)(), (error) => Object.getPrototypeOf(error).name === "TypeError");
});
control("truthiness never reads thenable coercion iterator or metadata members", async () => {
    const value = new Proxy({}, { get() { assert.fail("metadata get"); }, getPrototypeOf() { assert.fail("metadata prototype"); }, ownKeys() { assert.fail("metadata keys"); }, getOwnPropertyDescriptor() { assert.fail("metadata descriptor"); } });
    assert.equal(await load(binding(value))(), undefined);
});
control("revoked metadata proxy stays truthy and is never inspected", async () => {
    const { proxy, revoke } = Proxy.revocable({}, {});
    revoke();
    assert.equal(await load(binding(proxy))(), undefined);
});
control("fresh property value is read on every call without cached acceptance", async () => {
    const env = { BOTRUS_JWT_SECRET: metadata() };
    const selected = load({ env });
    assert.equal(await selected(), undefined);
    env.BOTRUS_JWT_SECRET = undefined;
    await assert.rejects(selected(), { message });
    env.BOTRUS_JWT_SECRET = metadata();
    assert.equal(await selected(), undefined);
});
control("fresh env object is resolved on every call", async () => {
    let env = binding(metadata()).env;
    let reads = 0;
    const selected = load({ get env() { reads++; return env; } });
    await selected();
    env = binding("").env;
    await assert.rejects(selected(), { message });
    assert.equal(reads, 2);
});
control("truthy path never resolves the injected Error constructor", async () => {
    const selected = vm.runInNewContext("(" + javascript + ")", Object.defineProperty({ process: binding(metadata()) }, "Error", { get() { assert.fail("Error read"); } }));
    assert.equal(await selected(), undefined);
});
control("falsy path constructs only the fixed public message and rejects its exact instance", async () => {
    const events = [];
    const fault = Object.freeze({ publicFault: "constructed" });
    const ErrorBinding = new Proxy(function PublicError() { }, { construct(_target, args) { events.push(args); return fault; } });
    await assert.rejects(load(binding(""), ErrorBinding)(), (error) => error === fault);
    assert.equal(events.length, 1);
    const args = events[0];
    assert.equal(args.length, 1);
    assert.equal(args[0], message);
});
control("Error constructor fault becomes identical Promise rejection", async () => {
    const fault = Object.freeze({ publicFault: "constructor" });
    const ErrorBinding = new Proxy(function PublicError() { }, { construct() { throw fault; } });
    await assert.rejects(load(binding(false), ErrorBinding)(), (error) => error === fault);
});
control("this and extra arguments remain unobserved", async () => {
    const opaque = new Proxy({}, { get() { assert.fail("unused metadata read"); } });
    assert.equal(await load(binding(metadata())).call(opaque, opaque), undefined);
});
control("each invocation returns a separate Promise that fulfills undefined", async () => {
    const selected = load(binding(metadata()));
    const first = selected();
    const second = selected();
    assert.notEqual(first, second);
    assert.deepEqual(await Promise.all([first, second]), [undefined, undefined]);
});
control("frozen public env and metadata are accepted without mutation", async () => {
    const env = Object.freeze({ BOTRUS_JWT_SECRET: metadata() });
    const processBinding = Object.freeze({ env });
    assert.equal(await load(processBinding)(), undefined);
    assert.deepEqual(Reflect.ownKeys(env), ["BOTRUS_JWT_SECRET"]);
});
control("presence reads happen synchronously before asynchronous fulfillment observation", async () => {
    const events = [];
    const selected = load({ get env() { events.push("env"); return { get BOTRUS_JWT_SECRET() { events.push("input"); return metadata(); } }; } });
    const result = selected();
    events.push("returned");
    assert.deepEqual(events, ["env", "input", "returned"]);
    assert.equal(await result, undefined);
});
assert.equal(count, 36);
