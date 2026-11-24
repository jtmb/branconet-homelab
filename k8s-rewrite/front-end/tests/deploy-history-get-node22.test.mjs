import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

// Distinct supported PUBLIC selected-declaration controls; historical80 remain frozen.
// Real module/imports/initializers/auth/operator/PrismaSQLORM/native/backend/recovery/HTTP/services inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/app/api/deploy/history/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), 'f0e082a86d2fa535ca8a7913899592f6f0227bbbaacc9facc6c9c77184996c09');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '57536eb39d49b4427a05dabcc72c0a39a78bcce4b021a5b1ab57cfe0395cbf16');
const ast = ts.createSourceFile('selected-history-delete.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
assert.equal(ast.parseDiagnostics.length, 0);
const nodes = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'GET');
assert.equal(nodes.length, 1);
const selected = nodes[0];
assert.deepEqual(selected.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
const declaration = selected.getText(ast);
const expectedDeclaration = "export async function GET(request: NextRequest) {\n  try {\n    const jobId = request.nextUrl.searchParams.get(\"jobId\");\n    if (jobId !== null) {\n      const auth = await requireOperator();\n      if (auth instanceof NextResponse) return auth;\n      const rawTail = request.nextUrl.searchParams.get(\"tail\") ?? \"65536\";\n      const tail = Number(rawTail);\n      if (!jobIdValid(jobId) || !/^\\d{1,5}$/.test(rawTail) || !Number.isInteger(tail) || tail < 1 || tail > 65536)\n        return NextResponse.json({ error: \"Valid jobId and tail from 1 to 65536 are required\" }, { status: 400 });\n      const result = await readJobTail(jobId, tail);\n      return result ? NextResponse.json(result, { headers: { \"Cache-Control\": \"private, no-store\" } })\n        : NextResponse.json({ error: \"Job not found\" }, { status: 404 });\n    }\n    const jobs = await prisma.job.findMany({ orderBy: { startedAt: \"desc\" }, take: 50,\n      select: { id: true, playbook: true, status: true, startedAt: true, finishedAt: true } });\n    return NextResponse.json(jobs, { headers: { \"Cache-Control\": \"private, no-store\" } });\n  } catch { return NextResponse.json({ error: \"Job history unavailable\" }, { status: 503 }); }\n}";
assert.equal(declaration, expectedDeclaration);
assert.equal(digest(declaration), '262ef44998f5ed8899c854458a12851ada920275d881255944ea8a402761638e');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '5619269d1e300fe5fcdab70a680a12da27680e2876ae120273521f965e441257');
const emitted = ts.transpileModule(declaration.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(emitted.diagnostics.length, 0);
const javascript = emitted.outputText;
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
const factory = new Function('requireOperator', 'NextResponse', 'jobIdValid', 'readJobTail', 'prisma', 'Number', javascript + '\nreturn GET;');
let count = 0;
const control = (...args) => { count++; return test(...args); };
class PublicResponse {
    body;
    options;
    constructor(body, options = {}) { this.body = body; this.options = options; }
}
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
function setup(options = {}) {
    const events = [];
    const calls = { auth: [], valid: [], number: [], integer: [], tail: [], list: [], responses: [] };
    const sentinel = Object.freeze({ publicFault: 'inert-binding-only' });
    const occurrences = new Map();
    function mark(name) {
        events.push(name);
        const count = (occurrences.get(name) ?? 0) + 1;
        occurrences.set(name, count);
        if (options.faultAt === name && count === (options.faultOccurrence ?? 1))
            throw sentinel;
    }
    function prop(target, name, label, value) {
        Object.defineProperty(target, name, { configurable: true, get() { mark(label); return value(); } });
    }
    const request = {}, url = {}, params = {}, prisma = {}, job = {};
    class Response extends PublicResponse {
    }
    prop(Response, Symbol.hasInstance, 'instance.get', () => function (value) {
        assert.equal(this, Response);
        mark('instance.call');
        return Function.prototype[Symbol.hasInstance].call(PublicResponse, value);
    });
    prop(Response, 'json', 'response.get', () => function (body, responseOptions) {
        assert.equal(this, Response);
        mark('response.call');
        calls.responses.push([body, responseOptions]);
        return options.response ? options.response(body, responseOptions, calls.responses.length) : new Response(body, responseOptions);
    });
    const denied = new Response({ publicDenial: true }, { status: 403 });
    const requireOperator = function (...args) {
        assert.equal(this, undefined);
        mark('auth.call');
        calls.auth.push(args);
        return options.authPromise ?? Promise.resolve(options.denied ? denied : { publicActor: true });
    };
    prop(request, 'nextUrl', 'request.nextUrl', () => url);
    prop(url, 'searchParams', 'url.searchParams', () => params);
    prop(params, 'get', 'params.get', () => function (...args) {
        assert.equal(this, params);
        assert.equal(args.length, 1);
        const name = args[0];
        assert.ok(name === 'jobId' || name === 'tail');
        mark('query.' + name);
        return name === 'jobId' ? (Object.hasOwn(options, 'id') ? options.id : 'public-job') : (Object.hasOwn(options, 'tail') ? options.tail : null);
    });
    const number = function (...args) {
        assert.equal(this, undefined);
        mark('number.call');
        calls.number.push(args);
        return Object.hasOwn(options, 'numeric') ? options.numeric : Number(args[0]);
    };
    prop(number, 'isInteger', 'integer.get', () => function (...args) {
        assert.equal(this, number);
        mark('integer.call');
        calls.integer.push(args);
        return Object.hasOwn(options, 'integer') ? options.integer : Number.isInteger(args[0]);
    });
    const jobIdValid = function (...args) {
        assert.equal(this, undefined);
        mark('valid.call');
        calls.valid.push(args);
        return Object.hasOwn(options, 'valid') ? options.valid : true;
    };
    const result = Object.freeze({ publicTailMetadata: true });
    const jobs = Object.freeze([{ id: 'public-job', playbook: 'public.yml', status: 'success', startedAt: 'public-start', finishedAt: null }]);
    const readJobTail = function (...args) {
        assert.equal(this, undefined);
        mark('tail.call');
        calls.tail.push(args);
        return options.tailPromise ?? Promise.resolve(Object.hasOwn(options, 'result') ? options.result : result);
    };
    prop(prisma, 'job', 'prisma.job', () => job);
    prop(job, 'findMany', 'job.findMany.get', () => function (...args) {
        assert.equal(this, job);
        mark('job.findMany.call');
        calls.list.push(args);
        return options.listPromise ?? Promise.resolve(Object.hasOwn(options, 'jobs') ? options.jobs : jobs);
    });
    const handler = factory(requireOperator, Response, jobIdValid, readJobTail, prisma, number);
    return { handler, request, run: () => handler(request), events, calls, sentinel, denied, result, jobs };
}
function response(value, status, body, headers) {
    assert.ok(value instanceof PublicResponse);
    assert.equal(value.options.status ?? 200, status);
    assert.deepEqual(value.body, body);
    assert.deepEqual(value.options.headers, headers);
}
const selection = (name) => ['request.nextUrl', 'url.searchParams', 'params.get', 'query.' + name];
const auth = ['auth.call', 'instance.get', 'instance.call'];
const validity = ['number.call', 'valid.call', 'integer.get', 'integer.call'];
const reply = ['response.get', 'response.call'];
const list = ['prisma.job', 'job.findMany.get', 'job.findMany.call'];
const prefix = [...selection('jobId'), ...auth, ...selection('tail')];
const noStore = { 'Cache-Control': 'private, no-store' };
const invalid = { error: 'Valid jobId and tail from 1 to 65536 are required' };
const unavailable = { error: 'Job history unavailable' };
control('exact selected exported async GET only, one request argument and no application imports', () => {
    const s = setup();
    assert.equal(s.handler.length, 1);
    assert.equal(s.handler.constructor.name, 'AsyncFunction');
    assert.equal(selected.parameters.length, 1);
    assert.equal(selected.parameters[0].name.text, 'request');
    assert.ok(!javascript.includes('require('));
    assert.ok(!javascript.includes('DELETE'));
    assert.deepEqual(s.events, []);
});
control('null ID metadata selection has exact receiver, query, five fields and no tail or operator access', async () => {
    const s = setup({ id: null });
    const result = await s.run();
    response(result, 200, s.jobs, noStore);
    assert.deepEqual(s.events, [...selection('jobId'), ...list, ...reply]);
    assert.deepEqual(s.calls.list, [[{ orderBy: { startedAt: 'desc' }, take: 50, select: { id: true, playbook: true, status: true, startedAt: true, finishedAt: true } }]]);
    assert.deepEqual(s.calls.auth, []);
    assert.deepEqual(s.calls.valid, []);
    assert.deepEqual(s.calls.tail, []);
    assert.equal(result.body, s.jobs);
});
control('explicit ID default tail preserves exact binding order, identity, arguments and no list access', async () => {
    const s = setup();
    const result = await s.run();
    response(result, 200, s.result, noStore);
    assert.deepEqual(s.events, [...prefix, ...validity, 'tail.call', ...reply]);
    assert.deepEqual(s.calls.auth, [[]]);
    assert.deepEqual(s.calls.number, [['65536']]);
    assert.deepEqual(s.calls.valid, [['public-job']]);
    assert.deepEqual(s.calls.integer, [[65536]]);
    assert.deepEqual(s.calls.tail, [['public-job', 65536]]);
    assert.deepEqual(s.calls.list, []);
    assert.equal(result.body, s.result);
});
control('denial returns identical response after ID selection and before tail access', async () => {
    const s = setup({ denied: true });
    assert.equal(await s.run(), s.denied);
    assert.deepEqual(s.events, [...selection('jobId'), ...auth]);
    assert.deepEqual(s.calls.responses, []);
    assert.deepEqual(s.calls.tail, []);
    assert.deepEqual(s.calls.list, []);
});
control('authorization await fences later tail, numeric, validator and lookup bindings', async () => {
    const gate = deferred();
    const s = setup({ authPromise: gate.promise });
    const pending = s.run();
    assert.deepEqual(s.events, [...selection('jobId'), 'auth.call']);
    await Promise.resolve();
    assert.deepEqual(s.calls.number, []);
    gate.resolve({ publicActor: true });
    response(await pending, 200, s.result, noStore);
});
for (const [label, id] of [['empty', ''], ['undefined-nondomain', undefined], ['false-nondomain', false], ['zero-nondomain', 0]]) {
    control('strict non-null ID selects operator path without truthiness fallback: ' + label, async () => {
        const s = setup({ id });
        response(await s.run(), 200, s.result, noStore);
        assert.deepEqual(s.calls.valid, [[id]]);
        assert.deepEqual(s.calls.tail, [[id, 65536]]);
        assert.deepEqual(s.calls.list, []);
    });
}
for (const [label, tail, expected] of [['minimum', '1', 1], ['maximum', '65536', 65536], ['five-digits', '65535', 65535], ['leading-zero', '00001', 1], ['null-default', null, 65536], ['undefined-default-nondomain', undefined, 65536]]) {
    control('tail selection boundary: ' + label, async () => {
        const s = setup({ tail });
        response(await s.run(), 200, s.result, noStore);
        assert.deepEqual(s.calls.tail, [['public-job', expected]]);
        assert.deepEqual(s.calls.number, [[tail ?? '65536']]);
    });
}
for (const tail of ['', '0', '00000', '65537', '99999', '100000', '-1', '+1', '1.0', '1e1', ' 1', '1 ', '１２', 'NaN', 'Infinity']) {
    control('invalid public tail refuses before selected lookup: ' + JSON.stringify(tail), async () => {
        const s = setup({ tail });
        response(await s.run(), 400, invalid);
        assert.deepEqual(s.calls.tail, []);
        assert.deepEqual(s.calls.list, []);
        assert.deepEqual(s.calls.number, [[tail]]);
        assert.deepEqual(s.calls.valid, [['public-job']]);
        assert.equal(s.calls.integer.length, /^\d{1,5}$/.test(tail) ? 1 : 0);
    });
}
control('literal regex rejects final newline before integer validation', async () => {
    const s = setup({ tail: '1\n' });
    response(await s.run(), 400, invalid);
    assert.deepEqual(s.calls.number, [['1\n']]);
    assert.deepEqual(s.calls.valid, [['public-job']]);
    assert.deepEqual(s.calls.integer, []);
    assert.deepEqual(s.calls.tail, []);
});
control('invalid job ID shortcircuits regex and integer checks after numeric conversion', async () => {
    const s = setup({ valid: false, tail: '1' });
    response(await s.run(), 400, invalid);
    assert.deepEqual(s.events, [...prefix, 'number.call', 'valid.call', ...reply]);
    assert.deepEqual(s.calls.tail, []);
});
for (const numeric of [NaN, Infinity, 1.5, 0, 65537]) {
    control('synthetic immediate Number result exercises integer and range refusal: ' + String(numeric), async () => {
        const s = setup({ tail: '1', numeric });
        response(await s.run(), 400, invalid);
        assert.deepEqual(s.calls.integer, [[numeric]]);
        assert.deepEqual(s.calls.tail, []);
    });
}
for (const result of [null, undefined, false, 0, '']) {
    control('falsy synthetic tail result is fixed404: ' + String(result), async () => {
        const s = setup({ result });
        response(await s.run(), 404, { error: 'Job not found' });
        assert.deepEqual(s.calls.tail, [['public-job', 65536]]);
    });
}
control('selected tail await fences response construction and preserves resolved result identity', async () => {
    const gate = deferred();
    const s = setup({ tailPromise: gate.promise });
    const pending = s.run();
    await Promise.resolve();
    assert.deepEqual(s.events, [...prefix, ...validity, 'tail.call']);
    assert.deepEqual(s.calls.responses, []);
    gate.resolve(s.result);
    const result = await pending;
    response(result, 200, s.result, noStore);
    assert.equal(result.body, s.result);
});
control('metadata list await fences response construction', async () => {
    const gate = deferred();
    const s = setup({ id: null, listPromise: gate.promise });
    const pending = s.run();
    assert.deepEqual(s.events, [...selection('jobId'), ...list]);
    assert.deepEqual(s.calls.responses, []);
    gate.resolve(s.jobs);
    response(await pending, 200, s.jobs, noStore);
});
for (const lane of ['auth', 'tail', 'list']) {
    control('awaited ' + lane + ' rejection becomes fixed503 without leaking the rejection', async () => {
        const gate = deferred();
        const options = lane === 'auth' ? { authPromise: gate.promise } : lane === 'tail' ? { tailPromise: gate.promise } : { id: null, listPromise: gate.promise };
        const s = setup(options);
        const pending = s.run();
        await Promise.resolve();
        gate.reject(s.sentinel);
        response(await pending, 503, unavailable);
        assert.deepEqual(s.calls.responses, [[unavailable, { status: 503 }]]);
    });
}
for (const lane of ['tail', 'list']) {
    const stages = lane === 'tail' ? [...selection('jobId'), ...auth, ...selection('tail'), ...validity, 'tail.call', ...reply] : [...selection('jobId'), ...list, ...reply];
    const seen = new Map();
    for (let index = 0; index < stages.length; index++) {
        const stage = stages[index];
        const occurrence = (seen.get(stage) ?? 0) + 1;
        seen.set(stage, occurrence);
        control('one-shot ' + lane + ' binding fault becomes fixed503 at ' + stage + '#' + occurrence, async () => {
            const s = setup({ ...(lane === 'list' ? { id: null } : {}), faultAt: stage, faultOccurrence: occurrence });
            response(await s.run(), 503, unavailable);
            assert.deepEqual(s.events, [...stages.slice(0, index + 1), ...reply]);
            assert.deepEqual(s.calls.responses.at(-1), [unavailable, { status: 503 }]);
        });
    }
}
control('synchronous success-response failure is caught but catch-response failure propagates', async () => {
    const fault = Object.freeze({ publicResponseFault: true });
    const s = setup({ response() { throw fault; } });
    await assert.rejects(s.run(), error => error === fault);
    assert.equal(s.calls.responses.length, 2);
    assert.deepEqual(s.calls.responses[1], [unavailable, { status: 503 }]);
});
for (const lane of ['tail', 'list', 'invalid', 'missing']) {
    control('unawaited ' + lane + ' response rejection is adopted outside catch', async () => {
        const gate = deferred();
        const options = lane === 'list' ? { id: null } : lane === 'invalid' ? { valid: false } : lane === 'missing' ? { result: null } : {};
        const s = setup({ ...options, response: () => gate.promise });
        const pending = s.run();
        await Promise.resolve();
        await Promise.resolve();
        assert.equal(s.calls.responses.length, 1);
        gate.reject(s.sentinel);
        await assert.rejects(pending, error => error === s.sentinel);
        assert.equal(s.calls.responses.length, 1);
    });
}
control('catch-response Promise rejection propagates without a second catch attempt', async () => {
    const gate = deferred();
    const s = setup({ faultAt: 'number.call', response: () => gate.promise });
    const pending = s.run();
    await Promise.resolve();
    assert.deepEqual(s.calls.responses, [[unavailable, { status: 503 }]]);
    gate.reject(s.sentinel);
    await assert.rejects(pending, error => error === s.sentinel);
    assert.equal(s.calls.responses.length, 1);
});
assert.equal(count, 80);
