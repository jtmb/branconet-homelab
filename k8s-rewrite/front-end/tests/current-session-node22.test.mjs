import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct supported PUBLIC selected-declaration controls; historical57 remain frozen.
// Actual module/imports/initializers/JWT/cookies/auth/readers/PrismaSQLORM/native/HTTP inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/lib/auth.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), '932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff');
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'f190c4ba27ee2069a799ed9aa5cd37e6a69ebba70bcd05f927c3ad8eeecdc7d8');
const ast = ts.createSourceFile('selected-auth.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'currentSession');
assert.equal(declarations.length, 1);
assert.deepEqual(declarations[0].modifiers.map(node => node.kind), [ts.SyntaxKind.AsyncKeyword]);
const declaration = declarations[0].getText(ast);
const expectedDeclaration = "async function currentSession(payload: NonNullable<Awaited<ReturnType<typeof verifyJWT>>>): Promise<Session | null> {\n  const user = await directAccountReader.readSession(payload.sub);\n  if (!user || user.sessionVersion !== payload.sessionVersion) return null;\n  return { id: user.id, username: user.username, sessionVersion: user.sessionVersion };\n}";
assert.equal(declaration, expectedDeclaration);
assert.equal(digest(declaration), '8e96b84b6ffffe1cb5fbd5b9b4a4ace86568ca0d5586b3da274d751798095032');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '2df2065380fe62fe1ba9e32316fee04b00b25548e82129d97954dda7dbf8e91e');
const emitted = ts.transpileModule(declaration, { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
assert.equal(emitted.diagnostics.length, 0);
const javascript = emitted.outputText;
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const forbiddenCalls = [];
const forbidden = () => { forbiddenCalls.push("unexpected injected reader"); throw new Error("unexpected injected reader"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(...readers) {
    const reader = readers.length ? readers[0] : { readSession: forbidden };
    return vm.runInNewContext("(" + javascript + ")", { directAccountReader: reader });
}
const payload = (version = 7) => ({ sub: "PUBLIC_SUBJECT", username: "UNUSED_PAYLOAD_NAME", sessionVersion: version });
const user = (version = 7) => ({ id: "PUBLIC_ID", username: "PUBLIC_CURRENT_NAME", sessionVersion: version });
function projected(actual, expected) {
    assert.ok(actual && typeof actual === "object");
    const value = actual;
    assert.deepEqual(Object.keys(value), ["id", "username", "sessionVersion"]);
    assert.equal(value.id, expected.id);
    assert.equal(value.username, expected.username);
    assert.equal(value.sessionVersion, expected.sessionVersion);
}
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
const falsy = [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]];
control("pinned one-parameter async declaration and fresh projection", async () => {
    const selected = load({ readSession: () => user() });
    assert.equal(selected.name, "currentSession");
    assert.equal(selected.length, 1);
    assert.equal(declarations[0].parameters.length, 1);
    assert.equal(declarations[0].body.statements.length, 3);
    const first = await selected(payload());
    const second = await selected(payload(), "PUBLIC_UNUSED");
    projected(first, user());
    projected(second, user());
    assert.notEqual(first, second);
});
control("member before subject; exact reader receiver/argument; version comparison before ordered projection", async () => {
    const events = [];
    const identity = { publicSubject: "UNCOERCED" };
    const p = { get sub() { events.push("sub"); return identity; }, get sessionVersion() { events.push("payload-version"); return 7; }, get username() { forbiddenCalls.push("payload-name"); throw new Error("unused"); } };
    const u = { get sessionVersion() { events.push("user-version"); return 7; }, get id() { events.push("id"); return "PUBLIC_ID"; }, get username() { events.push("name"); return "PUBLIC_CURRENT_NAME"; } };
    const reader = { get readSession() { events.push("member"); return function (...args) { assert.equal(this, reader); assert.equal(args.length, 1); assert.equal(args[0], identity); events.push("call"); return u; }; } };
    const result = await load(reader)(p);
    projected(result, user());
    assert.notEqual(result, u);
    assert.deepEqual(events, ["member", "sub", "call", "user-version", "payload-version", "id", "name", "user-version"]);
});
for (const [name, value] of falsy)
    control("falsy awaited account short-circuits all version/projection reads: " + name, async () => {
        const p = { sub: "PUBLIC_SUBJECT", get sessionVersion() { forbiddenCalls.push("version-after-falsy"); throw new Error("unused"); } };
        assert.equal(await load({ readSession: () => value })(p), null);
    });
for (const [name, value] of [["string", "7"], ["other", 8], ["missing", undefined], ["null", null], ["boolean", true], ["bigint", 7n], ["NaN", NaN], ["object", {}]])
    control("strict unequal version refuses before projection: " + name, async () => {
        const u = { sessionVersion: value, get id() { forbiddenCalls.push("id-after-mismatch"); throw new Error("unused"); }, get username() { forbiddenCalls.push("name-after-mismatch"); throw new Error("unused"); } };
        assert.equal(await load({ readSession: () => u })(payload()), null);
    });
for (const [name, version] of [["number", 7], ["zero", 0], ["string metadata", "PUBLIC_VERSION"], ["undefined metadata", undefined], ["null metadata", null], ["boolean metadata", false], ["bigint metadata", 3n], ["object identity metadata", {}]])
    control("equal inert version metadata uses strict equality without extra validation: " + name, async () => {
        const p = { sub: "PUBLIC_SUBJECT", sessionVersion: version };
        const u = { id: "PUBLIC_ID", username: "PUBLIC_CURRENT_NAME", sessionVersion: version };
        projected(await load({ readSession: () => u })(p), u);
    });
control("positive and negative zero versions compare equal; returned value comes from current account", async () => {
    const result = await load({ readSession: () => user(-0) })(payload(0));
    projected(result, user(-0));
    assert.ok(Object.is(result.sessionVersion, -0));
});
control("two NaN metadata versions refuse under strict inequality", async () => { assert.equal(await load({ readSession: () => user(NaN) })(payload(NaN)), null); });
for (const [name, subject] of [["undefined", undefined], ["null", null], ["empty", ""], ["number", 3], ["object", {}]])
    control("subject metadata forwarded unchanged without coercion: " + name, async () => {
        let calls = 0;
        const selected = load({ readSession: (...args) => { calls++; assert.equal(args.length, 1); assert.equal(args[0], subject); return user(); } });
        projected(await selected({ sub: subject, sessionVersion: 7 }), user());
        assert.equal(calls, 1);
    });
for (const [name, reader] of [["null", null], ["undefined", undefined], ["missing member", {}], ["noncallable", { readSession: 1 }]])
    control("invalid inert reader rejects: " + name, async () => { await assert.rejects(load(reader)(payload()), { name: "TypeError" }); });
for (const [name, p] of [["null", null], ["undefined", undefined]])
    control("invalid payload rejects before reader call: " + name, async () => { await assert.rejects(load()(p), { name: "TypeError" }); });
control("reader-member fault precedes payload access and propagates exact fault", async () => {
    const fault = Object.freeze({ publicFault: "MEMBER" });
    const selected = load({ get readSession() { throw fault; } });
    const p = { get sub() { forbiddenCalls.push("sub-after-member-fault"); throw new Error("unused"); } };
    await assert.rejects(selected(p), (e) => e === fault);
});
control("subject getter fault propagates without calling captured member", async () => {
    const fault = Object.freeze({ publicFault: "SUBJECT" });
    await assert.rejects(load({ readSession: forbidden })({ get sub() { throw fault; } }), (e) => e === fault);
});
for (const asynchronous of [false, true])
    control("reader fault propagates exact identity, async=" + asynchronous, async () => {
        const fault = Object.freeze({ publicFault: "READ" });
        await assert.rejects(load({ readSession: () => { if (asynchronous)
                return Promise.reject(fault); throw fault; } })(payload()), (e) => e === fault);
    });
for (const position of ["user-version-first", "payload-version", "id", "username", "user-version-second"])
    control("ordered metadata getter fault propagates and stops later reads: " + position, async () => {
        const events = [];
        const fault = Object.freeze({ publicFault: position });
        let versions = 0;
        const read = (name, value) => { events.push(name); if (name === position)
            throw fault; return value; };
        const u = { get sessionVersion() { return read(++versions === 1 ? "user-version-first" : "user-version-second", 7); }, get id() { return read("id", "PUBLIC_ID"); }, get username() { return read("username", "PUBLIC_CURRENT_NAME"); } };
        const p = { sub: "PUBLIC_SUBJECT", get sessionVersion() { return read("payload-version", 7); } };
        await assert.rejects(load({ readSession: () => u })(p), (e) => e === fault);
        const expected = ["user-version-first", "payload-version", "id", "username", "user-version-second"];
        assert.deepEqual(events, expected.slice(0, expected.indexOf(position) + 1));
    });
control("await fence prevents version/projection reads until read fulfills", async () => {
    const gate = deferred();
    const events = [];
    let settled = false;
    const pending = load({ readSession: () => { events.push("read"); return gate.promise; } })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { events.push("version"); return 7; } });
    void pending.then(() => { settled = true; });
    await Promise.resolve();
    assert.deepEqual(events, ["read"]);
    assert.equal(settled, false);
    gate.resolve(user());
    projected(await pending, user());
    assert.deepEqual(events, ["read", "version"]);
});
control("pending read rejection skips version access and retains rejection identity", async () => {
    const gate = deferred();
    const fault = Object.freeze({ publicFault: "PENDING" });
    const pending = load({ readSession: () => gate.promise })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { forbiddenCalls.push("version-after-rejection"); throw new Error("unused"); } });
    const rejected = assert.rejects(pending, (e) => e === fault);
    gate.reject(fault);
    await rejected;
});
control("custom read thenable is assimilated once before metadata decision", async () => {
    let calls = 0;
    const account = user();
    const thenable = { then(resolve) { calls++; resolve(account); } };
    projected(await load({ readSession: () => thenable })(payload()), account);
    assert.equal(calls, 1);
});
control("awaited read then-getter fault propagates", async () => {
    const fault = Object.freeze({ publicFault: "THEN" });
    await assert.rejects(load({ readSession: () => ({ get then() { throw fault; } }) })(payload()), (e) => e === fault);
});
control("projection rereads version and uses current account fields rather than payload username", async () => {
    let reads = 0;
    const u = { id: "PUBLIC_NEW_ID", username: "PUBLIC_NEW_NAME", get sessionVersion() { return ++reads === 1 ? 7 : 9; } };
    projected(await load({ readSession: () => u })(payload()), { id: "PUBLIC_NEW_ID", username: "PUBLIC_NEW_NAME", sessionVersion: 9 });
    assert.equal(reads, 2);
});
control("projection values are copied unchanged and unrelated fields are not read", async () => {
    const id = Object.freeze({ publicField: "ID" });
    const username = Object.freeze({ publicField: "NAME" });
    const u = { id, username, sessionVersion: 7, get role() { forbiddenCalls.push("role"); throw new Error("unused"); }, get passwordHash() { forbiddenCalls.push("password"); throw new Error("unused"); }, get then() { return undefined; } };
    projected(await load({ readSession: () => u })(payload()), u);
});
control("same selected function makes fresh allow/refuse/allow decisions with no user cache", async () => {
    const values = [user(), null, user(8)];
    let calls = 0;
    const selected = load({ readSession: () => values[calls++] });
    projected(await selected(payload()), user());
    assert.equal(await selected(payload()), null);
    projected(await selected(payload(8)), user(8));
    assert.equal(calls, 3);
});
control("concurrent calls keep their own payloads and out-of-order account results", async () => {
    const a = deferred();
    const b = deferred();
    const subjects = [];
    const selected = load({ readSession: (sub) => { subjects.push(sub); return sub === "PUBLIC_A" ? a.promise : b.promise; } });
    const pa = selected({ sub: "PUBLIC_A", sessionVersion: 7 });
    const pb = selected({ sub: "PUBLIC_B", sessionVersion: 8 });
    b.resolve(user(7));
    assert.equal(await pb, null);
    a.resolve(user(7));
    projected(await pa, user(7));
    assert.deepEqual(subjects, ["PUBLIC_A", "PUBLIC_B"]);
});
control("captured read member is retained even if subject getter replaces reader member", async () => {
    const reader = { readSession: () => user() };
    const p = { get sub() { reader.readSession = forbidden; return "PUBLIC_SUBJECT"; }, sessionVersion: 7 };
    projected(await load(reader)(p), user());
});
assert.equal(count, 57);
