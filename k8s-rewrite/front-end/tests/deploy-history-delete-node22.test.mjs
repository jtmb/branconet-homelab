import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';

// Distinct supported PUBLIC selected-declaration controls; historical66 remain frozen.
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
const nodes = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'DELETE');
assert.equal(nodes.length, 1);
const selected = nodes[0];
assert.deepEqual(selected.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
const declaration = selected.getText(ast);
const expectedDeclaration = "export async function DELETE(request: NextRequest) {\n  const auth = await requireOperator();\n  if (auth instanceof NextResponse) return auth;\n  const jobId = request.nextUrl.searchParams.get(\"jobId\");\n  if (!jobIdValid(jobId)) return NextResponse.json({ error: \"Valid jobId is required\" }, { status: 400 });\n  try {\n    const removed = await prisma.job.deleteMany({ where: { id: jobId, status: { not: \"running\" } } });\n    if (!removed.count) {\n      const exists = await prisma.job.findUnique({ where: { id: jobId }, select: { id: true } });\n      return NextResponse.json({ error: exists ? \"Running jobs cannot be deleted\" : \"Job not found\" }, { status: exists ? 409 : 404 });\n    }\n    return NextResponse.json({ success: true });\n  } catch { return NextResponse.json({ error: \"Job deletion unavailable\" }, { status: 503 }); }\n}";
assert.equal(declaration, expectedDeclaration);
assert.equal(digest(declaration), '2804717d06d00415b14294161101665c441702614fefbaf17c8fc93ace274851');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '68ee1555655a5b9868cee4e36918f4dbc2c75013b9c7f7c94bf9b54afb9aa75b');
const emitted = ts.transpileModule(declaration.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(emitted.diagnostics.length, 0);
const javascript = emitted.outputText;
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
const factory = new Function('requireOperator', 'NextResponse', 'jobIdValid', 'prisma', javascript + '\nreturn DELETE;');
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
    const calls = { auth: [], valid: [], remove: [], lookup: [], responses: [] };
    const sentinel = Object.freeze({ publicFault: 'inert-immediate-binding' });
    const occurrences = new Map();
    function mark(name) {
        events.push(name);
        const n = (occurrences.get(name) ?? 0) + 1;
        occurrences.set(name, n);
        if (options.faultAt === name && n === (options.faultOccurrence ?? 1))
            throw sentinel;
    }
    function prop(target, name, label, value) {
        Object.defineProperty(target, name, { configurable: true, get() { mark(label); return value(); } });
    }
    const request = {}, url = {}, params = {}, prisma = {}, job = {}, removed = {};
    class Response extends PublicResponse {
    }
    prop(Response, Symbol.hasInstance, 'instance.get', () => function (value) {
        assert.equal(this, Response);
        mark('instance.call');
        return Function.prototype[Symbol.hasInstance].call(PublicResponse, value);
    });
    prop(Response, 'json', 'response.get', () => function (...args) {
        assert.equal(this, Response);
        mark('response.call');
        calls.responses.push(args);
        return options.response ? options.response(args[0], args[1], calls.responses.length) : new Response(args[0], args[1]);
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
        assert.deepEqual(args, ['jobId']);
        mark('query.jobId');
        return Object.hasOwn(options, 'id') ? options.id : 'public-job';
    });
    const jobIdValid = function (...args) {
        assert.equal(this, undefined);
        mark('valid.call');
        calls.valid.push(args);
        return Object.hasOwn(options, 'valid') ? options.valid : true;
    };
    prop(prisma, 'job', 'prisma.job', () => job);
    prop(job, 'deleteMany', 'delete.get', () => function (...args) {
        assert.equal(this, job);
        mark('delete.call');
        calls.remove.push(args);
        return options.deletePromise ?? Promise.resolve(Object.hasOwn(options, 'removed') ? options.removed : removed);
    });
    prop(removed, 'count', 'removed.count', () => Object.hasOwn(options, 'count') ? options.count : 1);
    prop(job, 'findUnique', 'lookup.get', () => function (...args) {
        assert.equal(this, job);
        mark('lookup.call');
        calls.lookup.push(args);
        return options.lookupPromise ?? Promise.resolve(Object.hasOwn(options, 'exists') ? options.exists : { id: 'public-job' });
    });
    const handler = factory(requireOperator, Response, jobIdValid, prisma);
    return { handler, request, run: () => handler(request), events, calls, sentinel, denied };
}
function response(value, status, body) {
    assert.ok(value instanceof PublicResponse);
    assert.equal(value.options.status ?? 200, status);
    assert.deepEqual(value.body, body);
}
const auth = ['auth.call', 'instance.get', 'instance.call'];
const selection = ['request.nextUrl', 'url.searchParams', 'params.get', 'query.jobId', 'valid.call'];
const prefix = [...auth, ...selection];
const remove = ['prisma.job', 'delete.get', 'delete.call'];
const lookup = ['prisma.job', 'lookup.get', 'lookup.call'];
const reply = ['response.get', 'response.call'];
const unavailable = { error: 'Job deletion unavailable' };
const invalid = { error: 'Valid jobId is required' };
control('exact exported async DELETE declaration only, one request and no neighbours', () => {
    const s = setup();
    assert.equal(s.handler.length, 1);
    assert.equal(s.handler.constructor.name, 'AsyncFunction');
    assert.equal(selected.parameters.length, 1);
    assert.equal(selected.parameters[0].name.text, 'request');
    assert.ok(!javascript.includes('require('));
    assert.ok(!javascript.includes('GET('));
    assert.deepEqual(s.events, []);
});
control('successful deletion uses exact completed-only predicate, receiver and single response argument', async () => {
    const s = setup();
    response(await s.run(), 200, { success: true });
    assert.deepEqual(s.events, [...prefix, ...remove, 'removed.count', ...reply]);
    assert.deepEqual(s.calls.auth, [[]]);
    assert.deepEqual(s.calls.valid, [['public-job']]);
    assert.deepEqual(s.calls.remove, [[{ where: { id: 'public-job', status: { not: 'running' } } }]]);
    assert.deepEqual(s.calls.lookup, []);
    assert.deepEqual(s.calls.responses, [[{ success: true }]]);
});
control('denial preserves identical response before request validation or database access', async () => {
    const s = setup({ denied: true });
    assert.equal(await s.run(), s.denied);
    assert.deepEqual(s.events, auth);
    assert.deepEqual(s.calls.valid, []);
    assert.deepEqual(s.calls.remove, []);
    assert.deepEqual(s.calls.responses, []);
});
control('authorization await fences request and database bindings', async () => {
    const gate = deferred();
    const s = setup({ authPromise: gate.promise });
    const pending = s.run();
    assert.deepEqual(s.events, ['auth.call']);
    await Promise.resolve();
    assert.deepEqual(s.events, ['auth.call']);
    gate.resolve({ publicActor: true });
    response(await pending, 200, { success: true });
});
control('delete await fences count lookup and response', async () => {
    const gate = deferred();
    const s = setup({ deletePromise: gate.promise });
    const pending = s.run();
    await Promise.resolve();
    assert.deepEqual(s.events, [...prefix, ...remove]);
    gate.resolve({ count: 0 });
    response(await pending, 409, { error: 'Running jobs cannot be deleted' });
});
control('lookup await fences conflict and notfound response', async () => {
    const gate = deferred();
    const s = setup({ count: 0, lookupPromise: gate.promise });
    const pending = s.run();
    await Promise.resolve();
    await Promise.resolve();
    assert.deepEqual(s.events, [...prefix, ...remove, 'removed.count', ...lookup]);
    gate.resolve(null);
    response(await pending, 404, { error: 'Job not found' });
});
for (const [label, exists, status, error] of [['present', { id: 'public-job' }, 409, 'Running jobs cannot be deleted'], ['absent', null, 404, 'Job not found']]) {
    control('zero-count lookup branch: ' + label, async () => {
        const s = setup({ count: 0, exists });
        response(await s.run(), status, { error });
        assert.deepEqual(s.events, [...prefix, ...remove, 'removed.count', ...lookup, ...reply]);
        assert.deepEqual(s.calls.lookup, [[{ where: { id: 'public-job' }, select: { id: true } }]]);
        assert.deepEqual(s.calls.responses, [[{ error }, { status }]]);
    });
}
for (const [label, id] of [['null', null], ['empty', ''], ['synthetic-text', 'public-invalid']]) {
    control('inert validator refusal is400 before database access: ' + label, async () => {
        const s = setup({ id, valid: false });
        response(await s.run(), 400, invalid);
        assert.deepEqual(s.events, [...prefix, ...reply]);
        assert.deepEqual(s.calls.valid, [[id]]);
        assert.deepEqual(s.calls.remove, []);
        assert.deepEqual(s.calls.responses, [[invalid, { status: 400 }]]);
    });
}
for (const [label, valid] of [['zero', 0], ['null', null], ['undefined', undefined], ['empty', '']]) {
    control('synthetic validator falsiness characterization: ' + label, async () => {
        const s = setup({ valid });
        response(await s.run(), 400, invalid);
        assert.deepEqual(s.calls.remove, []);
    });
}
for (const [label, count] of [['one', 1], ['multiple', 2], ['synthetic-negative', -1], ['synthetic-object', {}]]) {
    control('deletion count truthiness characterization: ' + label, async () => {
        const s = setup({ count });
        response(await s.run(), 200, { success: true });
        assert.deepEqual(s.calls.lookup, []);
        assert.equal(s.events.filter(e => e === 'removed.count').length, 1);
    });
}
for (const [label, count] of [['zero', 0], ['undefined', undefined], ['null', null], ['false', false], ['empty', ''], ['nan', NaN]]) {
    control('synthetic count falsiness enters lookup exactly once: ' + label, async () => {
        const s = setup({ count, exists: null });
        response(await s.run(), 404, { error: 'Job not found' });
        assert.equal(s.calls.remove.length, 1);
        assert.equal(s.calls.lookup.length, 1);
    });
}
for (const [label, exists, status] of [['undefined', undefined, 404], ['false', false, 404], ['zero', 0, 404], ['empty', '', 404], ['empty-object', {}, 409]]) {
    control('synthetic existence truthiness without row-field access: ' + label, async () => {
        const s = setup({ count: 0, exists });
        response(await s.run(), status, { error: status === 409 ? 'Running jobs cannot be deleted' : 'Job not found' });
    });
}
for (const fault of ['auth.call', 'instance.get', 'instance.call', ...selection]) {
    control('outside-try binding fault propagates without503 or database: ' + fault, async () => {
        const s = setup({ faultAt: fault });
        await assert.rejects(s.run(), e => e === s.sentinel);
        assert.deepEqual(s.calls.remove, []);
        assert.deepEqual(s.calls.responses, []);
        assert.equal(s.events.at(-1), fault);
    });
}
for (const fault of reply) {
    control('invalid400 response fault stays outside try: ' + fault, async () => {
        const s = setup({ valid: false, faultAt: fault });
        await assert.rejects(s.run(), e => e === s.sentinel);
        assert.deepEqual(s.calls.remove, []);
        assert.equal(s.events.filter(e => e === 'response.get').length, 1);
    });
}
for (const [fault, occurrence, count] of [['prisma.job', 1, 1], ['delete.get', 1, 1], ['delete.call', 1, 1], ['removed.count', 1, 1], ['prisma.job', 2, 0], ['lookup.get', 1, 0], ['lookup.call', 1, 0]]) {
    control('inside-try binding fault returns fixed503 without retry: ' + fault + occurrence, async () => {
        const s = setup({ count, faultAt: fault, faultOccurrence: occurrence });
        response(await s.run(), 503, unavailable);
        assert.deepEqual(s.events.slice(-2), reply);
        assert.equal(s.calls.responses.length, 1);
        assert.ok(s.calls.remove.length <= 1);
        assert.ok(s.calls.lookup.length <= 1);
    });
}
for (const branch of ['success', 'conflict', 'missing']) {
    for (const fault of reply) {
        control('synchronous response fault enters catch on ' + branch + ': ' + fault, async () => {
            const s = setup({ count: branch === 'success' ? 1 : 0, exists: branch === 'missing' ? null : {}, faultAt: fault });
            response(await s.run(), 503, unavailable);
            assert.equal(s.events.filter(e => e === 'response.get').length, 2);
        });
    }
}
for (const removed of [null, undefined]) {
    control('synthetic nullish deletion result returns fixed503: ' + String(removed), async () => {
        const s = setup({ removed });
        response(await s.run(), 503, unavailable);
        assert.deepEqual(s.calls.lookup, []);
    });
}
control('authorization rejection propagates before request access', async () => {
    const gate = deferred();
    const s = setup({ authPromise: gate.promise });
    const pending = s.run();
    const check = assert.rejects(pending, e => e === s.sentinel);
    gate.reject(s.sentinel);
    await check;
    assert.deepEqual(s.events, ['auth.call']);
});
for (const phase of ['delete', 'lookup']) {
    control('awaited database rejection becomes fixed503: ' + phase, async () => {
        const gate = deferred();
        const s = setup(phase === 'delete' ? { deletePromise: gate.promise } : { count: 0, lookupPromise: gate.promise });
        const pending = s.run();
        gate.reject(s.sentinel);
        response(await pending, 503, unavailable);
        assert.deepEqual(s.calls.responses, [[unavailable, { status: 503 }]]);
    });
}
for (const branch of ['invalid', 'success', 'conflict', 'missing', 'catch']) {
    control('response promise rejection propagates without catch retry: ' + branch, async () => {
        const gate = deferred();
        const s = setup({ valid: branch !== 'invalid', count: branch === 'success' ? 1 : 0, exists: branch === 'missing' ? null : {}, faultAt: branch === 'catch' ? 'delete.call' : undefined, response: () => gate.promise });
        const pending = s.run();
        const check = assert.rejects(pending, e => e === s.sentinel);
        gate.reject(s.sentinel);
        await check;
        assert.equal(s.calls.responses.length, 1);
        assert.equal(s.events.filter(e => e === 'response.get').length, 1);
    });
}
control('unawaited response promise adopts exact fulfilled identity', async () => {
    const gate = deferred();
    const identity = Object.freeze({ publicResponseMetadata: true });
    const s = setup({ response: () => gate.promise });
    const pending = s.run();
    gate.resolve(identity);
    assert.equal(await pending, identity);
    assert.equal(s.calls.responses.length, 1);
});
control('catch response synchronous throw propagates with no further retry', async () => {
    const s = setup({ faultAt: 'delete.call', response: () => { throw new Error('public-response-fault'); } });
    await assert.rejects(s.run(), { message: 'public-response-fault' });
    assert.equal(s.calls.responses.length, 1);
});
control('identifiers and result objects are not coerced or inspected by this declaration', async () => {
    const id = Object.freeze({ publicID: true, toString() { throw new Error('coercion forbidden'); } });
    const exists = new Proxy({}, { get(_target, key) { if (key === 'then')
            return undefined; throw new Error('row inspection forbidden'); } });
    const s = setup({ id, count: 0, exists });
    response(await s.run(), 409, { error: 'Running jobs cannot be deleted' });
    assert.equal(s.calls.remove[0][0].where.id, id);
    assert.equal(s.calls.lookup[0][0].where.id, id);
});
assert.equal(count, 66);
