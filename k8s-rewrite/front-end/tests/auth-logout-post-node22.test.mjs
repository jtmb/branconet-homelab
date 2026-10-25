import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

// Distinct supported PUBLIC projection. Never import the route or historical test.
const ts = createRequire(import.meta.url)('typescript');
assert.equal(process.version, 'v22.23.3'); assert.equal(ts.version, '5.9.3');
const raw = readFileSync(new URL('../src/app/api/auth/logout/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
const digest = value => createHash('sha256').update(value).digest('hex');
assert.equal(digest(source), '82b68003458beed4b2c108eb86c6cde08d2c11306cb03b740d330564499f9702');
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'cad0a4a6a0fae32e57c75a68c0d855cb2f86873866fe8f1338c06591e17ea4b4');
const ast = ts.createSourceFile('selected-logout.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
assert.equal(ast.parseDiagnostics.length, 0);
const nodes = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'POST');
assert.equal(nodes.length, 1);
for (const kind of [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword])
  assert.equal(nodes[0].modifiers.filter(modifier => modifier.kind === kind).length, 1);
const selected = nodes[0].getText(ast);
assert.equal(selected, `export async function POST() {
  const response = NextResponse.json({ success: true });
  response.cookies.set(AUTH_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}`);
const emitted = ts.transpileModule(selected.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(emitted.diagnostics.length, 0);
// Same-realm async semantics preserve native Promise/TypeError identity. Only the
// pinned declaration executes, with these three synthetic immediate bindings.
const bind = new Function('NextResponse', 'AUTH_COOKIE', 'process', '"use strict";\n' + emitted.outputText + '\nreturn POST;');
const order = ['json.get', 'json.call', 'response.cookies', 'set.get', 'process.env', 'env.NODE_ENV', 'set.call', 'response.then'];
function fixture(input = {}) {
  const events = [], json = [], writes = [], refusal = Object.freeze({ publicFault: true });
  const next = {}, response = {}, cookies = {}, processBinding = {}, environment = {};
  const value = (key, fallback) => Object.hasOwn(input, key) ? input[key] : fallback;
  function mark(event) { events.push(event); if (value('fault', undefined) === event) throw refusal; }
  function getter(target, key, event, read) {
    Object.defineProperty(target, key, { get() { mark(event); return read(); } });
  }
  getter(next, 'json', 'json.get', () => function(...args) {
    assert.equal(this, next); mark('json.call'); json.push(args); return value('jsonResult', response);
  });
  getter(response, 'cookies', 'response.cookies', () => cookies);
  getter(cookies, 'set', 'set.get', () => function(...args) {
    assert.equal(this, cookies); mark('set.call'); writes.push(args); return value('setResult', cookies);
  });
  getter(processBinding, 'env', 'process.env', () => environment);
  getter(environment, 'NODE_ENV', 'env.NODE_ENV', () => value('env', 'test'));
  getter(response, 'then', 'response.then', () => value('responseThen', undefined));
  const cookie = value('cookie', 'public_auth_cookie');
  const post = bind(next, cookie, processBinding);
  return { invoke: () => post(), events, json, writes, refusal, response, cookie };
}
function argumentsMatch(f, secure = false) {
  assert.deepEqual(f.json, [[{ success: true }]]);
  assert.deepEqual(f.writes, [[f.cookie, '', { httpOnly: true, secure, sameSite: 'lax', path: '/', maxAge: 0 }]]);
  assert.deepEqual(Object.keys(f.writes[0][2]), ['httpOnly', 'secure', 'sameSite', 'path', 'maxAge']);
}
let count = 0;
const control = (label, run) => test(`L${String(++count).padStart(2, '0')} ${label}`, run);
control('success keeps the response, exact arguments, method receivers and full read order', async () => {
  const f = fixture(); assert.equal(await f.invoke(), f.response); argumentsMatch(f); assert.deepEqual(f.events, order);
});
const environments = [
  ['production', 'production', true], ['development', 'development', false], ['test', 'test', false],
  ['undefined', undefined, false], ['null', null, false], ['boolean', true, false], ['number', 1, false],
  ['uppercase', 'PRODUCTION', false], ['surrounding spaces', ' production ', false], ['empty', '', false],
  ['boxed production', Object('production'), false],
  ['noncoercible object', { [Symbol.toPrimitive]() { throw new Error('must not coerce'); } }, false],
];
for (const [label, env, secure] of environments) control(`strict production equality: ${label}`, async () => {
  const f = fixture({ env }); assert.equal(await f.invoke(), f.response); argumentsMatch(f, secure); assert.deepEqual(f.events, order);
});
for (const fault of order.slice(0, -1)) control(`immediate fault stops once at ${fault}`, async () => {
  const f = fixture({ fault }); const pending = f.invoke(); assert.ok(pending instanceof Promise);
  await assert.rejects(pending, error => error === f.refusal);
  assert.deepEqual(f.events, order.slice(0, order.indexOf(fault) + 1));
  assert.ok(f.json.length <= 1 && f.writes.length <= 1);
});
control('response then getter rejects after the completed cookie write', async () => {
  const f = fixture({ fault: 'response.then' }); await assert.rejects(f.invoke(), error => error === f.refusal);
  argumentsMatch(f); assert.deepEqual(f.events, order);
});
control('opaque cookie binding reaches set with its identity and no coercion', async () => {
  const cookie = Object.freeze({ [Symbol.toPrimitive]() { throw new Error('must not coerce'); } });
  const f = fixture({ cookie }); assert.equal(await f.invoke(), f.response); assert.equal(f.writes[0][0], cookie); argumentsMatch(f);
});
control('setter result then getter is never inspected', async () => {
  const setResult = Object.defineProperty({}, 'then', { get() { throw new Error('setter result inspected'); } });
  const f = fixture({ setResult }); assert.equal(await f.invoke(), f.response); argumentsMatch(f); assert.deepEqual(f.events, order);
});
control('unresolved setter promise does not hold the response', async () => {
  const f = fixture({ setResult: new Promise(() => {}) }); assert.equal(await f.invoke(), f.response); argumentsMatch(f);
});
control('noncallable response then preserves response identity', async () => {
  const f = fixture({ responseThen: 1 }); assert.equal(await f.invoke(), f.response); argumentsMatch(f);
});
control('async return adopts the response thenable only after set', async () => {
  const result = Object.freeze({ publicResponse: true }); let release;
  const gate = new Promise(resolve => { release = resolve; });
  const f = fixture({ responseThen: function(resolve) {
    assert.equal(this, f.response); assert.equal(f.writes.length, 1); f.events.push('then.call'); gate.then(resolve);
  } });
  let settled = false; const pending = f.invoke().finally(() => { settled = true; });
  await Promise.resolve(); await Promise.resolve(); assert.equal(settled, false);
  assert.deepEqual(f.events, [...order, 'then.call']); release(result); assert.equal(await pending, result); argumentsMatch(f);
});
control('response thenable rejection preserves the fault and single response', async () => {
  const f = fixture({ responseThen: function(resolve, reject) {
    assert.equal(typeof resolve, 'function'); assert.equal(this, f.response); assert.equal(f.writes.length, 1); reject(f.refusal);
  } });
  await assert.rejects(f.invoke(), error => error === f.refusal); argumentsMatch(f); assert.deepEqual(f.events, order);
});
control('null JSON result rejects before environment reads or set', async () => {
  const f = fixture({ jsonResult: null }); await assert.rejects(f.invoke(), TypeError);
  assert.deepEqual(f.events, ['json.get', 'json.call']); assert.equal(f.writes.length, 0);
});
control('JSON promise is used immediately without awaiting its cookies', async () => {
  const f = fixture({ jsonResult: Promise.resolve({ cookies: {} }) }); await assert.rejects(f.invoke(), TypeError);
  assert.deepEqual(f.events, ['json.get', 'json.call']); assert.equal(f.writes.length, 0);
});
control('repeated invocations create equal but separate success and option objects', async () => {
  const f = fixture(); await f.invoke(); await f.invoke(); assert.deepEqual(f.events, [...order, ...order]);
  assert.equal(f.json.length, 2); assert.equal(f.writes.length, 2);
  assert.notEqual(f.json[0][0], f.json[1][0]); assert.notEqual(f.writes[0][2], f.writes[1][2]);
  assert.deepEqual(f.json[0], f.json[1]); assert.deepEqual(f.writes[0], f.writes[1]);
});
assert.equal(count, 30);
