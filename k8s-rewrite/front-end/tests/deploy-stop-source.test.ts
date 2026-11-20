import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

// PUBLIC SOURCE only. No imports, module initializers, real services or controllers execute.
const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compiler, 'explicit current TypeScript input is required');
const ts = createRequire(import.meta.url)(compiler);
const source = readFileSync(new URL('../src/app/api/deploy/stop/route.ts', import.meta.url), 'utf8');
assert.equal(createHash('sha256').update(source).digest('hex'), '3cf65f67dee0231d09dfb3cc9a78d644a89c95eb4737d8f58666de3f86f69fc9');
const ast = ts.createSourceFile('selected-stop-route.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const selected = ast.statements.filter((n: { kind: number; name?: { text: string } }) => n.kind === ts.SyntaxKind.FunctionDeclaration && n.name?.text === 'POST');
assert.equal(selected.length, 1);
const node = selected[0];
assert.ok(node.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(node.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.AsyncKeyword));
const declaration = source.slice(node.getStart(ast), node.end);
const javascript = ts.transpileModule(declaration.replace(/^export /, ''), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Handler = (request: unknown) => Promise<unknown>;
const bind = new Function('requireOperator', 'NextResponse', 'jobIdValid', 'prisma', 'activeJobs', javascript + '\nreturn POST;') as (...bindings: unknown[]) => Handler;

class PublicResponse {
  readonly body: unknown;
  readonly status: number;
  constructor(body: unknown, status: number) { this.body = body; this.status = status; }
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
type Options = {
  query?: unknown; body?: unknown; valid?: unknown; job?: unknown; controller?: unknown;
  faultAt?: string; fault?: unknown; denied?: boolean; authPromise?: Promise<unknown>;
  databasePromise?: Promise<unknown>; jsonRejection?: unknown; abortReturn?: unknown;
  response?: (body: unknown, options: unknown) => unknown;
};
function setup(options: Options = {}) {
  const events: string[] = [];
  const calls: { validation: unknown[][]; database: unknown[][]; active: unknown[][]; abort: unknown[][]; responses: unknown[][] } = { validation: [], database: [], active: [], abort: [], responses: [] };
  const sentinel = options.fault ?? Object.freeze({ publicFault: 'synthetic-only' });
  let thrown = false;
  function mark(name: string) {
    events.push(name);
    if (!thrown && options.faultAt === name) { thrown = true; throw sentinel; }
  }
  function prop(target: object, name: PropertyKey, stage: string, value: () => unknown) {
    Object.defineProperty(target, name, { configurable: true, get() { mark(stage); return value(); } });
  }
  const request = {}, url = {}, params = {}, prisma = {}, jobs = {}, active = {}, controller = {}, job = {};
  class Response extends PublicResponse {}
  prop(Response, Symbol.hasInstance, 'instance.get', () => function(this: unknown, value: unknown) {
    assert.equal(this, Response); mark('instance.call');
    return Function.prototype[Symbol.hasInstance].call(PublicResponse, value);
  });
  prop(Response, 'json', 'response.json.get', () => function(this: unknown, body: unknown, responseOptions: { status: number }) {
    assert.equal(this, Response); mark('response.json.call');
    calls.responses.push([body, responseOptions]);
    return options.response ? options.response(body, responseOptions) : new Response(body, responseOptions.status);
  });
  const denied = new Response({ publicDenial: true }, 403);
  const requireOperator = function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); assert.deepEqual(args, []); mark('auth.call');
    return options.authPromise ?? Promise.resolve(options.denied ? denied : { publicActor: 'operator-metadata' });
  };
  prop(request, 'nextUrl', 'request.nextUrl.get', () => url);
  prop(url, 'searchParams', 'url.searchParams.get', () => params);
  prop(params, 'get', 'params.get.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, params); assert.deepEqual(args, ['jobId']); mark('params.get.call');
    return Object.hasOwn(options, 'query') ? options.query : 'public-job';
  });
  const body = {};
  prop(body, 'jobId', 'body.jobId.get', () => 'public-body-job');
  prop(request, 'json', 'request.json.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, request); assert.deepEqual(args, []); mark('request.json.call');
    const value = Object.hasOwn(options, 'body') ? options.body : body;
    const carrier = {};
    prop(carrier, 'catch', 'json.catch.get', () => function(this: unknown, handler: (reason: unknown) => unknown) {
      assert.equal(this, carrier); assert.equal(arguments.length, 1); assert.equal(typeof handler, 'function'); mark('json.catch.call');
      if (Object.hasOwn(options, 'jsonRejection')) {
        return Promise.reject(options.jsonRejection).catch(reason => {
          mark('json.rejection.handler'); const result = handler(reason); assert.deepEqual(result, {}); return result;
        });
      }
      return Promise.resolve(value);
    });
    return carrier;
  });
  const jobIdValid = function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); mark('validator.call'); calls.validation.push(args);
    return Object.hasOwn(options, 'valid') ? options.valid : true;
  };
  prop(prisma, 'job', 'prisma.job.get', () => jobs);
  prop(jobs, 'findUnique', 'job.findUnique.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, jobs); mark('job.findUnique.call'); calls.database.push(args);
    return options.databasePromise ?? Promise.resolve(Object.hasOwn(options, 'job') ? options.job : job);
  });
  prop(job, 'status', 'job.status.get', () => 'running');
  Object.defineProperty(job, 'id', { get() { throw new Error('returned job.id must remain unread'); } });
  prop(active, 'get', 'active.get.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, active); mark('active.get.call'); calls.active.push(args);
    return Object.hasOwn(options, 'controller') ? options.controller : controller;
  });
  prop(controller, 'abort', 'controller.abort.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, controller); mark('controller.abort.call'); calls.abort.push(args); return options.abortReturn;
  });
  const handler = bind(requireOperator, Response, jobIdValid, prisma, active);
  return { handler, request, events, calls, sentinel, denied, Response, run: () => handler(request) };
}
function response(value: unknown, status: number, body: unknown) {
  assert.ok(value instanceof PublicResponse); assert.equal(value.status, status); assert.deepEqual(value.body, body);
}
const prefix = ['auth.call', 'instance.get', 'instance.call'];
const selection = ['request.nextUrl.get', 'url.searchParams.get', 'params.get.get', 'params.get.call'];
const database = ['validator.call', 'prisma.job.get', 'job.findUnique.get', 'job.findUnique.call'];
const cancellation = ['job.status.get', 'active.get.get', 'active.get.call', 'controller.abort.get', 'controller.abort.call'];
const reply = ['response.json.get', 'response.json.call'];

test('exact exported async declaration has one request parameter and synthetic bindings only', () => {
  const s = setup(); assert.equal(s.handler.length, 1); assert.equal(s.handler.constructor.name, 'AsyncFunction');
  assert.equal(node.parameters.length, 1); assert.equal(node.parameters[0].name.text, 'request');
  assert.ok(!javascript.includes('require(')); assert.deepEqual(s.events, []);
});
test('query success preserves exact member/call order, receivers, arguments, selected ID and202 metadata', async () => {
  const s = setup(); response(await s.run(), 202, { success: true, jobId: 'public-job', stopping: true });
  assert.deepEqual(s.events, [...prefix, ...selection, ...database, ...cancellation, ...reply]);
  assert.deepEqual(s.calls.validation, [['public-job']]);
  assert.deepEqual(s.calls.database, [[{ where: { id: 'public-job' }, select: { id: true, status: true } }]]);
  assert.deepEqual(s.calls.active, [['public-job']]); assert.deepEqual(s.calls.abort, [[]]);
  assert.deepEqual(s.calls.responses, [[{ success: true, jobId: 'public-job', stopping: true }, { status: 202 }]]);
});
test('authorization denial returns the identical response before any request access', async () => {
  const s = setup({ denied: true }); assert.equal(await s.run(), s.denied); assert.deepEqual(s.events, prefix);
});
for (const stage of ['auth.call', 'instance.get', 'instance.call']) {
  test('outside-try fault propagates exactly: ' + stage, async () => {
    const s = setup({ faultAt: stage }); await assert.rejects(s.run(), e => e === s.sentinel);
    assert.deepEqual(s.events, prefix.slice(0, prefix.indexOf(stage) + 1)); assert.deepEqual(s.calls.responses, []);
  });
}
test('authorization rejection propagates without entering instance or request checks', async () => {
  const gate = deferred(); const s = setup({ authPromise: gate.promise }); const result = s.run();
  assert.deepEqual(s.events, ['auth.call']); gate.reject(s.sentinel); await assert.rejects(result, e => e === s.sentinel);
  assert.deepEqual(s.events, ['auth.call']);
});
test('authorization await fences every later access', async () => {
  const gate = deferred(); const s = setup({ authPromise: gate.promise }); const result = s.run();
  assert.deepEqual(s.events, ['auth.call']); await Promise.resolve(); assert.deepEqual(s.events, ['auth.call']);
  gate.resolve({ publicActor: true }); response(await result, 202, { success: true, jobId: 'public-job', stopping: true });
});
for (const query of [null, undefined]) {
  test('nullish query uses JSON catch binding then selected body ID: ' + String(query), async () => {
    const s = setup({ query }); response(await s.run(), 202, { success: true, jobId: 'public-body-job', stopping: true });
    assert.deepEqual(s.events, [...prefix, ...selection, 'request.json.get', 'request.json.call', 'json.catch.get', 'json.catch.call', 'body.jobId.get', ...database, ...cancellation, ...reply]);
    assert.deepEqual(s.calls.validation, [['public-body-job']]); assert.deepEqual(s.calls.active, [['public-body-job']]);
  });
}
for (const [label, query] of [['empty-string', ''], ['false', false], ['zero', 0], ['object', Object.freeze({ publicSelection: true })], ['array', []]] as const) {
  test('nonnullish query bypasses JSON and passes selected metadata unchanged: ' + label, async () => {
    const s = setup({ query }); response(await s.run(), 202, { success: true, jobId: query, stopping: true });
    assert.deepEqual(s.calls.validation, [[query]]); assert.deepEqual(s.calls.active, [[query]]);
    assert.ok(!s.events.some(x => x.startsWith('request.json')));
  });
}
for (const valid of [false, undefined, null, 0, '']) {
  test('falsy synthetic validator refuses400 before ORM/cancellation: ' + String(valid), async () => {
    const s = setup({ valid }); response(await s.run(), 400, { error: 'Valid jobId is required' });
    assert.deepEqual(s.events, [...prefix, ...selection, 'validator.call', ...reply]);
    assert.deepEqual(s.calls.database, []); assert.deepEqual(s.calls.active, []);
  });
}
test('JSON rejection uses exact source catch callback empty-object result and cannot expose the fault', async () => {
  const s = setup({ query: null, valid: false, jsonRejection: { publicFault: 'json-refusal' } });
  response(await s.run(), 400, { error: 'Valid jobId is required' });
  assert.ok(s.events.includes('json.rejection.handler')); assert.deepEqual(s.calls.validation, [[undefined]]);
});
for (const body of [null, undefined]) {
  test('nullish JSON body property access is caught503: ' + String(body), async () => {
    const s = setup({ query: null, body }); response(await s.run(), 503, { error: 'Job cancellation unavailable' });
    assert.deepEqual(s.calls.validation, []); assert.deepEqual(s.calls.database, []);
  });
}
test('JSON catch result await fences validator and ORM', async () => {
  const gate = deferred(); const s = setup({ query: null, body: gate.promise }); const result = s.run();
  await Promise.resolve(); assert.ok(s.events.includes('json.catch.call')); assert.ok(!s.events.includes('validator.call'));
  gate.resolve({ jobId: 'public-later-body' }); response(await result, 202, { success: true, jobId: 'public-later-body', stopping: true });
});
test('findUnique await fences status, registry and abort', async () => {
  const gate = deferred(); const s = setup({ databasePromise: gate.promise }); const result = s.run();
  await Promise.resolve(); assert.deepEqual(s.events, [...prefix, ...selection, ...database]);
  gate.resolve({ id: 'different-returned-id', status: 'running' }); response(await result, 202, { success: true, jobId: 'public-job', stopping: true });
  assert.deepEqual(s.calls.active, [['public-job']]);
});
test('findUnique rejection is caught503 before any cancellation', async () => {
  const gate = deferred(); const s = setup({ databasePromise: gate.promise }); const result = s.run();
  await Promise.resolve(); gate.reject(s.sentinel); response(await result, 503, { error: 'Job cancellation unavailable' });
  assert.deepEqual(s.calls.active, []); assert.deepEqual(s.calls.abort, []);
});
for (const job of [null, undefined, false, 0]) {
  test('falsy synthetic job returns404 before registry: ' + String(job), async () => {
    const s = setup({ job }); response(await s.run(), 404, { error: 'Job not found' });
    assert.deepEqual(s.events, [...prefix, ...selection, ...database, ...reply]); assert.deepEqual(s.calls.active, []);
  });
}
for (const status of ['success', 'failed', '', undefined, Object('running')]) {
  test('strict non-running status returns409 before registry: ' + String(status), async () => {
    const s = setup({ job: { id: 'different-public-id', status } }); response(await s.run(), 409, { error: 'Job is already complete' });
    assert.deepEqual(s.calls.active, []); assert.deepEqual(s.calls.abort, []);
  });
}
for (const controller of [null, undefined, false, 0]) {
  test('falsy synthetic registry result returns fixed unowned409: ' + String(controller), async () => {
    const s = setup({ controller }); response(await s.run(), 409, { error: 'Job is not running in this process; inspect the operator runner' });
    assert.deepEqual(s.calls.active, [['public-job']]); assert.deepEqual(s.calls.abort, []);
  });
}
for (const stage of [...selection, ...database, ...cancellation, 'request.json.get', 'request.json.call', 'json.catch.get', 'json.catch.call', 'body.jobId.get', ...reply]) {
  test('inside-try immediate fault returns fixed503, without later effects: ' + stage, async () => {
    const fallback = stage.startsWith('request.json') || stage.startsWith('json.') || stage.startsWith('body.');
    const s = setup({ query: fallback ? null : 'public-job', faultAt: stage });
    response(await s.run(), 503, { error: 'Job cancellation unavailable' });
    assert.equal(s.events.filter(x => x === stage).length, stage.startsWith('response.') ? 2 : 1);
    const position = s.events.indexOf(stage); assert.deepEqual(s.events.slice(position + 1), reply);
  });
}
test('abort return is discarded without then inspection or awaiting', async () => {
  const result = {}; Object.defineProperty(result, 'then', { get() { throw new Error('abort return must stay unobserved'); } });
  const s = setup({ abortReturn: result }); response(await s.run(), 202, { success: true, jobId: 'public-job', stopping: true });
});
test('response Promise adoption succeeds without another response construction', async () => {
  const gate = deferred(); const s = setup({ response: () => gate.promise }); const result = s.run();
  await Promise.resolve(); await Promise.resolve(); assert.equal(s.calls.responses.length, 1);
  const value = new s.Response({ publicAdoption: true }, 202); gate.resolve(value); assert.equal(await result, value);
});
test('returned response rejection propagates without entering fixed503 catch', async () => {
  const gate = deferred(); const s = setup({ response: () => gate.promise }); const result = s.run();
  await Promise.resolve(); await Promise.resolve(); gate.reject(s.sentinel); await assert.rejects(result, e => e === s.sentinel);
  assert.equal(s.calls.responses.length, 1); assert.deepEqual(s.calls.responses[0][1], { status: 202 });
});
test('failure constructing the catch response propagates exactly', async () => {
  const fault = Object.freeze({ publicFault: 'response-construction' });
  const s = setup({ valid: false, response: () => { throw fault; } }); await assert.rejects(s.run(), e => e === fault);
  assert.deepEqual(s.calls.responses.map(x => x[1]), [{ status: 400 }, { status: 503 }]);
});
