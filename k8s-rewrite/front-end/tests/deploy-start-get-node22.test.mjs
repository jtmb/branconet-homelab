import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct supported PUBLIC selected-declaration controls; historical28 remain frozen.
// Real module/imports/initializers/auth/capabilities/DB/jobs/provisioning/timers stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/app/api/deploy/start/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), 'f52fd8b6959c3e7fcf0eaaea9cf4b00877822cd0e1f9799337bf71b3b5e70418');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '9e7afd9407f4d591eddce8cb6624f3c53477f1ba37572984a775e93d4fd7d353');
const parsed = ts.createSourceFile('selected.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(parsed.parseDiagnostics.length, 0);
const declarations = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'GET');
assert.equal(declarations.length, 1);
const selected = declarations[0];
assert.equal(selected.parameters.length, 0);
assert.deepEqual(selected.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
const declaration = selected.getText(parsed);
assert.equal(declaration, "export async function GET() {\n  // Return list of active job IDs (for health check / status polling)\n  return NextResponse.json({\n    activeJobIds: Array.from(activeJobs.keys()),\n  });\n}");
assert.equal(digest(declaration), '8065440a9bd3887977d7cea87925912f6c2303e1d1f4fe01630da07b47612798');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), 'bf62a3bd06e92478361fbf917b7d0503bb5f4d43ca6ec30ec87b4c71797aa79f');
const compiled = ts.transpileModule(declaration.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const emitted = compiled.outputText;
assert.ok(!emitted.includes('import(') && !emitted.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
function harness(settings = {}) {
    const trace = [];
    const fault = Error("PUBLIC-SOURCE-FAULT");
    const ids = settings.ids ?? ["PUBLIC-JOB-2", "PUBLIC-JOB-1"];
    const result = settings.result ?? Object.freeze({ public: "RESPONSE" });
    let body;
    let argumentsCount = 0;
    let index = 0;
    let jsonReceiver;
    let keysReceiver;
    let fromReceiver;
    function mark(name) { trace.push(name); if (settings.fault === name)
        throw fault; }
    const iterator = {
        get [Symbol.iterator]() {
            mark("iterator:get");
            return function () { mark("iterator:call"); return iterator; };
        },
        get next() {
            mark("next:get");
            return function () {
                mark("next:" + index);
                return index < ids.length ? { done: false, value: ids[index++] } : { done: true };
            };
        },
    };
    const activeJobs = {
        get keys() {
            mark("keys:get");
            return function () { keysReceiver = this; mark("keys:call"); return settings.keysResult ?? iterator; };
        },
        get values() { throw Error("ACTUAL JOB VALUES MUST REMAIN INERT"); },
        get entries() { throw Error("ACTUAL JOB ENTRIES MUST REMAIN INERT"); },
    };
    const arrayBinding = {
        get from() {
            mark("from:get");
            return function (items) {
                fromReceiver = this;
                mark("from:call");
                return Array.from(items);
            };
        },
    };
    const responseBinding = {
        get json() {
            mark("json:get");
            return function (value) {
                jsonReceiver = this;
                argumentsCount = arguments.length;
                mark("json:call");
                body = value;
                return result;
            };
        },
    };
    const bindings = {
        NextResponse: responseBinding, activeJobs, Array: arrayBinding,
        get requireOperator() { throw Error("ACTUAL AUTHORIZATION MUST REMAIN INERT"); },
        get runtimeCapabilities() { throw Error("ACTUAL CAPABILITIES MUST REMAIN INERT"); },
        get prisma() { throw Error("ACTUAL DATABASE MUST REMAIN INERT"); },
        get runAnsiblePlaybook() { throw Error("ACTUAL PROVISIONING MUST REMAIN INERT"); },
        get setTimeout() { throw Error("ACTUAL TIMERS MUST REMAIN INERT"); },
    };
    const GET = new vm.Script(emitted + "\nGET", { filename: "selected-deploy-start-GET.js" })
        .runInNewContext(bindings, { timeout: 1000, contextCodeGeneration: { strings: false, wasm: false } });
    return { GET, trace, ids, fault, result, activeJobs, arrayBinding, responseBinding,
        body: () => body, argumentsCount: () => argumentsCount,
        receivers: () => [jsonReceiver, keysReceiver, fromReceiver] };
}
const prefix = ["json:get", "from:get", "keys:get", "keys:call", "from:call", "iterator:get", "iterator:call", "next:get"];
const expected = (count) => [...prefix, ...Array.from({ length: count + 1 }, (_, i) => "next:" + i), "json:call"];
control("exact GET selection is exported async zero-argument declaration only", () => {
    assert.match(declaration, /^export async function GET\(\) \{/);
    assert.equal(declaration.includes("async function runAnsible"), false);
    assert.equal(declaration.includes("requireOperator"), false);
    assert.equal(declaration.includes("runtimeCapabilities"), false);
});
control("creating the exact declaration executes no body or imported initializer", () => {
    const h = harness();
    assert.deepEqual(h.trace, []);
});
control("successful source-derived member/call/iteration order is exact", async () => {
    const h = harness();
    assert.equal(await h.GET(), h.result);
    assert.deepEqual(h.trace, expected(2));
});
control("json, keys and from receive their original member receivers", async () => {
    const h = harness();
    await h.GET();
    assert.deepEqual(h.receivers(), [h.responseBinding, h.activeJobs, h.arrayBinding]);
});
control("json gets exactly one argument and only activeJobIds metadata", async () => {
    const h = harness();
    await h.GET();
    assert.equal(h.argumentsCount(), 1);
    assert.deepEqual(Object.keys(h.body()), ["activeJobIds"]);
    assert.deepEqual(h.body().activeJobIds, h.ids);
});
for (const [name, ids] of [
    ["empty", []], ["one", ["PUBLIC-1"]], ["insertion order", ["PUBLIC-9", "PUBLIC-2", "PUBLIC-7"]],
    ["Unicode", ["PUBLIC-\u03b1", "PUBLIC-\ud83d\ude80"]],
    ["special metadata names", ["__proto__", "constructor", "toString"]],
]) {
    control("finite PUBLIC IDs preserve " + name, async () => {
        const h = harness({ ids });
        await h.GET();
        assert.deepEqual(h.body().activeJobIds, ids);
        assert.deepEqual(h.trace, expected(ids.length));
    });
}
control("each invocation obtains a fresh metadata snapshot", async () => {
    const h = harness({ ids: [] });
    await h.GET();
    const first = h.body().activeJobIds;
    h.ids.push("PUBLIC-NEXT");
    h.trace.length = 0;
    await h.GET();
    assert.deepEqual(first, []);
    assert.deepEqual(h.body().activeJobIds, ["PUBLIC-NEXT"]);
    assert.notEqual(first, h.body().activeJobIds);
    assert.deepEqual(h.trace, expected(1));
});
control("all synchronous body work precedes the returned Promise settlement", async () => {
    const h = harness();
    const pending = h.GET();
    assert.deepEqual(h.trace, expected(2));
    assert.equal(typeof pending.then, "function");
    assert.equal(await pending, h.result);
});
control("a synthetic response thenable is adopted by the async return", async () => {
    const token = Object.freeze({ public: "THENABLE-RESULT" });
    const h = harness({ result: { then: (done) => done(token) } });
    assert.equal(await h.GET(), token);
    assert.deepEqual(h.trace, expected(2));
});
control("an inert finite Map exposes keys without inspecting job values", async () => {
    const values = new Map([["PUBLIC-B", Object.freeze({})], ["PUBLIC-A", Object.freeze({})]]);
    const h = harness({ keysResult: values.keys() });
    await h.GET();
    assert.deepEqual(h.body().activeJobIds, ["PUBLIC-B", "PUBLIC-A"]);
    assert.deepEqual(h.trace, ["json:get", "from:get", "keys:get", "keys:call", "from:call", "json:call"]);
});
for (const point of [...prefix, "next:0", "next:1", "next:2", "json:call"]) {
    control("exact PUBLIC fault at " + point + " rejects without later calls", async () => {
        const h = harness({ fault: point });
        const all = expected(2);
        await assert.rejects(h.GET(), e => e === h.fault);
        assert.deepEqual(h.trace, all.slice(0, all.indexOf(point) + 1));
        assert.equal(h.body(), undefined);
    });
}
control("synthetic response rejection is preserved without a second json call", async () => {
    const fault = Error("PUBLIC-RESPONSE-REJECTION");
    const h = harness({ result: { then: (_done, reject) => reject(fault) } });
    await assert.rejects(h.GET(), e => e === fault);
    assert.deepEqual(h.trace, expected(2));
});
control("authorization/capability/database/provisioning/timer bindings stay unread", async () => {
    const h = harness();
    await h.GET();
    assert.deepEqual(h.trace, expected(2));
    // This is an exact-declaration boundary check, not real authorization qualification.
});
assert.equal(count, 28);
