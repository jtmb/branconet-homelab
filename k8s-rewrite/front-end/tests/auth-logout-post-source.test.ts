import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

// Exact PUBLIC declaration only; all imported application modules stay inert.
assert.equal(process.version, 'v24.18.0');
const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compiler);
const ts = createRequire(import.meta.url)(compiler);
const source = readFileSync(new URL('../src/app/api/auth/logout/route.ts', import.meta.url), 'utf8');
assert.equal(createHash('sha256').update(source).digest('hex'), 'cad0a4a6a0fae32e57c75a68c0d855cb2f86873866fe8f1338c06591e17ea4b4');
const ast = ts.createSourceFile('selected-logout.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const nodes = ast.statements.filter((n: { kind: number; name?: { text: string } }) => n.kind === ts.SyntaxKind.FunctionDeclaration && n.name?.text === 'POST');
assert.equal(nodes.length, 1);
const selected = nodes[0];
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.AsyncKeyword));
const declaration = source.slice(selected.getStart(ast), selected.end);
const js = ts.transpileModule(declaration.replace(/^export /, ''), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
const factory = new Function('NextResponse', 'AUTH_COOKIE', 'process', js + '\nreturn POST;') as (...args: unknown[]) => () => Promise<unknown>;
type Options = { env?: unknown; cookie?: unknown; faultAt?: string; jsonResult?: unknown; setResult?: unknown; responseThen?: unknown };
function setup(o: Options = {}) {
  const events: string[] = [], jsonCalls: unknown[][] = [], setCalls: unknown[][] = [];
  const sentinel = Object.freeze({ publicFault: true });
  const own = (key: keyof Options, fallback: unknown) => Object.hasOwn(o, key) ? o[key] : fallback;
  function mark(event: string) { events.push(event); if (o.faultAt === event) throw sentinel; }
  function prop(target: object, key: string, event: string, get: () => unknown) {
    Object.defineProperty(target, key, { get() { mark(event); return get(); } });
  }
  const next = {}, response = {}, cookies = {}, proc = {}, env = {};
  prop(next, 'json', 'json.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, next); mark('json.call'); jsonCalls.push(args); return own('jsonResult', response);
  });
  prop(response, 'cookies', 'response.cookies', () => cookies);
  prop(cookies, 'set', 'set.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, cookies); mark('set.call'); setCalls.push(args); return own('setResult', cookies);
  });
  prop(proc, 'env', 'process.env', () => env);
  prop(env, 'NODE_ENV', 'env.NODE_ENV', () => own('env', 'test'));
  prop(response, 'then', 'response.then', () => own('responseThen', undefined));
  const cookie = own('cookie', 'public_auth_cookie');
  const handler = factory(next, cookie, proc);
  return { run: () => handler(), events, jsonCalls, setCalls, sentinel, response, cookies, cookie };
}
const order = ['json.get', 'json.call', 'response.cookies', 'set.get', 'process.env', 'env.NODE_ENV', 'set.call', 'response.then'];
const options = (secure: boolean) => ({ httpOnly: true, secure, sameSite: 'lax', path: '/', maxAge: 0 });
function cookieCall(s: ReturnType<typeof setup>, secure = false) {
  assert.deepEqual(s.jsonCalls, [[{ success: true }]]);
  assert.deepEqual(s.setCalls, [[s.cookie, '', options(secure)]]);
  assert.deepEqual(Object.keys(s.setCalls[0][2] as object), ['httpOnly', 'secure', 'sameSite', 'path', 'maxAge']);
}
test('complete success order, argument shapes, receivers and response identity', async () => {
  const s = setup(); assert.equal(await s.run(), s.response); assert.deepEqual(s.events, order); cookieCall(s);
});
const environments: [string, unknown, boolean][] = [
  ['production', 'production', true], ['development', 'development', false], ['test', 'test', false],
  ['missing', undefined, false], ['null', null, false], ['true', true, false], ['one', 1, false],
  ['uppercase', 'PRODUCTION', false], ['whitespace', ' production ', false], ['empty', '', false],
  ['boxed string', Object('production'), false], ['noncoercible object', { [Symbol.toPrimitive]() { throw new Error('must not coerce'); } }, false],
];
for (const [name, env, secure] of environments) test('strict environment comparison: ' + name, async () => {
  const s = setup({ env }); assert.equal(await s.run(), s.response); cookieCall(s, secure); assert.deepEqual(s.events, order);
});
for (const faultAt of order.slice(0, -1)) test('synchronous fault rejects without retry: ' + faultAt, async () => {
  const s = setup({ faultAt }); const promise = s.run(); assert.ok(promise instanceof Promise);
  await assert.rejects(promise, error => error === s.sentinel);
  assert.deepEqual(s.events, order.slice(0, order.indexOf(faultAt) + 1));
  assert.ok(s.jsonCalls.length <= 1 && s.setCalls.length <= 1);
});
test('return then getter fault occurs after cookie write and propagates', async () => {
  const s = setup({ faultAt: 'response.then' }); await assert.rejects(s.run(), error => error === s.sentinel);
  assert.deepEqual(s.events, order); cookieCall(s);
});
test('cookie binding is forwarded without coercion', async () => {
  const cookie = Object.freeze({ [Symbol.toPrimitive]() { throw new Error('must not coerce'); } });
  const s = setup({ cookie }); assert.equal(await s.run(), s.response); assert.equal(s.setCalls[0][0], cookie); cookieCall(s);
});
test('setter return thenable is ignored without inspection or await', async () => {
  const ignored = Object.defineProperty({}, 'then', { get() { throw new Error('setter result inspected'); } });
  const s = setup({ setResult: ignored }); assert.equal(await s.run(), s.response); cookieCall(s); assert.deepEqual(s.events, order);
});
test('setter unresolved promise does not delay the response', async () => {
  const s = setup({ setResult: new Promise(() => {}) }); assert.equal(await s.run(), s.response); cookieCall(s);
});
test('noncallable response then field preserves original response', async () => {
  const s = setup({ responseThen: 1 }); assert.equal(await s.run(), s.response); cookieCall(s);
});
test('returned response thenable is adopted only after cookie write', async () => {
  const result = Object.freeze({ publicResponse: true }); let release!: (v: unknown) => void;
  const gate = new Promise<unknown>(resolve => { release = resolve; });
  const s = setup({ responseThen: function(this: unknown, resolve: (v: unknown) => void) {
    assert.equal(this, s.response); assert.equal(s.setCalls.length, 1); s.events.push('then.call'); gate.then(resolve);
  } });
  let settled = false; const pending = s.run().finally(() => { settled = true; });
  await Promise.resolve(); await Promise.resolve(); assert.equal(settled, false);
  assert.deepEqual(s.events, [...order, 'then.call']); release(result); assert.equal(await pending, result); cookieCall(s);
});
test('returned response thenable rejection propagates without a second response', async () => {
  const s = setup({ responseThen: function(this: unknown, resolve: unknown, reject: (v: unknown) => void) {
    assert.equal(typeof resolve, 'function'); assert.equal(this, s.response); assert.equal(s.setCalls.length, 1); reject(s.sentinel);
  } });
  await assert.rejects(s.run(), error => error === s.sentinel); cookieCall(s); assert.deepEqual(s.events, order);
});
test('null json result rejects before environment and set', async () => {
  const s = setup({ jsonResult: null }); await assert.rejects(s.run(), TypeError); assert.deepEqual(s.events, ['json.get', 'json.call']);
  assert.equal(s.setCalls.length, 0);
});
test('promise json result is not awaited before cookies member access', async () => {
  const s = setup({ jsonResult: Promise.resolve({ cookies: {} }) }); await assert.rejects(s.run(), TypeError);
  assert.deepEqual(s.events, ['json.get', 'json.call']); assert.equal(s.setCalls.length, 0);
});
test('fresh invocation creates fresh success and cookie options objects', async () => {
  const s = setup(); await s.run(); await s.run(); assert.deepEqual(s.events, [...order, ...order]);
  assert.equal(s.jsonCalls.length, 2); assert.equal(s.setCalls.length, 2);
  assert.notEqual(s.jsonCalls[0][0], s.jsonCalls[1][0]); assert.notEqual(s.setCalls[0][2], s.setCalls[1][2]);
  assert.deepEqual(s.jsonCalls[0], s.jsonCalls[1]); assert.deepEqual(s.setCalls[0], s.setCalls[1]);
});
