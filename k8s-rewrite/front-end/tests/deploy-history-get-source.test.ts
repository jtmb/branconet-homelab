import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

// PUBLIC SOURCE only: no application import, initializer, neighbour or real service executes.
const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compiler, 'explicit current TypeScript input required');
const ts = createRequire(import.meta.url)(compiler);
const source = readFileSync(new URL('../src/app/api/deploy/history/route.ts', import.meta.url), 'utf8');
assert.equal(createHash('sha256').update(source).digest('hex'), '57536eb39d49b4427a05dabcc72c0a39a78bcce4b021a5b1ab57cfe0395cbf16');
const ast = ts.createSourceFile('selected-history-route.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const nodes = ast.statements.filter((n: { kind: number; name?: { text: string } }) => n.kind === ts.SyntaxKind.FunctionDeclaration && n.name?.text === 'GET');
assert.equal(nodes.length, 1);
const selected = nodes[0];
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.AsyncKeyword));
const declaration = source.slice(selected.getStart(ast), selected.end);
const javascript = ts.transpileModule(declaration.replace(/^export /, ''), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Handler = (request: unknown) => Promise<unknown>;
const factory = new Function('requireOperator', 'NextResponse', 'jobIdValid', 'readJobTail', 'prisma', 'Number', javascript + '\nreturn GET;') as (...args: unknown[]) => Handler;
class PublicResponse {
  readonly body: unknown;
  readonly options: { status?: number; headers?: Record<string, string> };
  constructor(body: unknown, options: { status?: number; headers?: Record<string, string> } = {}) { this.body = body; this.options = options; }
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
type Options = {
  id?: unknown; tail?: unknown; valid?: unknown; result?: unknown; jobs?: unknown;
  denied?: boolean; authPromise?: Promise<unknown>; tailPromise?: Promise<unknown>; listPromise?: Promise<unknown>;
  numeric?: unknown; integer?: unknown; faultAt?: string; faultOccurrence?: number;
  response?: (body: unknown, options: unknown, call: number) => unknown;
};
function setup(options: Options = {}) {
  const events: string[] = [];
  const calls: { auth: unknown[][]; valid: unknown[][]; number: unknown[][]; integer: unknown[][]; tail: unknown[][]; list: unknown[][]; responses: unknown[][] } = { auth: [], valid: [], number: [], integer: [], tail: [], list: [], responses: [] };
  const sentinel = Object.freeze({ publicFault: 'inert-binding-only' });
  const occurrences = new Map<string, number>();
  function mark(name: string) {
    events.push(name); const count = (occurrences.get(name) ?? 0) + 1; occurrences.set(name, count);
    if (options.faultAt === name && count === (options.faultOccurrence ?? 1)) throw sentinel;
  }
  function prop(target: object, name: PropertyKey, label: string, value: () => unknown) {
    Object.defineProperty(target, name, { configurable: true, get() { mark(label); return value(); } });
  }
  const request = {}, url = {}, params = {}, prisma = {}, job = {};
  class Response extends PublicResponse {}
  prop(Response, Symbol.hasInstance, 'instance.get', () => function(this: unknown, value: unknown) {
    assert.equal(this, Response); mark('instance.call'); return Function.prototype[Symbol.hasInstance].call(PublicResponse, value);
  });
  prop(Response, 'json', 'response.get', () => function(this: unknown, body: unknown, responseOptions: { status?: number; headers?: Record<string, string> }) {
    assert.equal(this, Response); mark('response.call'); calls.responses.push([body, responseOptions]);
    return options.response ? options.response(body, responseOptions, calls.responses.length) : new Response(body, responseOptions);
  });
  const denied = new Response({ publicDenial: true }, { status: 403 });
  const requireOperator = function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); mark('auth.call'); calls.auth.push(args);
    return options.authPromise ?? Promise.resolve(options.denied ? denied : { publicActor: true });
  };
  prop(request, 'nextUrl', 'request.nextUrl', () => url);
  prop(url, 'searchParams', 'url.searchParams', () => params);
  prop(params, 'get', 'params.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, params); assert.equal(args.length, 1); const name = args[0]; assert.ok(name === 'jobId' || name === 'tail'); mark('query.' + name);
    return name === 'jobId' ? (Object.hasOwn(options, 'id') ? options.id : 'public-job') : (Object.hasOwn(options, 'tail') ? options.tail : null);
  });
  const number = function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); mark('number.call'); calls.number.push(args);
    return Object.hasOwn(options, 'numeric') ? options.numeric : Number(args[0]);
  };
  prop(number, 'isInteger', 'integer.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, number); mark('integer.call'); calls.integer.push(args);
    return Object.hasOwn(options, 'integer') ? options.integer : Number.isInteger(args[0]);
  });
  const jobIdValid = function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); mark('valid.call'); calls.valid.push(args); return Object.hasOwn(options, 'valid') ? options.valid : true;
  };
  const result = Object.freeze({ publicTailMetadata: true });
  const jobs = Object.freeze([{ id: 'public-job', playbook: 'public.yml', status: 'success', startedAt: 'public-start', finishedAt: null }]);
  const readJobTail = function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); mark('tail.call'); calls.tail.push(args);
    return options.tailPromise ?? Promise.resolve(Object.hasOwn(options, 'result') ? options.result : result);
  };
  prop(prisma, 'job', 'prisma.job', () => job);
  prop(job, 'findMany', 'job.findMany.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, job); mark('job.findMany.call'); calls.list.push(args);
    return options.listPromise ?? Promise.resolve(Object.hasOwn(options, 'jobs') ? options.jobs : jobs);
  });
  const handler = factory(requireOperator, Response, jobIdValid, readJobTail, prisma, number);
  return { handler, request, run: () => handler(request), events, calls, sentinel, denied, result, jobs };
}
function response(value: unknown, status: number, body: unknown, headers?: Record<string, string>) {
  assert.ok(value instanceof PublicResponse); assert.equal(value.options.status ?? 200, status); assert.deepEqual(value.body, body); assert.deepEqual(value.options.headers, headers);
}
const selection = (name: string) => ['request.nextUrl', 'url.searchParams', 'params.get', 'query.' + name];
const auth = ['auth.call', 'instance.get', 'instance.call'];
const validity = ['number.call', 'valid.call', 'integer.get', 'integer.call'];
const reply = ['response.get', 'response.call'];
const list = ['prisma.job', 'job.findMany.get', 'job.findMany.call'];
const prefix = [...selection('jobId'), ...auth, ...selection('tail')];
const noStore = { 'Cache-Control': 'private, no-store' };
const invalid = { error: 'Valid jobId and tail from 1 to 65536 are required' };
const unavailable = { error: 'Job history unavailable' };

test('exact selected exported async GET only, one request argument and no application imports', () => {
  const s = setup(); assert.equal(s.handler.length, 1); assert.equal(s.handler.constructor.name, 'AsyncFunction');
  assert.equal(selected.parameters.length, 1); assert.equal(selected.parameters[0].name.text, 'request');
  assert.ok(!javascript.includes('require(')); assert.ok(!javascript.includes('DELETE')); assert.deepEqual(s.events, []);
});
test('null ID metadata selection has exact receiver, query, five fields and no tail or operator access', async () => {
  const s = setup({ id: null }); const result = await s.run(); response(result, 200, s.jobs, noStore);
  assert.deepEqual(s.events, [...selection('jobId'), ...list, ...reply]);
  assert.deepEqual(s.calls.list, [[{ orderBy: { startedAt: 'desc' }, take: 50, select: { id: true, playbook: true, status: true, startedAt: true, finishedAt: true } }]]);
  assert.deepEqual(s.calls.auth, []); assert.deepEqual(s.calls.valid, []); assert.deepEqual(s.calls.tail, []);
  assert.equal((result as PublicResponse).body, s.jobs);
});
test('explicit ID default tail preserves exact binding order, identity, arguments and no list access', async () => {
  const s = setup(); const result = await s.run(); response(result, 200, s.result, noStore);
  assert.deepEqual(s.events, [...prefix, ...validity, 'tail.call', ...reply]);
  assert.deepEqual(s.calls.auth, [[]]); assert.deepEqual(s.calls.number, [['65536']]); assert.deepEqual(s.calls.valid, [['public-job']]);
  assert.deepEqual(s.calls.integer, [[65536]]); assert.deepEqual(s.calls.tail, [['public-job', 65536]]); assert.deepEqual(s.calls.list, []);
  assert.equal((result as PublicResponse).body, s.result);
});
test('denial returns identical response after ID selection and before tail access', async () => {
  const s = setup({ denied: true }); assert.equal(await s.run(), s.denied); assert.deepEqual(s.events, [...selection('jobId'), ...auth]);
  assert.deepEqual(s.calls.responses, []); assert.deepEqual(s.calls.tail, []); assert.deepEqual(s.calls.list, []);
});
test('authorization await fences later tail, numeric, validator and lookup bindings', async () => {
  const gate = deferred(); const s = setup({ authPromise: gate.promise }); const pending = s.run();
  assert.deepEqual(s.events, [...selection('jobId'), 'auth.call']); await Promise.resolve(); assert.deepEqual(s.calls.number, []);
  gate.resolve({ publicActor: true }); response(await pending, 200, s.result, noStore);
});
for (const [label, id] of [['empty', ''], ['undefined-nondomain', undefined], ['false-nondomain', false], ['zero-nondomain', 0]] as const) {
  test('strict non-null ID selects operator path without truthiness fallback: ' + label, async () => {
    const s = setup({ id }); response(await s.run(), 200, s.result, noStore); assert.deepEqual(s.calls.valid, [[id]]); assert.deepEqual(s.calls.tail, [[id, 65536]]); assert.deepEqual(s.calls.list, []);
  });
}
for (const [label, tail, expected] of [['minimum', '1', 1], ['maximum', '65536', 65536], ['five-digits', '65535', 65535], ['leading-zero', '00001', 1], ['null-default', null, 65536], ['undefined-default-nondomain', undefined, 65536]] as const) {
  test('tail selection boundary: ' + label, async () => {
    const s = setup({ tail }); response(await s.run(), 200, s.result, noStore); assert.deepEqual(s.calls.tail, [['public-job', expected]]);
    assert.deepEqual(s.calls.number, [[tail ?? '65536']]);
  });
}
for (const tail of ['', '0', '00000', '65537', '99999', '100000', '-1', '+1', '1.0', '1e1', ' 1', '1 ', '１２', 'NaN', 'Infinity']) {
  test('invalid public tail refuses before selected lookup: ' + JSON.stringify(tail), async () => {
    const s = setup({ tail }); response(await s.run(), 400, invalid); assert.deepEqual(s.calls.tail, []); assert.deepEqual(s.calls.list, []);
    assert.deepEqual(s.calls.number, [[tail]]); assert.deepEqual(s.calls.valid, [['public-job']]);
    assert.equal(s.calls.integer.length, /^\d{1,5}$/.test(tail) ? 1 : 0);
  });
}
test('literal regex rejects final newline before integer validation', async () => {
  const s = setup({ tail: '1\n' }); response(await s.run(), 400, invalid);
  assert.deepEqual(s.calls.number, [['1\n']]); assert.deepEqual(s.calls.valid, [['public-job']]);
  assert.deepEqual(s.calls.integer, []); assert.deepEqual(s.calls.tail, []);
});
test('invalid job ID shortcircuits regex and integer checks after numeric conversion', async () => {
  const s = setup({ valid: false, tail: '1' }); response(await s.run(), 400, invalid);
  assert.deepEqual(s.events, [...prefix, 'number.call', 'valid.call', ...reply]); assert.deepEqual(s.calls.tail, []);
});
for (const numeric of [NaN, Infinity, 1.5, 0, 65537]) {
  test('synthetic immediate Number result exercises integer and range refusal: ' + String(numeric), async () => {
    const s = setup({ tail: '1', numeric }); response(await s.run(), 400, invalid); assert.deepEqual(s.calls.integer, [[numeric]]); assert.deepEqual(s.calls.tail, []);
  });
}
for (const result of [null, undefined, false, 0, '']) {
  test('falsy synthetic tail result is fixed404: ' + String(result), async () => {
    const s = setup({ result }); response(await s.run(), 404, { error: 'Job not found' }); assert.deepEqual(s.calls.tail, [['public-job', 65536]]);
  });
}
test('selected tail await fences response construction and preserves resolved result identity', async () => {
  const gate = deferred(); const s = setup({ tailPromise: gate.promise }); const pending = s.run(); await Promise.resolve();
  assert.deepEqual(s.events, [...prefix, ...validity, 'tail.call']); assert.deepEqual(s.calls.responses, []);
  gate.resolve(s.result); const result = await pending; response(result, 200, s.result, noStore); assert.equal((result as PublicResponse).body, s.result);
});
test('metadata list await fences response construction', async () => {
  const gate = deferred(); const s = setup({ id: null, listPromise: gate.promise }); const pending = s.run();
  assert.deepEqual(s.events, [...selection('jobId'), ...list]); assert.deepEqual(s.calls.responses, []);
  gate.resolve(s.jobs); response(await pending, 200, s.jobs, noStore);
});
for (const lane of ['auth', 'tail', 'list'] as const) {
  test('awaited ' + lane + ' rejection becomes fixed503 without leaking the rejection', async () => {
    const gate = deferred(); const options: Options = lane === 'auth' ? { authPromise: gate.promise } : lane === 'tail' ? { tailPromise: gate.promise } : { id: null, listPromise: gate.promise };
    const s = setup(options); const pending = s.run(); await Promise.resolve(); gate.reject(s.sentinel); response(await pending, 503, unavailable);
    assert.deepEqual(s.calls.responses, [[unavailable, { status: 503 }]]);
  });
}
for (const lane of ['tail', 'list'] as const) {
  const stages = lane === 'tail' ? [...selection('jobId'), ...auth, ...selection('tail'), ...validity, 'tail.call', ...reply] : [...selection('jobId'), ...list, ...reply];
  const seen = new Map<string, number>();
  for (let index = 0; index < stages.length; index++) {
    const stage = stages[index]; const occurrence = (seen.get(stage) ?? 0) + 1; seen.set(stage, occurrence);
    test('one-shot ' + lane + ' binding fault becomes fixed503 at ' + stage + '#' + occurrence, async () => {
      const s = setup({ ...(lane === 'list' ? { id: null } : {}), faultAt: stage, faultOccurrence: occurrence }); response(await s.run(), 503, unavailable);
      assert.deepEqual(s.events, [...stages.slice(0, index + 1), ...reply]);
      assert.deepEqual(s.calls.responses.at(-1), [unavailable, { status: 503 }]);
    });
  }
}
test('synchronous success-response failure is caught but catch-response failure propagates', async () => {
  const fault = Object.freeze({ publicResponseFault: true }); const s = setup({ response() { throw fault; } });
  await assert.rejects(s.run(), error => error === fault); assert.equal(s.calls.responses.length, 2); assert.deepEqual(s.calls.responses[1], [unavailable, { status: 503 }]);
});
for (const lane of ['tail', 'list', 'invalid', 'missing'] as const) {
  test('unawaited ' + lane + ' response rejection is adopted outside catch', async () => {
    const gate = deferred(); const options: Options = lane === 'list' ? { id: null } : lane === 'invalid' ? { valid: false } : lane === 'missing' ? { result: null } : {};
    const s = setup({ ...options, response: () => gate.promise }); const pending = s.run(); await Promise.resolve(); await Promise.resolve();
    assert.equal(s.calls.responses.length, 1); gate.reject(s.sentinel); await assert.rejects(pending, error => error === s.sentinel); assert.equal(s.calls.responses.length, 1);
  });
}
test('catch-response Promise rejection propagates without a second catch attempt', async () => {
  const gate = deferred(); const s = setup({ faultAt: 'number.call', response: () => gate.promise }); const pending = s.run(); await Promise.resolve();
  assert.deepEqual(s.calls.responses, [[unavailable, { status: 503 }]]); gate.reject(s.sentinel); await assert.rejects(pending, error => error === s.sentinel); assert.equal(s.calls.responses.length, 1);
});
