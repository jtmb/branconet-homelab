import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

// Distinct supported PUBLIC selected-declaration controls; historical61 remain frozen.
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
const declarations = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'POST');
assert.equal(declarations.length, 1);
const selected = declarations[0];
assert.equal(selected.parameters.length, 1);
assert.equal(selected.parameters[0].getText(parsed), 'request: NextRequest');
assert.deepEqual(selected.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
const declaration = selected.getText(parsed);
assert.equal(declaration, "export async function POST(request: NextRequest) {\n  const auth = await requireOperator();\n  if (auth instanceof NextResponse) return auth;\n\n  if (!runtimeCapabilities().provisioning) return NextResponse.json({ error: \"Run bootstrap/provisioning from the independent operator environment\" }, { status: 501 });\n\n  try {\n    const body = await request.json();\n    const selected = ansibleSelection(body?.playbook ?? \"site.yml\", body?.roles ?? []);\n    const playbookFile = selected.playbook;\n\n    // Fail before launching on invalid lookup references; never use old generated files.\n    await syncVarsToYAML();\n    await syncNodesFromVars();\n    await syncInventoryToFile();\n\n    // Create job record in SQLite via Prisma\n    const job = await prisma.job.create({\n      data: {\n        playbook: playbookFile,\n        status: \"running\",\n        output: PREPARATION_OUTPUT,\n        startedAt: new Date(),\n      },\n    });\n\n    // Create AbortController for cancellation\n    const controller = new AbortController();\n    activeJobs.set(job.id, controller);\n\n    // Start Ansible asynchronously (don't await)\n    void runAnsible(job.id, playbookFile, selected.roles, controller.signal);\n\n    return NextResponse.json({ success: true, jobId: job.id });\n  } catch (err) {\n    if (err instanceof AnsibleSelectionError) return NextResponse.json({ error: err.message }, { status: 400 });\n    return NextResponse.json({ error: \"Provisioning preparation failed\" }, { status: 500 });\n  }\n}");
assert.equal(digest(declaration), '1466c279086ecd1fd9140f9d1e130acaf4284b7382b89d69cab65077fa032e39');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), 'bd9a6cff3badf64bd530bebf026a31d92678dd78aa1a2a9fa5cbebc524a2b706');
assert.equal(digest(declaration + '\n'), '3fa5ec7d8f8adf01c163d0df6dd534ab1fe845e433dc8b71c6ce90ca6f7ed9d4');
const compiled = ts.transpileModule(declaration.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const javascript = compiled.outputText;
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const names = ["requireOperator", "NextResponse", "runtimeCapabilities", "ansibleSelection", "syncVarsToYAML", "syncNodesFromVars", "syncInventoryToFile", "prisma", "PREPARATION_OUTPUT", "Date", "AbortController", "activeJobs", "runAnsible", "AnsibleSelectionError"];
const factory = new Function(...names, javascript + "\nreturn POST;");
class PublicSelectionError extends Error {
}
function setup(settings = {}) {
    const trace = [];
    const calls = [];
    const counts = new Map();
    const failure = Object.hasOwn(settings, "failure") ? settings.failure : new Error("PUBLIC synthetic failure");
    function hit(label) {
        trace.push(label);
        const count = (counts.get(label) ?? 0) + 1;
        counts.set(label, count);
        if (settings.fault === label && count === (settings.occurrence ?? 1))
            throw failure;
    }
    function call(label, receiver, args, fallback) {
        hit(label);
        calls.push({ label, receiver, args });
        return settings.returns && Object.hasOwn(settings.returns, label) ? settings.returns[label] : fallback;
    }
    class SyntheticResponse {
        static [Symbol.hasInstance](value) {
            hit("auth.instanceof");
            return typeof value === "object" && value !== null && Object.getPrototypeOf(value) === SyntheticResponse.prototype;
        }
        static get json() {
            hit("response.member");
            return function (...args) {
                call("response.call", this, args, undefined);
                const result = { body: args[0], options: args[1], args };
                return settings.responseResult ? settings.responseResult(result) : result;
            };
        }
    }
    const selectionError = new Proxy(PublicSelectionError, {
        get(target, key, receiver) {
            if (key === Symbol.hasInstance)
                return (value) => {
                    hit("selectionError.instanceof");
                    return typeof value === "object" && value !== null && Object.getPrototypeOf(value) === PublicSelectionError.prototype;
                };
            return Reflect.get(target, key, receiver);
        },
    });
    const selected = {
        get playbook() { hit("selected.playbook"); return "public-selected.yml"; },
        get roles() { hit("selected.roles"); return ["PUBLIC-role"]; },
    };
    const job = { get id() { hit("job.id"); return "PUBLIC-job-id"; } };
    const jobReceiver = {
        get create() {
            hit("prisma.create.member");
            return function (...args) { return call("prisma.create.call", this, args, job); };
        },
    };
    const prisma = { get job() { hit("prisma.job"); return jobReceiver; } };
    let controller;
    class SyntheticController {
        constructor(...args) { call("controller.construct", undefined, args, undefined); controller = this; }
        get signal() { hit("controller.signal"); return "PUBLIC-signal"; }
    }
    const registrations = [];
    const activeJobs = {
        get set() {
            hit("activeJobs.set.member");
            return function (...args) {
                call("activeJobs.set.call", this, args, undefined);
                registrations.push(args);
            };
        },
    };
    const request = {
        get json() {
            hit("request.json.member");
            return function (...args) {
                return call("request.json.call", this, args, Object.hasOwn(settings, "body") ? settings.body : {});
            };
        },
    };
    const auth = Object.hasOwn(settings, "auth") ? settings.auth : { id: "PUBLIC-operator" };
    const capabilities = { get provisioning() { hit("capability.provisioning"); return Object.hasOwn(settings, "capability") ? settings.capability : true; } };
    const values = [
        function (...args) { return call("auth.call", this, args, auth); },
        SyntheticResponse,
        function (...args) { return call("capability.call", this, args, capabilities); },
        function (...args) { return call("selection.call", this, args, Object.hasOwn(settings, "selectResult") ? settings.selectResult : selected); },
        function (...args) { return call("vars.call", this, args, undefined); },
        function (...args) { return call("nodes.call", this, args, undefined); },
        function (...args) { return call("inventory.call", this, args, undefined); },
        prisma, "PUBLIC preparation metadata",
        class SyntheticDate {
            constructor(...args) { call("date.construct", undefined, args, undefined); }
        },
        SyntheticController, activeJobs,
        function (...args) { return call("runner.call", this, args, undefined); },
        selectionError,
    ];
    const handler = factory(...values);
    const invoke = () => handler(request);
    return { trace, calls, counts, failure, request, selected, job, jobReceiver, activeJobs, registrations, invoke, Response: SyntheticResponse, controller: () => controller };
}
function response(value) {
    assert.ok(typeof value === "object" && value !== null && "body" in value && "args" in value);
    return value;
}
function callAt(h, label) {
    const found = h.calls.find(x => x.label === label);
    assert.ok(found, label);
    return found;
}
const successOrder = ["auth.call", "auth.instanceof", "capability.call", "capability.provisioning", "request.json.member", "request.json.call", "selection.call", "selected.playbook", "vars.call", "nodes.call", "inventory.call", "prisma.job", "prisma.create.member", "date.construct", "prisma.create.call", "controller.construct", "activeJobs.set.member", "job.id", "activeJobs.set.call", "job.id", "selected.roles", "controller.signal", "runner.call", "response.member", "job.id", "response.call"];
control("exact POST source selection excludes imports, GET and neighbours", () => {
    assert.match(declaration, /^export async function POST\(request: NextRequest\)/);
    assert.doesNotMatch(declaration, /\bimport\s|export async function GET/);
    assert.equal(names.length, 14);
});
control("success observes exact source order, receivers and metadata arguments", async () => {
    const h = setup();
    const result = response(await h.invoke());
    assert.deepEqual(h.trace, successOrder);
    assert.deepEqual(result.body, { success: true, jobId: "PUBLIC-job-id" });
    assert.equal(result.args.length, 1);
    assert.equal(callAt(h, "request.json.call").receiver, h.request);
    assert.equal(callAt(h, "prisma.create.call").receiver, h.jobReceiver);
    assert.equal(callAt(h, "activeJobs.set.call").receiver, h.activeJobs);
    for (const label of ["auth.call", "capability.call", "request.json.call", "vars.call", "nodes.call", "inventory.call", "date.construct", "controller.construct"])
        assert.deepEqual(callAt(h, label).args, []);
    assert.deepEqual(callAt(h, "selection.call").args, ["site.yml", []]);
    const data = callAt(h, "prisma.create.call").args[0].data;
    assert.deepEqual(Object.keys(data), ["playbook", "status", "output", "startedAt"]);
    assert.equal(data.playbook, "public-selected.yml");
    assert.equal(data.status, "running");
    assert.equal(data.output, "PUBLIC preparation metadata");
    assert.deepEqual(h.registrations, [["PUBLIC-job-id", h.controller()]]);
    assert.deepEqual(callAt(h, "runner.call").args, ["PUBLIC-job-id", "public-selected.yml", ["PUBLIC-role"], "PUBLIC-signal"]);
});
control("auth denial returns exact identity before capability or request", async () => {
    const first = setup();
    const denial = new first.Response();
    // The handler must use the same synthetic response constructor as its denial.
    const h = setup({ returns: { "auth.call": denial } });
    h.Response[Symbol.hasInstance] = value => value === denial;
    assert.equal(await h.invoke(), denial);
    assert.deepEqual(h.trace, ["auth.call"]);
});
for (const label of ["auth.call", "auth.instanceof", "capability.call", "capability.provisioning"]) {
    control("outside try fault propagates unchanged: " + label, async () => {
        const h = setup({ fault: label });
        await assert.rejects(h.invoke(), x => x === h.failure);
        assert.equal(h.counts.has("request.json.member"), false);
        assert.equal(h.counts.has("selectionError.instanceof"), false);
    });
}
control("outside try asynchronous authorization rejection propagates unchanged", async () => {
    const failure = new Error("PUBLIC authorization rejection");
    const h = setup({ returns: { "auth.call": { then(_resolve, reject) { reject(failure); } } } });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.deepEqual(h.trace, ["auth.call"]);
});
for (const capability of [false, 0, null, undefined, ""]) {
    control("disabled capability refuses before request: " + String(capability), async () => {
        const h = setup({ capability });
        const r = response(await h.invoke());
        assert.deepEqual(h.trace, ["auth.call", "auth.instanceof", "capability.call", "capability.provisioning", "response.member", "response.call"]);
        assert.deepEqual(r.options, { status: 501 });
        assert.deepEqual(r.body, { error: "Run bootstrap/provisioning from the independent operator environment" });
    });
}
for (const capability of [true, 1, "PUBLIC-enabled", {}]) {
    control("capability source truthiness proceeds: " + String(capability), async () => {
        const h = setup({ capability });
        assert.deepEqual(response(await h.invoke()).body, { success: true, jobId: "PUBLIC-job-id" });
    });
}
for (const body of [undefined, null, {}]) {
    control("nullish request fields default without fabricated selection: " + String(body), async () => {
        const h = setup({ body });
        await h.invoke();
        assert.deepEqual(callAt(h, "selection.call").args, ["site.yml", []]);
    });
}
control("nonnull falsy selection fields preserve identity and source getter order", async () => {
    const observed = [];
    const body = { get playbook() { observed.push("playbook"); return 0; }, get roles() { observed.push("roles"); return false; } };
    const h = setup({ body });
    await h.invoke();
    assert.deepEqual(observed, ["playbook", "roles"]);
    assert.deepEqual(callAt(h, "selection.call").args, [0, false]);
});
control("default roles array is fresh for each invocation", async () => {
    const h = setup();
    await h.invoke();
    await h.invoke();
    const selections = h.calls.filter(x => x.label === "selection.call");
    assert.notEqual(selections[0].args[1], selections[1].args[1]);
});
for (const field of ["playbook", "roles"]) {
    control("body field fault prevents selection and preparation: " + field, async () => {
        const body = Object.defineProperty({}, field, { get() { throw new Error("PUBLIC field failure"); } });
        const h = setup({ body });
        assert.deepEqual(response(await h.invoke()).options, { status: 500 });
        assert.equal(h.counts.has("selection.call"), false);
        assert.equal(h.counts.has("vars.call"), false);
    });
}
const caughtFaults = ["request.json.member", "request.json.call", "selection.call", "selected.playbook", "vars.call", "nodes.call", "inventory.call", "prisma.job", "prisma.create.member", "date.construct", "prisma.create.call", "controller.construct", "activeJobs.set.member", "job.id", "activeJobs.set.call", "selected.roles", "controller.signal", "runner.call", "response.member", "response.call"];
for (const label of caughtFaults) {
    control("caught synchronous fault is fixed500 and stops later phases: " + label, async () => {
        const h = setup({ fault: label });
        const r = response(await h.invoke());
        assert.deepEqual(r.body, { error: "Provisioning preparation failed" });
        assert.deepEqual(r.options, { status: 500 });
        const at = successOrder.indexOf(label);
        const next = h.trace.indexOf("selectionError.instanceof");
        assert.deepEqual(h.trace.slice(0, next), successOrder.slice(0, at + 1));
        assert.deepEqual(h.trace.slice(next), ["selectionError.instanceof", "response.member", "response.call"]);
    });
}
for (const label of ["request.json.call", "vars.call", "nodes.call", "inventory.call", "prisma.create.call"]) {
    control("awaited synthetic rejection becomes fixed500: " + label, async () => {
        const failure = new Error("PUBLIC rejected immediate binding");
        const h = setup({ returns: { [label]: { then(_resolve, reject) { reject(failure); } } } });
        const r = response(await h.invoke());
        assert.deepEqual(r.body, { error: "Provisioning preparation failed" });
        assert.deepEqual(r.options, { status: 500 });
        assert.equal(h.counts.has("runner.call"), false);
    });
}
control("selection-class failure returns public400 and skips preparation", async () => {
    const h = setup({ fault: "selection.call", failure: new PublicSelectionError("PUBLIC invalid selection") });
    const r = response(await h.invoke());
    assert.deepEqual(r.body, { error: "PUBLIC invalid selection" });
    assert.deepEqual(r.options, { status: 400 });
    assert.equal(h.counts.has("vars.call"), false);
});
control("request parsing and each preparation await fence the next phase", async () => {
    for (const [label, next] of [["request.json.call", "selection.call"], ["vars.call", "nodes.call"], ["nodes.call", "inventory.call"], ["inventory.call", "prisma.job"], ["prisma.create.call", "controller.construct"]]) {
        let release;
        const pending = new Promise(resolve => { release = resolve; });
        const h = setup({ returns: { [label]: pending } });
        const result = h.invoke();
        for (let i = 0; i < 8; i++)
            await Promise.resolve();
        assert.equal(h.counts.has(label), true);
        assert.equal(h.counts.has(next), false);
        assert.ok(release);
        release(label === "request.json.call" ? {} : label === "prisma.create.call" ? h.job : undefined);
        assert.deepEqual(response(await result).body, { success: true, jobId: "PUBLIC-job-id" });
    }
});
for (const occurrence of [2, 3]) {
    control("later job id fault retains only prior inert registration: " + occurrence, async () => {
        const h = setup({ fault: "job.id", occurrence });
        const r = response(await h.invoke());
        assert.deepEqual(r.options, { status: 500 });
        assert.equal(h.registrations.length, 1);
        assert.equal(h.counts.has("runner.call"), occurrence === 3);
    });
}
control("void runner result is discarded without then inspection or awaiting", async () => {
    let inspected = false;
    const h = setup({ returns: { "runner.call": { get then() { inspected = true; throw new Error("PUBLIC must remain inert"); } } } });
    assert.deepEqual(response(await h.invoke()).body, { success: true, jobId: "PUBLIC-job-id" });
    assert.equal(inspected, false);
});
control("successful return adopts synthetic response Promise", async () => {
    const sentinel = { public: "adopted response" };
    const h = setup({ responseResult: () => Promise.resolve(sentinel) });
    assert.equal(await h.invoke(), sentinel);
});
control("successful returned Promise rejection bypasses synchronous catch", async () => {
    const failure = new Error("PUBLIC asynchronous response refusal");
    const h = setup({ responseResult: () => ({ then(_resolve, reject) { reject(failure); } }) });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.equal(h.counts.has("selectionError.instanceof"), false);
    assert.equal(h.counts.get("response.call"), 1);
});
control("disabled branch response rejection remains outside catch", async () => {
    const failure = new Error("PUBLIC disabled response refusal");
    const h = setup({ capability: false, responseResult: () => ({ then(_resolve, reject) { reject(failure); } }) });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.equal(h.counts.has("selectionError.instanceof"), false);
});
control("catch classifier fault propagates unchanged", async () => {
    const failure = new Error("PUBLIC classifier failure");
    const h = setup({ returns: { "request.json.call": { then(_r, reject) { reject("PUBLIC rejected body"); } } }, fault: "selectionError.instanceof", failure });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.equal(h.counts.has("response.member"), false);
});
control("selection error message getter failure propagates from catch", async () => {
    const failure = new Error("PUBLIC message failure");
    const selected = new PublicSelectionError();
    Object.defineProperty(selected, "message", { get() { throw failure; } });
    const h = setup({ fault: "selection.call", failure: selected });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.equal(h.counts.get("response.member"), 1);
    assert.equal(h.counts.has("response.call"), false);
});
control("catch response fault propagates without recursively catching", async () => {
    const failure = new Error("PUBLIC catch response failure");
    const h = setup({ returns: { "request.json.call": { then(_r, reject) { reject("PUBLIC parse refusal"); } } }, fault: "response.call", failure });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.equal(h.counts.get("selectionError.instanceof"), 1);
    assert.equal(h.counts.get("response.call"), 1);
});
control("catch response Promise rejection is adopted unchanged", async () => {
    const failure = new Error("PUBLIC catch asynchronous failure");
    const h = setup({ fault: "selection.call", failure: new PublicSelectionError("PUBLIC selection"), responseResult: () => ({ then(_r, reject) { reject(failure); } }) });
    await assert.rejects(h.invoke(), x => x === failure);
    assert.equal(h.counts.get("response.call"), 1);
});
assert.equal(count, 61);
