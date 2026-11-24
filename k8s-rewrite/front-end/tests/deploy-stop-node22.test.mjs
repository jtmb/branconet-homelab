import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

// Distinct supported PUBLIC selected-declaration controls; historical63 remain frozen.
// Real module/imports/initializers/auth/validator/DB/jobs/controllers/cancellation stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/app/api/deploy/stop/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), 'd809b978c2575c2036ba80b81ac3e80a5f50776ff8640a0e297cfc13edbbcde1');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '3cf65f67dee0231d09dfb3cc9a78d644a89c95eb4737d8f58666de3f86f69fc9');
const ast = ts.createSourceFile('selected.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'POST');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.equal(node.parameters.length, 1);
assert.equal(node.parameters[0].getText(ast), 'request: NextRequest');
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function POST(request: NextRequest) {\n  const auth = await requireOperator();\n  if (auth instanceof NextResponse) return auth;\n  try {\n    const jobId = request.nextUrl.searchParams.get(\"jobId\") ?? (await request.json().catch(() => ({}))).jobId;\n    if (!jobIdValid(jobId)) return NextResponse.json({ error: \"Valid jobId is required\" }, { status: 400 });\n    const job = await prisma.job.findUnique({ where: { id: jobId }, select: { id: true, status: true } });\n    if (!job) return NextResponse.json({ error: \"Job not found\" }, { status: 404 });\n    if (job.status !== \"running\") return NextResponse.json({ error: \"Job is already complete\" }, { status: 409 });\n    const controller = activeJobs.get(jobId);\n    if (!controller) return NextResponse.json({ error: \"Job is not running in this process; inspect the operator runner\" }, { status: 409 });\n    controller.abort();\n    return NextResponse.json({ success: true, jobId, stopping: true }, { status: 202 });\n  } catch { return NextResponse.json({ error: \"Job cancellation unavailable\" }, { status: 503 }); }\n}");
assert.equal(digest(declaration), '66cc55810048964b4ac5cd0a4abfb33737e08dfdc14562a4c8cdcb00811c6f91');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '399115400d6d3468e2958c2685eeb7d49cd0e13af85247575f585b1a121eb1c4');
const compiled = ts.transpileModule(declaration.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const javascript = compiled.outputText;
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const bind = new Function('requireOperator', 'NextResponse', 'jobIdValid', 'prisma', 'activeJobs', javascript + '\nreturn POST;');
class PublicResponse {
    body;
    status;
    constructor(body, status) { this.body = body; this.status = status; }
}
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
function setup(options = {}) {
    const events = [];
    const calls = { validation: [], database: [], active: [], abort: [], responses: [] };
    const sentinel = options.fault ?? Object.freeze({ publicFault: 'synthetic-only' });
    let thrown = false;
    function mark(name) {
        events.push(name);
        if (!thrown && options.faultAt === name) {
            thrown = true;
            throw sentinel;
        }
    }
    function prop(target, name, stage, value) {
        Object.defineProperty(target, name, { configurable: true, get() { mark(stage); return value(); } });
    }
    const request = {}, url = {}, params = {}, prisma = {}, jobs = {}, active = {}, controller = {}, job = {};
    class Response extends PublicResponse {
    }
    prop(Response, Symbol.hasInstance, 'instance.get', () => function (value) {
        assert.equal(this, Response);
        mark('instance.call');
        return Function.prototype[Symbol.hasInstance].call(PublicResponse, value);
    });
    prop(Response, 'json', 'response.json.get', () => function (body, responseOptions) {
        assert.equal(this, Response);
        mark('response.json.call');
        calls.responses.push([body, responseOptions]);
        return options.response ? options.response(body, responseOptions) : new Response(body, responseOptions.status);
    });
    const denied = new Response({ publicDenial: true }, 403);
    const requireOperator = function (...args) {
        assert.equal(this, undefined);
        assert.deepEqual(args, []);
        mark('auth.call');
        return options.authPromise ?? Promise.resolve(options.denied ? denied : { publicActor: 'operator-metadata' });
    };
    prop(request, 'nextUrl', 'request.nextUrl.get', () => url);
    prop(url, 'searchParams', 'url.searchParams.get', () => params);
    prop(params, 'get', 'params.get.get', () => function (...args) {
        assert.equal(this, params);
        assert.deepEqual(args, ['jobId']);
        mark('params.get.call');
        return Object.hasOwn(options, 'query') ? options.query : 'public-job';
    });
    const body = {};
    prop(body, 'jobId', 'body.jobId.get', () => 'public-body-job');
    prop(request, 'json', 'request.json.get', () => function (...args) {
        assert.equal(this, request);
        assert.deepEqual(args, []);
        mark('request.json.call');
        const value = Object.hasOwn(options, 'body') ? options.body : body;
        const carrier = {};
        prop(carrier, 'catch', 'json.catch.get', () => function (handler) {
            assert.equal(this, carrier);
            assert.equal(arguments.length, 1);
            assert.equal(typeof handler, 'function');
            mark('json.catch.call');
            if (Object.hasOwn(options, 'jsonRejection')) {
                return Promise.reject(options.jsonRejection).catch(reason => {
                    mark('json.rejection.handler');
                    const result = handler(reason);
                    assert.deepEqual(result, {});
                    return result;
                });
            }
            return Promise.resolve(value);
        });
        return carrier;
    });
    const jobIdValid = function (...args) {
        assert.equal(this, undefined);
        mark('validator.call');
        calls.validation.push(args);
        return Object.hasOwn(options, 'valid') ? options.valid : true;
    };
    prop(prisma, 'job', 'prisma.job.get', () => jobs);
    prop(jobs, 'findUnique', 'job.findUnique.get', () => function (...args) {
        assert.equal(this, jobs);
        mark('job.findUnique.call');
        calls.database.push(args);
        return options.databasePromise ?? Promise.resolve(Object.hasOwn(options, 'job') ? options.job : job);
    });
    prop(job, 'status', 'job.status.get', () => 'running');
    Object.defineProperty(job, 'id', { get() { throw new Error('returned job.id must remain unread'); } });
    prop(active, 'get', 'active.get.get', () => function (...args) {
        assert.equal(this, active);
        mark('active.get.call');
        calls.active.push(args);
        return Object.hasOwn(options, 'controller') ? options.controller : controller;
    });
    prop(controller, 'abort', 'controller.abort.get', () => function (...args) {
        assert.equal(this, controller);
        mark('controller.abort.call');
        calls.abort.push(args);
        return options.abortReturn;
    });
    const handler = bind(requireOperator, Response, jobIdValid, prisma, active);
    return { handler, request, events, calls, sentinel, denied, Response, run: () => handler(request) };
}
function response(value, status, body) {
    assert.ok(value instanceof PublicResponse);
    assert.equal(value.status, status);
    assert.deepEqual(value.body, body);
}
const prefix = ['auth.call', 'instance.get', 'instance.call'];
const selection = ['request.nextUrl.get', 'url.searchParams.get', 'params.get.get', 'params.get.call'];
const database = ['validator.call', 'prisma.job.get', 'job.findUnique.get', 'job.findUnique.call'];
const cancellation = ['job.status.get', 'active.get.get', 'active.get.call', 'controller.abort.get', 'controller.abort.call'];
const reply = ['response.json.get', 'response.json.call'];
control('exact exported async declaration has one request parameter and synthetic bindings only', () => {
    const s = setup();
    assert.equal(s.handler.length, 1);
    assert.equal(s.handler.constructor.name, 'AsyncFunction');
    assert.equal(node.parameters.length, 1);
    assert.equal(node.parameters[0].name.text, 'request');
    assert.ok(!javascript.includes('require('));
    assert.deepEqual(s.events, []);
});
control('query success preserves exact member/call order, receivers, arguments, selected ID and202 metadata', async () => {
    const s = setup();
    response(await s.run(), 202, { success: true, jobId: 'public-job', stopping: true });
    assert.deepEqual(s.events, [...prefix, ...selection, ...database, ...cancellation, ...reply]);
    assert.deepEqual(s.calls.validation, [['public-job']]);
    assert.deepEqual(s.calls.database, [[{ where: { id: 'public-job' }, select: { id: true, status: true } }]]);
    assert.deepEqual(s.calls.active, [['public-job']]);
    assert.deepEqual(s.calls.abort, [[]]);
    assert.deepEqual(s.calls.responses, [[{ success: true, jobId: 'public-job', stopping: true }, { status: 202 }]]);
});
control('authorization denial returns the identical response before any request access', async () => {
    const s = setup({ denied: true });
    assert.equal(await s.run(), s.denied);
    assert.deepEqual(s.events, prefix);
});
for (const stage of ['auth.call', 'instance.get', 'instance.call']) {
    control('outside-try fault propagates exactly: ' + stage, async () => {
        const s = setup({ faultAt: stage });
        await assert.rejects(s.run(), e => e === s.sentinel);
        assert.deepEqual(s.events, prefix.slice(0, prefix.indexOf(stage) + 1));
        assert.deepEqual(s.calls.responses, []);
    });
}
control('authorization rejection propagates without entering instance or request checks', async () => {
    const gate = deferred();
    const s = setup({ authPromise: gate.promise });
    const result = s.run();
    assert.deepEqual(s.events, ['auth.call']);
    gate.reject(s.sentinel);
    await assert.rejects(result, e => e === s.sentinel);
    assert.deepEqual(s.events, ['auth.call']);
});
control('authorization await fences every later access', async () => {
    const gate = deferred();
    const s = setup({ authPromise: gate.promise });
    const result = s.run();
    assert.deepEqual(s.events, ['auth.call']);
    await Promise.resolve();
    assert.deepEqual(s.events, ['auth.call']);
    gate.resolve({ publicActor: true });
    response(await result, 202, { success: true, jobId: 'public-job', stopping: true });
});
for (const query of [null, undefined]) {
    control('nullish query uses JSON catch binding then selected body ID: ' + String(query), async () => {
        const s = setup({ query });
        response(await s.run(), 202, { success: true, jobId: 'public-body-job', stopping: true });
        assert.deepEqual(s.events, [...prefix, ...selection, 'request.json.get', 'request.json.call', 'json.catch.get', 'json.catch.call', 'body.jobId.get', ...database, ...cancellation, ...reply]);
        assert.deepEqual(s.calls.validation, [['public-body-job']]);
        assert.deepEqual(s.calls.active, [['public-body-job']]);
    });
}
for (const [label, query] of [['empty-string', ''], ['false', false], ['zero', 0], ['object', Object.freeze({ publicSelection: true })], ['array', []]]) {
    control('nonnullish query bypasses JSON and passes selected metadata unchanged: ' + label, async () => {
        const s = setup({ query });
        response(await s.run(), 202, { success: true, jobId: query, stopping: true });
        assert.deepEqual(s.calls.validation, [[query]]);
        assert.deepEqual(s.calls.active, [[query]]);
        assert.ok(!s.events.some(x => x.startsWith('request.json')));
    });
}
for (const valid of [false, undefined, null, 0, '']) {
    control('falsy synthetic validator refuses400 before ORM/cancellation: ' + String(valid), async () => {
        const s = setup({ valid });
        response(await s.run(), 400, { error: 'Valid jobId is required' });
        assert.deepEqual(s.events, [...prefix, ...selection, 'validator.call', ...reply]);
        assert.deepEqual(s.calls.database, []);
        assert.deepEqual(s.calls.active, []);
    });
}
control('JSON rejection uses exact source catch callback empty-object result and cannot expose the fault', async () => {
    const s = setup({ query: null, valid: false, jsonRejection: { publicFault: 'json-refusal' } });
    response(await s.run(), 400, { error: 'Valid jobId is required' });
    assert.ok(s.events.includes('json.rejection.handler'));
    assert.deepEqual(s.calls.validation, [[undefined]]);
});
for (const body of [null, undefined]) {
    control('nullish JSON body property access is caught503: ' + String(body), async () => {
        const s = setup({ query: null, body });
        response(await s.run(), 503, { error: 'Job cancellation unavailable' });
        assert.deepEqual(s.calls.validation, []);
        assert.deepEqual(s.calls.database, []);
    });
}
control('JSON catch result await fences validator and ORM', async () => {
    const gate = deferred();
    const s = setup({ query: null, body: gate.promise });
    const result = s.run();
    await Promise.resolve();
    assert.ok(s.events.includes('json.catch.call'));
    assert.ok(!s.events.includes('validator.call'));
    gate.resolve({ jobId: 'public-later-body' });
    response(await result, 202, { success: true, jobId: 'public-later-body', stopping: true });
});
control('findUnique await fences status, registry and abort', async () => {
    const gate = deferred();
    const s = setup({ databasePromise: gate.promise });
    const result = s.run();
    await Promise.resolve();
    assert.deepEqual(s.events, [...prefix, ...selection, ...database]);
    gate.resolve({ id: 'different-returned-id', status: 'running' });
    response(await result, 202, { success: true, jobId: 'public-job', stopping: true });
    assert.deepEqual(s.calls.active, [['public-job']]);
});
control('findUnique rejection is caught503 before any cancellation', async () => {
    const gate = deferred();
    const s = setup({ databasePromise: gate.promise });
    const result = s.run();
    await Promise.resolve();
    gate.reject(s.sentinel);
    response(await result, 503, { error: 'Job cancellation unavailable' });
    assert.deepEqual(s.calls.active, []);
    assert.deepEqual(s.calls.abort, []);
});
for (const job of [null, undefined, false, 0]) {
    control('falsy synthetic job returns404 before registry: ' + String(job), async () => {
        const s = setup({ job });
        response(await s.run(), 404, { error: 'Job not found' });
        assert.deepEqual(s.events, [...prefix, ...selection, ...database, ...reply]);
        assert.deepEqual(s.calls.active, []);
    });
}
for (const status of ['success', 'failed', '', undefined, Object('running')]) {
    control('strict non-running status returns409 before registry: ' + String(status), async () => {
        const s = setup({ job: { id: 'different-public-id', status } });
        response(await s.run(), 409, { error: 'Job is already complete' });
        assert.deepEqual(s.calls.active, []);
        assert.deepEqual(s.calls.abort, []);
    });
}
for (const controller of [null, undefined, false, 0]) {
    control('falsy synthetic registry result returns fixed unowned409: ' + String(controller), async () => {
        const s = setup({ controller });
        response(await s.run(), 409, { error: 'Job is not running in this process; inspect the operator runner' });
        assert.deepEqual(s.calls.active, [['public-job']]);
        assert.deepEqual(s.calls.abort, []);
    });
}
for (const stage of [...selection, ...database, ...cancellation, 'request.json.get', 'request.json.call', 'json.catch.get', 'json.catch.call', 'body.jobId.get', ...reply]) {
    control('inside-try immediate fault returns fixed503, without later effects: ' + stage, async () => {
        const fallback = stage.startsWith('request.json') || stage.startsWith('json.') || stage.startsWith('body.');
        const s = setup({ query: fallback ? null : 'public-job', faultAt: stage });
        response(await s.run(), 503, { error: 'Job cancellation unavailable' });
        assert.equal(s.events.filter(x => x === stage).length, stage.startsWith('response.') ? 2 : 1);
        const position = s.events.indexOf(stage);
        assert.deepEqual(s.events.slice(position + 1), reply);
    });
}
control('abort return is discarded without then inspection or awaiting', async () => {
    const result = {};
    Object.defineProperty(result, 'then', { get() { throw new Error('abort return must stay unobserved'); } });
    const s = setup({ abortReturn: result });
    response(await s.run(), 202, { success: true, jobId: 'public-job', stopping: true });
});
control('response Promise adoption succeeds without another response construction', async () => {
    const gate = deferred();
    const s = setup({ response: () => gate.promise });
    const result = s.run();
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(s.calls.responses.length, 1);
    const value = new s.Response({ publicAdoption: true }, 202);
    gate.resolve(value);
    assert.equal(await result, value);
});
control('returned response rejection propagates without entering fixed503 catch', async () => {
    const gate = deferred();
    const s = setup({ response: () => gate.promise });
    const result = s.run();
    await Promise.resolve();
    await Promise.resolve();
    gate.reject(s.sentinel);
    await assert.rejects(result, e => e === s.sentinel);
    assert.equal(s.calls.responses.length, 1);
    assert.deepEqual(s.calls.responses[0][1], { status: 202 });
});
control('failure constructing the catch response propagates exactly', async () => {
    const fault = Object.freeze({ publicFault: 'response-construction' });
    const s = setup({ valid: false, response: () => { throw fault; } });
    await assert.rejects(s.run(), e => e === fault);
    assert.deepEqual(s.calls.responses.map(x => x[1]), [{ status: 400 }, { status: 503 }]);
});
assert.equal(count, 63);
