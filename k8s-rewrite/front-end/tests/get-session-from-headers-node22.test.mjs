import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct PUBLIC selected-declaration controls; historical65 remain frozen.
// Module/imports/initializers/neighbours/Kubernetes/HTTP/backend/recovery stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/lib/auth.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), '932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff');
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'f190c4ba27ee2069a799ed9aa5cd37e6a69ebba70bcd05f927c3ad8eeecdc7d8');
const ast = ts.createSourceFile('auth.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSessionFromHeaders');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
assert.deepEqual(node.parameters.map(node => node.getText(ast)), ['cookieHeader: string | null']);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function getSessionFromHeaders(\n  cookieHeader: string | null\n): Promise<Session | null> {\n  if (!cookieHeader) return null;\n  const match = cookieHeader.match(\n    new RegExp(`(?:^|;\\\\s*)${AUTH_COOKIE}=([^;]*)`)\n  );\n  const token = match?.[1];\n  if (!token) return null;\n  const payload = await verifyJWT(token);\n  if (!payload) return null;\n  return currentSession(payload);\n}");
assert.equal(digest(declaration), '46335e19c65ac7f64ae3d6bb3854bf373aca39d6c9aeb83833378e0d389c23e9');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '6e4c6280328981af61099da030b060887d75c7020221075e83dee27b5b2a26d8');
const selected = declaration.replace(/^export\s+/, '');
const compiled = ts.transpileModule(selected, { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const javascript = compiled.outputText.trim();
assert.ok(!javascript.includes('import ') && !javascript.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const cookie = "botrus_auth_token";
const header = (value = "PUBLIC_STUB_A") => cookie + "=" + value;
const payload = Object.freeze({ publicIdentity: "VERIFIER_METADATA" });
const session = Object.freeze({ publicIdentity: "ACCOUNT_METADATA" });
const fail = () => assert.fail("unreachable synthetic binding");
function load(verify = fail, current = fail, RegExpBinding = RegExp) {
    return vm.runInNewContext("(" + javascript + ")", { AUTH_COOKIE: cookie, verifyJWT: verify, currentSession: current, RegExp: RegExpBinding });
}
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
control("one pinned async declaration, one parameter and seven ordered statements", () => {
    const selected = load();
    assert.equal(selected.name, "getSessionFromHeaders");
    assert.equal(selected.length, 1);
    assert.equal(declarations[0].parameters.length, 1);
    assert.equal(declarations[0].body.statements.length, 7);
});
const falsy = [["null", null], ["empty", ""], ["undefined", undefined], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]];
for (const [name, value] of falsy)
    control("falsy header metadata short circuits: " + name, async () => {
        const forbiddenRegExp = new Proxy(function PublicRegExp() { }, { construct() { assert.fail("unexpected construction"); } });
        assert.equal(await load(fail, fail, forbiddenRegExp)(value), null);
    });
const absent = ["unrelated=PUBLIC", "xbotrus_auth_token=PUBLIC", "botrus_auth_token_suffix=PUBLIC", "BOTRUS_AUTH_TOKEN=PUBLIC", "botrus_auth_token =PUBLIC", " botrus_auth_token=PUBLIC", "a=PUBLIC,botrus_auth_token=PUBLIC", "botrus_auth_token"];
for (const value of absent)
    control("exact parser rejects nonmatching public metadata: " + value, async () => {
        assert.equal(await load()(value), null);
    });
const matches = [
    [header(), "PUBLIC_STUB_A"], ["a=PUBLIC;" + header(), "PUBLIC_STUB_A"],
    ["a=PUBLIC; " + header(), "PUBLIC_STUB_A"], ["a=PUBLIC;\t " + header(), "PUBLIC_STUB_A"],
    [header() + ";a=PUBLIC", "PUBLIC_STUB_A"], [header("PUBLIC=TAIL"), "PUBLIC=TAIL"],
    [header("PUBLIC%20TEXT"), "PUBLIC%20TEXT"], [header(" PUBLIC "), " PUBLIC "],
    [header("0"), "0"], [header("PUBLIC,TAIL"), "PUBLIC,TAIL"],
    [header("PUBLIC_FIRST") + ";" + header("PUBLIC_SECOND"), "PUBLIC_FIRST"],
    ["a=PUBLIC;\n" + header(), "PUBLIC_STUB_A"],
];
for (const [value, extracted] of matches)
    control("exact source passes parser metadata unchanged: " + JSON.stringify(value), async () => {
        const calls = [];
        const selected = load((...args) => { assert.equal(args.length, 1); assert.equal(args[0], extracted); calls.push("verify"); return payload; }, (...args) => { assert.equal(args.length, 1); assert.equal(args[0], payload); calls.push("current"); return session; });
        assert.equal(await selected(value), session);
        assert.deepEqual(calls, ["verify", "current"]);
    });
for (const value of [header(""), header("") + ";" + header("PUBLIC_LATER")])
    control("empty first capture refuses without duplicate fallback: " + value, async () => {
        assert.equal(await load()(value), null);
    });
for (const [name, value] of falsy)
    control("falsy verifier metadata refuses account lookup: " + name, async () => {
        assert.equal(await load(() => value)(header()), null);
    });
const truthy = [["object", payload], ["public text", "PUBLIC_PAYLOAD"], ["one", 1], ["bigint", 1n], ["symbol", Symbol("public payload")], ["array", []], ["function", () => undefined]];
for (const [name, value] of truthy)
    control("truthy verifier metadata is forwarded by identity: " + name, async () => {
        assert.equal(await load(() => value, (seen) => { assert.equal(seen, value); return session; })(header()), session);
    });
control("verifier promise is awaited before current metadata lookup", async () => {
    const pending = deferred();
    const events = [];
    const result = load(() => { events.push("verify"); return pending.promise; }, (seen) => { assert.equal(seen, payload); events.push("current"); return session; })(header());
    assert.deepEqual(events, ["verify"]);
    pending.resolve(payload);
    assert.equal(await result, session);
    assert.deepEqual(events, ["verify", "current"]);
});
control("current metadata promise is adopted and no intermediate identity is released", async () => {
    const pending = deferred();
    let called = false;
    let settled = false;
    const result = load(() => payload, () => { called = true; return pending.promise; })(header());
    result.then(() => { settled = true; });
    await Promise.resolve();
    assert.equal(called, true);
    assert.equal(settled, false);
    pending.resolve(session);
    assert.equal(await result, session);
});
control("synchronous verifier fault is an identical rejection without current lookup", async () => {
    const fault = Object.freeze({ publicFault: "verify" });
    let result;
    assert.doesNotThrow(() => { result = load(() => { throw fault; })(header()); });
    await assert.rejects(result, (seen) => seen === fault);
});
control("asynchronous verifier fault is an identical rejection", async () => {
    const fault = Symbol("public verifier rejection");
    await assert.rejects(load(() => Promise.reject(fault))(header()), (seen) => seen === fault);
});
control("synchronous current metadata fault is an identical rejection", async () => {
    const fault = Object.freeze({ publicFault: "current" });
    await assert.rejects(load(() => payload, () => { throw fault; })(header()), (seen) => seen === fault);
});
control("asynchronous current metadata fault is an identical rejection", async () => {
    const fault = Symbol("public current rejection");
    await assert.rejects(load(() => payload, () => Promise.reject(fault))(header()), (seen) => seen === fault);
});
control("current null result stays null without replacing it with verifier metadata", async () => {
    assert.equal(await load(() => payload, () => null)(header()), null);
});
control("source forwards unexpected current metadata unchanged without validation claim", async () => {
    assert.equal(await load(() => payload, () => undefined)(header()), undefined);
});
control("match receiver, regexp source and flags are exact with no mutation", async () => {
    let receiver;
    let reads = 0;
    let calls = 0;
    const metadata = Object.freeze({ get match() { reads++; return function (...args) { receiver = this; calls++; assert.equal(args.length, 1); const pattern = args[0]; assert.equal(pattern.source, "(?:^|;\\s*)botrus_auth_token=([^;]*)"); assert.equal(pattern.flags, ""); return null; }; } });
    assert.equal(await load()(metadata), null);
    assert.equal(receiver, metadata);
    assert.equal(reads, 1);
    assert.equal(calls, 1);
});
control("match getter fault rejects identically before verifier", async () => {
    const fault = Symbol("public match getter");
    await assert.rejects(load()({ get match() { throw fault; } }), (seen) => seen === fault);
});
control("match call fault rejects identically before verifier", async () => {
    const fault = Symbol("public match call");
    await assert.rejects(load()({ match() { throw fault; } }), (seen) => seen === fault);
});
control("regexp construction fault rejects identically before match invocation", async () => {
    const fault = Symbol("public regexp construction");
    const binding = new Proxy(function PublicRegExp() { }, { construct() { throw fault; } });
    await assert.rejects(load(fail, fail, binding)({ match: fail }), (seen) => seen === fault);
});
control("optional match capture is read once and no other result property is inspected", async () => {
    const result = new Proxy({}, { get(_target, key) { assert.equal(key, "1"); return "PUBLIC_CAPTURE"; }, set() { assert.fail("write"); }, ownKeys() { assert.fail("enumeration"); } });
    let reads = 0;
    const selected = load((value) => { reads++; assert.equal(value, "PUBLIC_CAPTURE"); return payload; }, () => session);
    assert.equal(await selected({ match() { return result; } }), session);
    assert.equal(reads, 1);
});
control("capture getter fault rejects identically", async () => {
    const fault = Symbol("public capture getter");
    await assert.rejects(load()({ match() { return { get 1() { throw fault; } }; } }), (seen) => seen === fault);
});
control("fresh verifier and account decisions are obtained on every invocation", async () => {
    let verified = true;
    let current = session;
    let verifyCalls = 0;
    let currentCalls = 0;
    const selected = load(() => { verifyCalls++; return verified ? payload : null; }, () => { currentCalls++; return current; });
    assert.equal(await selected(header()), session);
    current = null;
    assert.equal(await selected(header()), null);
    current = session;
    verified = false;
    assert.equal(await selected(header()), null);
    verified = true;
    assert.equal(await selected(header()), session);
    assert.equal(verifyCalls, 4);
    assert.equal(currentCalls, 3);
});
control("simultaneous calls retain their own payload and out of order current results", async () => {
    const first = deferred();
    const second = deferred();
    const a = Object.freeze({ public: "A" });
    const b = Object.freeze({ public: "B" });
    const selected = load(value => value === "PUBLIC_A" ? a : b, seen => seen === a ? first.promise : second.promise);
    const one = selected(header("PUBLIC_A"));
    const two = selected(header("PUBLIC_B"));
    second.resolve(b);
    assert.equal(await two, b);
    first.resolve(a);
    assert.equal(await one, a);
});
control("fresh calls return distinct promises even for a synchronous null branch", async () => {
    const selected = load();
    const first = selected(null);
    const second = selected(null);
    assert.notEqual(first, second);
    assert.deepEqual(await Promise.all([first, second]), [null, null]);
});
control("unused this and extra argument metadata stays opaque", async () => {
    const opaque = new Proxy({}, { get() { assert.fail("unused property access"); } });
    assert.equal(await load(() => payload, () => session).call(opaque, header(), opaque), session);
});
control("nonthenable payload properties remain opaque to the selected declaration", async () => {
    const opaque = new Proxy({}, { get(_target, key) { assert.equal(key, "then"); return undefined; }, ownKeys() { assert.fail("enumeration"); } });
    assert.equal(await load(() => opaque, seen => { assert.equal(seen, opaque); return session; })(header()), session);
});
assert.equal(count, 65);
