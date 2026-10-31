// DISTINCT NEW PUBLIC104 controls; historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
// PUBLIC SOURCE only. Immediate session/account/response bindings are inert facades.
// No original module, import, initializer, neighbour, authentication, ORM or HTTP runs.
const require = createRequire(import.meta.url);
const ts = require('typescript');
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
const raw = readFileSync(fileURLToPath(new URL("../src/lib/permissions.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "c894d04fa4cbcfaa09e97f1248100b671b29927b13950a4e964b0135a994b704");
const ast = ts.createSourceFile("permissions.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n) => ts.isFunctionDeclaration(n) && n.name?.text === "requireAccess");
assert.equal(declarations.length, 1);
const expected = "async function requireAccess(operator: boolean): Promise<\n  Session | NextResponse\n> {\n  const session = await getSession();\n  if (!session) {\n    return NextResponse.json(\n      { error: \"Authentication required\" },\n      { status: 401 }\n    );\n  }\n\n  const user = await prisma.user.findUnique({\n    where: { id: session.id },\n    select: { role: true, engineAdmin: true, sessionVersion: true },\n  });\n\n  if (!user || user.sessionVersion !== session.sessionVersion || user.role !== \"write\" || operator && !user.engineAdmin) {\n    return NextResponse.json(\n      { error: operator ? \"Engine administration required for infrastructure and identity operations\" : \"Write access required\" },\n      { status: 403 }\n    );\n  }\n\n  return session;\n}";
assert.equal(declarations[0].getText(ast), expected);
const javascript = ts.transpileModule(expected, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!/\b(?:import|require)\s*\(/.test(javascript));
function load(sessionBinding, accountBinding, responseBinding) {
    const factory = vm.runInNewContext('(function (getSession, prisma, NextResponse) { "use strict"; return (' + javascript + '); })', {});
    return factory(sessionBinding, accountBinding, responseBinding);
}
const marker = Object.freeze({ id: "PUBLIC", username: "PUBLIC", sessionVersion: 3 });
const fault = Object.freeze({ publicFailure: true });
const writeUser = () => ({ role: "write", engineAdmin: true, sessionVersion: 3 });
const authMessage = "Authentication required";
const writeMessage = "Write access required";
const operatorMessage = "Engine administration required for infrastructure and identity operations";
function model(session, user) {
    const queries = [], responses = [];
    let sessionCalls = 0;
    const account = { findUnique(...args) {
            assert.equal(this, account);
            assert.equal(args.length, 1);
            queries.push(args[0]);
            return user;
        } };
    const response = { json(...args) {
            assert.equal(this, response);
            assert.equal(args.length, 2);
            const output = { body: args[0], options: args[1] };
            responses.push(output);
            return output;
        } };
    const getSession = function (...args) {
        assert.equal(this, undefined);
        assert.equal(args.length, 0);
        sessionCalls++;
        return session;
    };
    return { selected: load(getSession, { user: account }, response), queries, responses, count: () => sessionCalls };
}
function responseIs(actual, status, error) {
    const result = actual;
    // The actual fresh objects originate in the VM realm; compare scalar fields/own keys.
    assert.deepEqual(Object.keys(result), ["body", "options"]);
    assert.deepEqual(Object.keys(result.body), ["error"]);
    assert.equal(result.body.error, error);
    assert.deepEqual(Object.keys(result.options), ["status"]);
    assert.equal(result.options.status, status);
}
async function rejectsSame(promise, expectedFault = fault) {
    let caught = false;
    try {
        await promise;
    }
    catch (actual) {
        caught = true;
        assert.ok(Object.is(actual, expectedFault));
    }
    assert.equal(caught, true);
}
function deferred() {
    let resolve;
    const promise = new Promise(yes => { resolve = yes; });
    return { promise, resolve };
}
control("exact async one-parameter declaration executes alone in a strict inert shell", async () => {
    const m = model(marker, writeUser());
    assert.equal(m.selected.name, "requireAccess");
    assert.equal(m.selected.length, 1);
    assert.equal(declarations[0].parameters.length, 1);
    assert.equal(declarations[0].modifiers.length, 1);
    const result = m.selected(false);
    assert.notEqual(result, marker);
    assert.equal(await result, marker);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 1);
    assert.equal(m.responses.length, 0);
});
control("falsy session undefined refuses401 before account for operator false", async () => {
    const m = model(undefined, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session null refuses401 before account for operator false", async () => {
    const m = model(null, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session false refuses401 before account for operator false", async () => {
    const m = model(false, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session zero refuses401 before account for operator false", async () => {
    const m = model(0, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session negative zero refuses401 before account for operator false", async () => {
    const m = model(-0, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session NaN refuses401 before account for operator false", async () => {
    const m = model(NaN, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session empty string refuses401 before account for operator false", async () => {
    const m = model("", new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session zero bigint refuses401 before account for operator false", async () => {
    const m = model(0n, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(false), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy account undefined refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, undefined);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account null refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, null);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account false refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, false);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account zero refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, 0);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account negative zero refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, -0);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account NaN refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, NaN);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account empty string refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, "");
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account zero bigint refuses403 for operator false", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, 0n);
    responseIs(await m.selected(false), 403, writeMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy session undefined refuses401 before account for operator true", async () => {
    const m = model(undefined, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session null refuses401 before account for operator true", async () => {
    const m = model(null, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session false refuses401 before account for operator true", async () => {
    const m = model(false, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session zero refuses401 before account for operator true", async () => {
    const m = model(0, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session negative zero refuses401 before account for operator true", async () => {
    const m = model(-0, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session NaN refuses401 before account for operator true", async () => {
    const m = model(NaN, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session empty string refuses401 before account for operator true", async () => {
    const m = model("", new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy session zero bigint refuses401 before account for operator true", async () => {
    const m = model(0n, new Proxy({}, { get() { return assert.fail("account read"); } }));
    responseIs(await m.selected(true), 401, authMessage);
    assert.equal(m.count(), 1);
    assert.equal(m.queries.length, 0);
    assert.equal(m.responses.length, 1);
});
control("falsy account undefined refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, undefined);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account null refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, null);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account false refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, false);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account zero refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, 0);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account negative zero refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, -0);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account NaN refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, NaN);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account empty string refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, "");
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("falsy account zero bigint refuses403 for operator true", async () => {
    const session = { id: "PUBLIC", get sessionVersion() { return assert.fail("version read after falsy user"); } };
    const m = model(session, 0n);
    responseIs(await m.selected(true), 403, operatorMessage);
    assert.equal(m.queries.length, 1);
    assert.equal(m.count(), 1);
});
control("strict version relation with inert metadata: same integer", async () => {
    const session = { id: "PUBLIC", sessionVersion: 3 };
    const user = { role: "write", engineAdmin: true, sessionVersion: 3 };
    const m = model(session, user);
    const result = await m.selected(false);
    assert.equal(result, session);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: different integer", async () => {
    const session = { id: "PUBLIC", sessionVersion: 3 };
    const user = { role: "write", engineAdmin: true, sessionVersion: 4 };
    const m = model(session, user);
    const result = await m.selected(false);
    responseIs(result, 403, writeMessage);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: number versus string", async () => {
    const session = { id: "PUBLIC", sessionVersion: 3 };
    const user = { role: "write", engineAdmin: true, sessionVersion: "3" };
    const m = model(session, user);
    const result = await m.selected(false);
    responseIs(result, 403, writeMessage);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: missing versus zero", async () => {
    const session = { id: "PUBLIC", sessionVersion: undefined };
    const user = { role: "write", engineAdmin: true, sessionVersion: 0 };
    const m = model(session, user);
    const result = await m.selected(false);
    responseIs(result, 403, writeMessage);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: same undefined", async () => {
    const session = { id: "PUBLIC", sessionVersion: undefined };
    const user = { role: "write", engineAdmin: true, sessionVersion: undefined };
    const m = model(session, user);
    const result = await m.selected(false);
    assert.equal(result, session);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: NaN versus NaN", async () => {
    const session = { id: "PUBLIC", sessionVersion: NaN };
    const user = { role: "write", engineAdmin: true, sessionVersion: NaN };
    const m = model(session, user);
    const result = await m.selected(false);
    responseIs(result, 403, writeMessage);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: signed zero", async () => {
    const session = { id: "PUBLIC", sessionVersion: -0 };
    const user = { role: "write", engineAdmin: true, sessionVersion: 0 };
    const m = model(session, user);
    const result = await m.selected(false);
    assert.equal(result, session);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("strict version relation with inert metadata: same public string", async () => {
    const session = { id: "PUBLIC", sessionVersion: "PUBLIC" };
    const user = { role: "write", engineAdmin: true, sessionVersion: "PUBLIC" };
    const m = model(session, user);
    const result = await m.selected(false);
    assert.equal(result, session);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("role strict refusal readonly for operator false", async () => {
    const user = { sessionVersion: 3, role: "readonly", get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(false), 403, writeMessage);
});
control("role strict refusal uppercase for operator false", async () => {
    const user = { sessionVersion: 3, role: "WRITE", get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(false), 403, writeMessage);
});
control("role strict refusal empty for operator false", async () => {
    const user = { sessionVersion: 3, role: "", get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(false), 403, writeMessage);
});
control("role strict refusal null for operator false", async () => {
    const user = { sessionVersion: 3, role: null, get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(false), 403, writeMessage);
});
control("role strict refusal undefined for operator false", async () => {
    const user = { sessionVersion: 3, role: undefined, get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(false), 403, writeMessage);
});
control("role strict refusal boxed write for operator false", async () => {
    const user = { sessionVersion: 3, role: new String("write"), get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(false), 403, writeMessage);
});
control("role strict refusal readonly for operator true", async () => {
    const user = { sessionVersion: 3, role: "readonly", get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(true), 403, operatorMessage);
});
control("role strict refusal uppercase for operator true", async () => {
    const user = { sessionVersion: 3, role: "WRITE", get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(true), 403, operatorMessage);
});
control("role strict refusal empty for operator true", async () => {
    const user = { sessionVersion: 3, role: "", get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(true), 403, operatorMessage);
});
control("role strict refusal null for operator true", async () => {
    const user = { sessionVersion: 3, role: null, get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(true), 403, operatorMessage);
});
control("role strict refusal undefined for operator true", async () => {
    const user = { sessionVersion: 3, role: undefined, get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(true), 403, operatorMessage);
});
control("role strict refusal boxed write for operator true", async () => {
    const user = { sessionVersion: 3, role: new String("write"), get engineAdmin() { return assert.fail("admin read after role refusal"); } };
    const m = model(marker, user);
    responseIs(await m.selected(true), 403, operatorMessage);
});
control("admin truthiness true with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: true });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness false with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: false });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness undefined with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: undefined });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness null with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: null });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness zero with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: 0 });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness one with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: 1 });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness empty with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: "" });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness string with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: "PUBLIC" });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness object with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: {} });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness array with operator false", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: [] });
    const result = await m.selected(false);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness true with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: true });
    const result = await m.selected(true);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness false with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: false });
    const result = await m.selected(true);
    responseIs(result, 403, operatorMessage);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness undefined with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: undefined });
    const result = await m.selected(true);
    responseIs(result, 403, operatorMessage);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness null with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: null });
    const result = await m.selected(true);
    responseIs(result, 403, operatorMessage);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness zero with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: 0 });
    const result = await m.selected(true);
    responseIs(result, 403, operatorMessage);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness one with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: 1 });
    const result = await m.selected(true);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness empty with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: "" });
    const result = await m.selected(true);
    responseIs(result, 403, operatorMessage);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness string with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: "PUBLIC" });
    const result = await m.selected(true);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness object with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: {} });
    const result = await m.selected(true);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("admin truthiness array with operator true", async () => {
    const m = model(marker, { role: "write", sessionVersion: 3, engineAdmin: [] });
    const result = await m.selected(true);
    assert.equal(result, marker);
    assert.equal(m.responses.length, 0);
    assert.equal(m.queries.length, 1);
});
control("successful access source member argument await and predicate order", async () => {
    const events = [];
    const session = { get id() { events.push("id"); return "PUBLIC"; }, get sessionVersion() { events.push("sessionVersion"); return 3; } };
    const user = { get sessionVersion() { events.push("userVersion"); return 3; }, get role() { events.push("role"); return "write"; }, get engineAdmin() { events.push("admin"); return true; } };
    const account = { get findUnique() {
            events.push("findUnique");
            return function (query) {
                events.push("findCall");
                assert.equal(this, account);
                assert.deepEqual(Object.keys(query), ["where", "select"]);
                assert.deepEqual(Object.keys(query.where), ["id"]);
                assert.equal(query.where.id, "PUBLIC");
                assert.deepEqual(Object.keys(query.select), ["role", "engineAdmin", "sessionVersion"]);
                for (const v of Object.values(query.select))
                    assert.equal(v, true);
                return user;
            };
        } };
    const prisma = { get user() { events.push("user"); return account; } };
    const selected = load(function (...args) { assert.equal(this, undefined); assert.equal(args.length, 0); events.push("sessionCall"); return session; }, prisma, new Proxy({}, { get() { return assert.fail("response reached"); } }));
    assert.equal(await selected(true), session);
    assert.deepEqual(events, ["sessionCall", "user", "findUnique", "id", "findCall", "userVersion", "sessionVersion", "role", "admin"]);
});
control("method and receiver captured before session id can replace account lookup", async () => {
    const original = { findUnique() { assert.equal(this, original); return writeUser(); } };
    const prisma = { user: original };
    let calls = 0;
    const first = original.findUnique;
    original.findUnique = function () { calls++; return Reflect.apply(first, this, []); };
    const session = { get id() { prisma.user = { findUnique() { return assert.fail("replacement method invoked"); } }; return "PUBLIC"; }, sessionVersion: 3 };
    assert.equal(await load(() => session, prisma, {})(true), session);
    assert.equal(calls, 1);
});
control("operator false never reads admin and successful session is not projected", async () => {
    const session = { id: "PUBLIC", sessionVersion: 3, get username() { return assert.fail("unused username read"); } };
    const user = { role: "write", sessionVersion: 3, get engineAdmin() { return assert.fail("admin read for scoped writer"); }, get password() { return assert.fail("unselected account field read"); } };
    assert.equal(await model(session, user).selected(false), session);
});
control("version mismatch shortcircuits role and administrator metadata", async () => {
    const user = { sessionVersion: 4, get role() { return assert.fail("role reached"); }, get engineAdmin() { return assert.fail("admin reached"); } };
    responseIs(await model(marker, user).selected(true), 403, operatorMessage);
});
control("response member capture precedes fresh literal body and options 401", async () => {
    const calls = [];
    const output = Object.freeze({ publicResponse: true });
    const response = { get json() { return function (...args) { assert.equal(this, response); calls.push(args); return output; }; } };
    const selected = load(() => null, { user: { findUnique() { return null; } } }, response);
    assert.equal(await selected(false), output);
    assert.equal(await selected(false), output);
    assert.equal(calls.length, 2);
    for (const args of calls) {
        assert.equal(args.length, 2);
        const body = args[0], options = args[1];
        assert.deepEqual(Object.keys(body), ["error"]);
        assert.equal(body.error, authMessage);
        assert.deepEqual(Object.keys(options), ["status"]);
        assert.equal(options.status, 401);
    }
    assert.notEqual(calls[0][0], calls[1][0]);
    assert.notEqual(calls[0][1], calls[1][1]);
});
control("response member capture precedes fresh literal body and options 403", async () => {
    const calls = [];
    const output = Object.freeze({ publicResponse: true });
    const response = { get json() { return function (...args) { assert.equal(this, response); calls.push(args); return output; }; } };
    const selected = load(() => marker, { user: { findUnique() { return null; } } }, response);
    assert.equal(await selected(false), output);
    assert.equal(await selected(false), output);
    assert.equal(calls.length, 2);
    for (const args of calls) {
        assert.equal(args.length, 2);
        const body = args[0], options = args[1];
        assert.deepEqual(Object.keys(body), ["error"]);
        assert.equal(body.error, writeMessage);
        assert.deepEqual(Object.keys(options), ["status"]);
        assert.equal(options.status, 403);
    }
    assert.notEqual(calls[0][0], calls[1][0]);
    assert.notEqual(calls[0][1], calls[1][1]);
});
control("pending synthetic session fences account and response until settlement", async () => {
    const session = deferred();
    let reads = 0;
    const selected = load(() => session.promise, { get user() { reads++; return { findUnique: () => writeUser() }; } }, {});
    const result = selected(true);
    assert.equal(reads, 0);
    session.resolve(marker);
    assert.equal(await result, marker);
    assert.equal(reads, 1);
});
control("pending account fences predicate fields until settlement", async () => {
    const account = deferred();
    let versionReads = 0;
    const session = { id: "PUBLIC", get sessionVersion() { versionReads++; return 3; } };
    const result = load(() => session, { user: { findUnique: () => account.promise } }, {})(false);
    await Promise.resolve();
    assert.equal(versionReads, 0);
    account.resolve(writeUser());
    assert.equal(await result, session);
    assert.equal(versionReads, 1);
});
control("async return adopts inert pending response 401", async () => {
    const response = deferred();
    let called = false;
    const selected = load(() => null, { user: { findUnique: () => null } }, { json() { called = true; return response.promise; } });
    const result = selected(false);
    let settled = false;
    void result.then(() => { settled = true; });
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(called, true);
    assert.equal(settled, false);
    response.resolve(marker);
    assert.equal(await result, marker);
});
control("async return adopts inert pending response 403", async () => {
    const response = deferred();
    let called = false;
    const selected = load(() => marker, { user: { findUnique: () => null } }, { json() { called = true; return response.promise; } });
    const result = selected(true);
    let settled = false;
    void result.then(() => { settled = true; });
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(called, true);
    assert.equal(settled, false);
    response.resolve(marker);
    assert.equal(await result, marker);
});
control("immediate fault propagates without catch or retry: session call", async () => {
    await rejectsSame(load(() => { throw fault; }, {}, {})(false));
});
control("immediate fault propagates without catch or retry: session rejection", async () => {
    await rejectsSame(load(() => Promise.reject(fault), {}, {})(false));
});
control("immediate fault propagates without catch or retry: account owner getter", async () => {
    await rejectsSame(load(() => marker, { get user() { throw fault; } }, {})(false));
});
control("immediate fault propagates without catch or retry: lookup getter", async () => {
    await rejectsSame(load(() => marker, { user: { get findUnique() { throw fault; } } }, {})(false));
});
control("immediate fault propagates without catch or retry: session id getter", async () => {
    await rejectsSame(load(() => ({ get id() { throw fault; } }), { user: { findUnique: () => writeUser() } }, {})(false));
});
control("immediate fault propagates without catch or retry: lookup call", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique() { throw fault; } } }, {})(false));
});
control("immediate fault propagates without catch or retry: lookup rejection", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique: () => Promise.reject(fault) } }, {})(false));
});
control("immediate fault propagates without catch or retry: account version getter", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique: () => ({ get sessionVersion() { throw fault; } }) } }, {})(false));
});
control("immediate fault propagates without catch or retry: session version getter", async () => {
    await rejectsSame(load(() => ({ id: "PUBLIC", get sessionVersion() { throw fault; } }), { user: { findUnique: () => writeUser() } }, {})(false));
});
control("immediate fault propagates without catch or retry: role getter", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique: () => ({ sessionVersion: 3, get role() { throw fault; } }) } }, {})(false));
});
control("immediate fault propagates without catch or retry: admin getter", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique: () => ({ sessionVersion: 3, role: "write", get engineAdmin() { throw fault; } }) } }, {})(true));
});
control("immediate fault propagates without catch or retry: unauthenticated json getter", async () => {
    await rejectsSame(load(() => null, {}, { get json() { throw fault; } })(false));
});
control("immediate fault propagates without catch or retry: unauthenticated response call", async () => {
    await rejectsSame(load(() => null, {}, { json() { throw fault; } })(false));
});
control("immediate fault propagates without catch or retry: forbidden json getter", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique: () => null } }, { get json() { throw fault; } })(true));
});
control("immediate fault propagates without catch or retry: forbidden response rejection", async () => {
    await rejectsSame(load(() => marker, { user: { findUnique: () => null } }, { json: () => Promise.reject(fault) })(true));
});
control("fresh independent session and query objects on repeated decisions", async () => {
    let session = marker;
    let user = writeUser();
    const queries = [];
    let calls = 0;
    const selected = load(() => { calls++; return session; }, { user: { findUnique(query) { queries.push(query); return user; } } }, { json: (body, options) => ({ body, options }) });
    assert.equal(await selected(false), marker);
    user = { ...writeUser(), role: "readonly" };
    responseIs(await selected(false), 403, writeMessage);
    user = writeUser();
    assert.equal(await selected(false), marker);
    session = null;
    responseIs(await selected(false), 401, authMessage);
    assert.equal(calls, 4);
    assert.equal(queries.length, 3);
    for (let i = 1; i < queries.length; i++) {
        assert.notEqual(queries[i], queries[0]);
        assert.notEqual(queries[i].where, queries[0].where);
        assert.notEqual(queries[i].select, queries[0].select);
    }
});
control("concurrent synthetic decisions retain their own session account and operator mode", async () => {
    const a = deferred(), b = deferred();
    const sessions = [a.promise, b.promise];
    let index = 0;
    const selected = load(() => sessions[index++], { user: { findUnique(query) { return { ...writeUser(), engineAdmin: query.where.id === "PUBLIC-A" }; } } }, { json: (body, options) => ({ body, options }) });
    const first = selected(true), second = selected(true);
    const sessionA = { ...marker, id: "PUBLIC-A" }, sessionB = { ...marker, id: "PUBLIC-B" };
    b.resolve(sessionB);
    responseIs(await second, 403, operatorMessage);
    a.resolve(sessionA);
    assert.equal(await first, sessionA);
    assert.equal(index, 2);
});
control("caller receiver and extra arguments never reach detached session facade", async () => {
    const poison = new Proxy({}, { get() { return assert.fail("caller metadata read"); } });
    const m = model(marker, writeUser());
    assert.equal(await Reflect.apply(m.selected, poison, [false, poison]), marker);
    assert.equal(m.count(), 1);
});
control("awaited account thenable assimilates once before predicate reads", async () => {
    let thenCalls = 0;
    const thenable = { then(resolve) { thenCalls++; resolve(writeUser()); } };
    assert.equal(await model(marker, thenable).selected(true), marker);
    assert.equal(thenCalls, 1);
});
control("thenable response rejection is adopted by async function", async () => {
    const response = { then(_resolve, reject) { reject(fault); } };
    await rejectsSame(load(() => null, {}, { json: () => response })(false));
});
control("response method lookup fault occurs before any response call", async () => {
    let calls = 0;
    const response = { get json() { calls++; throw fault; } };
    await rejectsSame(load(() => null, {}, response)(true));
    assert.equal(calls, 1);
});
assert.equal(count, 104);
