import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

// Distinct supported PUBLIC declaration projection. Never import the route or
// historical test; imports, schema initialization and all real callees stay inert.
const ts = createRequire(import.meta.url)('typescript');
assert.equal(process.version, 'v22.23.3'); assert.equal(ts.version, '5.9.3');
const raw = readFileSync(new URL('../src/app/api/auth/register/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
const digest = value => createHash('sha256').update(value).digest('hex');
assert.equal(digest(source), 'f0a7cf3f7d7fa5e6d42c60dcb65fd99ea95e7eb4d4c236d3ee8a4894d9c85d68');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '78249c3be01fdce79b7ed65dac24107f19e10ef8b4967b3a32c6a7e82bcd47d0');
const ast = ts.createSourceFile('selected-register.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
assert.equal(ast.parseDiagnostics.length, 0);
const nodes = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'POST');
assert.equal(nodes.length, 1);
for (const kind of [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword])
  assert.equal(nodes[0].modifiers.filter(modifier => modifier.kind === kind).length, 1);
const selected = nodes[0].getText(ast);
assert.equal(selected, `export async function POST(req: Request) {
  try {
    await ensureJwtSecret();

    // First-user-only gate unless ALLOW_REGISTRATION is explicitly "true"
    // or the DB setting allow_registration is "true"
    if (!await accounts.registrationOpen()) {
      return NextResponse.json(
        { error: "Registration is locked. Set ALLOW_REGISTRATION=true to enable." },
        { status: 403 }
      );
    }

    const body = await req.json();
    const parsed = registerSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: parsed.error.issues[0]?.message ?? "Invalid input" },
        { status: 400 }
      );
    }

    const { username, password } = parsed.data;

    const passwordHash = await bcrypt.hash(password, 12);
    const user = await accounts.register({ username, passwordHash });
    const token = await signJWT({ sub: user.id, username: user.username, sessionVersion: user.sessionVersion });

    const response = NextResponse.json(
      { id: user.id, username: user.username },
      { status: 201 }
    );

    response.cookies.set(AUTH_COOKIE, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return response;
  } catch (err) {
    return accountFailure(err);
  }
}`);
const emitted = ts.transpileModule(selected.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(emitted.diagnostics.length, 0);
// Same-realm async return/await semantics preserve native exception identity.
const bind = new Function('ensureJwtSecret', 'accounts', 'registerSchema', 'bcrypt', 'signJWT',
  'NextResponse', 'AUTH_COOKIE', 'process', 'accountFailure', '"use strict";\n' + emitted.outputText + '\nreturn POST;');
const order = ['ensure:call', 'accounts.registrationOpen:get', 'accounts.registrationOpen:call',
  'req.json:get', 'req.json:call', 'schema.safeParse:get', 'schema.safeParse:call', 'parsed.success',
  'parsed.data', 'data.username', 'data.password', 'bcrypt.hash:get', 'bcrypt.hash:call',
  'accounts.register:get', 'accounts.register:call', 'user.id', 'user.username', 'user.sessionVersion',
  'sign:call', 'json:get', 'user.id', 'user.username', 'json:call', 'response.cookies', 'cookies.set:get',
  'process.env', 'env.NODE_ENV', 'cookies.set:call'];
function fixture(input = {}) {
  const events = [], calls = Object.fromEntries(['open', 'parse', 'hash', 'register', 'sign', 'json', 'set', 'failures'].map(key => [key, []]));
  const value = (key, fallback) => Object.hasOwn(input, key) ? input[key] : fallback;
  const fault = Object.freeze({ publicFault: 'registration-source' });
  const body = Object.freeze({ publicBody: 'synthetic-registration' });
  const cookie = Object.freeze({ publicCookieName: 'inert' });
  const hash = value('hash', Object.freeze({ publicHash: 'placeholder' }));
  const token = value('token', Object.freeze({ publicToken: 'placeholder' }));
  function mark(event) { events.push(event); if (input.faultAt === event) throw fault; }
  function settle(event, result) { mark(event); return input.rejectAt === event ? Promise.reject(fault) : result; }
  function getter(target, key, event, read) {
    Object.defineProperty(target, key, { get() { mark(event); return read(); }, configurable: true });
  }
  const data = {}, parsed = {}, user = {}, accounts = {}, schema = {}, bcrypt = {}, next = {}, req = {}, cookies = {}, env = {}, processBinding = {};
  getter(data, 'username', 'data.username', () => 'public-user');
  getter(data, 'password', 'data.password', () => 'public-password');
  getter(parsed, 'success', 'parsed.success', () => !input.invalid);
  getter(parsed, 'data', 'parsed.data', () => data);
  getter(parsed, 'error', 'parsed.error', () => ({ issues: value('issues', [{ message: 'public-invalid' }]) }));
  getter(user, 'id', 'user.id', () => 'public-id');
  getter(user, 'username', 'user.username', () => 'public-canonical-user');
  getter(user, 'sessionVersion', 'user.sessionVersion', () => 3);
  getter(accounts, 'registrationOpen', 'accounts.registrationOpen:get', () => function(...args) {
    assert.equal(this, accounts); calls.open.push(args);
    return settle('accounts.registrationOpen:call', value('openResult', value('open', true)));
  });
  getter(accounts, 'register', 'accounts.register:get', () => function(...args) {
    assert.equal(this, accounts); calls.register.push(args);
    return settle('accounts.register:call', value('registerResult', value('user', user)));
  });
  getter(schema, 'safeParse', 'schema.safeParse:get', () => function(...args) {
    mark('schema.safeParse:call'); assert.equal(this, schema); calls.parse.push(args); return value('parseResult', parsed);
  });
  getter(bcrypt, 'hash', 'bcrypt.hash:get', () => function(...args) {
    assert.equal(this, bcrypt); calls.hash.push(args); return settle('bcrypt.hash:call', value('hashResult', hash));
  });
  const response = input.response ?? { publicResponse: 'created' };
  const branchResponse = input.branchResponse ?? { publicResponse: 'refused' };
  const failureResponse = value('failureResponse', { publicResponse: 'account-failure' });
  getter(response, 'cookies', 'response.cookies', () => cookies);
  getter(cookies, 'set', 'cookies.set:get', () => function(...args) {
    mark('cookies.set:call'); assert.equal(this, cookies); calls.set.push(args); return input.setterReturn;
  });
  getter(next, 'json', 'json:get', () => function(...args) {
    mark('json:call'); assert.equal(this, next); calls.json.push(args); return args[1].status === 201 ? response : branchResponse;
  });
  getter(req, 'json', 'req.json:get', () => function(...args) {
    assert.equal(this, req); assert.deepEqual(args, []); return settle('req.json:call', value('bodyResult', body));
  });
  getter(env, 'NODE_ENV', 'env.NODE_ENV', () => value('env', 'test'));
  getter(processBinding, 'env', 'process.env', () => env);
  const ensure = () => settle('ensure:call', input.ensureResult);
  const sign = (...args) => { calls.sign.push(args); return settle('sign:call', value('signResult', token)); };
  const failure = (...args) => { mark('accountFailure:call'); calls.failures.push(args); if (input.failureThrows) throw fault; return failureResponse; };
  const post = bind(ensure, accounts, schema, bcrypt, sign, next, cookie, processBinding, failure);
  return { post, req, events, calls, fault, body, cookie, hash, token, user, response, branchResponse, failureResponse };
}
let count = 0;
const control = (label, run) => test(`R${String(++count).padStart(2, '0')} ${label}`, run);
control('success preserves order, receivers, payloads, status201 and cookie option keys', async () => {
  const f = fixture(); assert.equal(await f.post(f.req), f.response); assert.deepEqual(f.events, order);
  assert.deepEqual(f.calls.open, [[]]); assert.deepEqual(f.calls.parse, [[f.body]]);
  assert.deepEqual(f.calls.hash, [['public-password', 12]]);
  assert.deepEqual(f.calls.register, [[{ username: 'public-user', passwordHash: f.hash }]]);
  assert.deepEqual(f.calls.sign, [[{ sub: 'public-id', username: 'public-canonical-user', sessionVersion: 3 }]]);
  assert.deepEqual(f.calls.json, [[{ id: 'public-id', username: 'public-canonical-user' }, { status: 201 }]]);
  assert.deepEqual(f.calls.set, [[f.cookie, f.token, { httpOnly: true, secure: false, sameSite: 'lax', path: '/', maxAge: 604800 }]]);
  assert.deepEqual(Object.keys(f.calls.set[0][2]), ['httpOnly', 'secure', 'sameSite', 'path', 'maxAge']);
  assert.deepEqual(f.calls.failures, []);
});
for (const open of [undefined, null, false, 0, '']) control(`falsy gate stops before body: ${String(open)}`, async () => {
  const f = fixture({ open }); assert.equal(await f.post(f.req), f.branchResponse);
  assert.deepEqual(f.events, ['ensure:call', 'accounts.registrationOpen:get', 'accounts.registrationOpen:call', 'json:get', 'json:call']);
  assert.deepEqual(f.calls.json, [[{ error: 'Registration is locked. Set ALLOW_REGISTRATION=true to enable.' }, { status: 403 }]]);
  for (const key of ['parse', 'hash', 'register', 'sign', 'set', 'failures']) assert.equal(f.calls[key].length, 0);
});
control('truthy PUBLIC gate characterizes declaration only', async () => {
  const f = fixture({ open: { publicGate: 'truthy' } }); assert.equal(await f.post(f.req), f.response);
});
for (const faultAt of new Set(order)) control(`immediate fault delegates exact identity once: ${faultAt}`, async () => {
  const f = fixture({ faultAt }); assert.equal(await f.post(f.req), f.failureResponse);
  assert.deepEqual(f.calls.failures, [[f.fault]]);
  assert.deepEqual(f.events, [...order.slice(0, order.indexOf(faultAt) + 1), 'accountFailure:call']);
});
for (const rejectAt of ['ensure:call', 'accounts.registrationOpen:call', 'req.json:call', 'bcrypt.hash:call', 'accounts.register:call', 'sign:call'])
  control(`await rejection delegates once: ${rejectAt}`, async () => {
    const f = fixture({ rejectAt }); assert.equal(await f.post(f.req), f.failureResponse);
    assert.deepEqual(f.calls.failures, [[f.fault]]); assert.equal(f.calls.set.length, 0);
  });
for (const issues of [[{ message: 'public-invalid' }], [], [{}], [{ message: null }], [{ message: undefined }], [{ message: '' }], [{ message: 0 }], [{ message: false }]])
  control(`invalid schema preserves nullish-only message: ${JSON.stringify(issues)}`, async () => {
    const f = fixture({ invalid: true, issues }); assert.equal(await f.post(f.req), f.branchResponse);
    assert.deepEqual(f.calls.json, [[{ error: issues[0]?.message ?? 'Invalid input' }, { status: 400 }]]);
    for (const key of ['hash', 'register', 'sign', 'set', 'failures']) assert.equal(f.calls[key].length, 0);
  });
for (const issues of [null, undefined]) control(`malformed issues delegates failure: ${String(issues)}`, async () => {
  const f = fixture({ invalid: true, issues }); assert.equal(await f.post(f.req), f.failureResponse);
  assert.equal(f.calls.failures.length, 1); assert.equal(f.calls.hash.length, 0);
});
control('synchronous parser result thenable stays unread', async () => {
  let touched = false;
  const f = fixture({ parseResult: { get then() { touched = true; throw new Error('unread'); } } });
  assert.equal(await f.post(f.req), f.failureResponse); assert.equal(touched, false); assert.equal(f.calls.failures.length, 1);
});
control('null parse result fails before hashing', async () => {
  const f = fixture({ parseResult: null }); assert.equal(await f.post(f.req), f.failureResponse);
  assert.equal(f.calls.hash.length, 0); assert.equal(f.calls.failures.length, 1);
});
control('null registered user fails after register and before signing', async () => {
  const f = fixture({ user: null }); assert.equal(await f.post(f.req), f.failureResponse);
  assert.equal(f.calls.register.length, 1); assert.equal(f.calls.sign.length, 0); assert.equal(f.calls.failures.length, 1);
});
for (const env of ['production', 'Production', ' production', undefined, null, 0, true, {}, Object('production')])
  control(`strict production equality: ${String(env)}`, async () => {
    const f = fixture({ env }); await f.post(f.req); assert.equal(f.calls.set[0][2].secure, env === 'production');
  });
control('setter thenable is ignored and argument objects are fresh on repeated invocation', async () => {
  let touched = false;
  const setterReturn = Object.defineProperty({}, 'then', { get() { touched = true; throw new Error('unread setter result'); } });
  const f = fixture({ setterReturn }); await f.post(f.req); await f.post(f.req); assert.equal(touched, false);
  for (const group of [f.calls.register, f.calls.sign, f.calls.json]) assert.notEqual(group[0][0], group[1][0]);
  assert.notEqual(f.calls.json[0][1], f.calls.json[1][1]); assert.notEqual(f.calls.set[0][2], f.calls.set[1][2]);
});
for (const hold of ['ensure', 'open', 'body', 'hash', 'register', 'sign']) control(`await settlement fences downstream work: ${hold}`, async () => {
  let release; const held = new Promise(resolve => { release = resolve; });
  const key = { ensure: 'ensureResult', open: 'openResult', body: 'bodyResult', hash: 'hashResult', register: 'registerResult', sign: 'signResult' }[hold];
  const f = fixture({ [key]: held }); const pending = f.post(f.req);
  for (let i = 0; i < 10; i++) await Promise.resolve();
  const marker = { ensure: 'ensure:call', open: 'accounts.registrationOpen:call', body: 'req.json:call', hash: 'bcrypt.hash:call', register: 'accounts.register:call', sign: 'sign:call' }[hold];
  assert.deepEqual(f.events, order.slice(0, order.indexOf(marker) + 1)); assert.ok(release);
  release({ ensure: undefined, open: true, body: f.body, hash: f.hash, register: f.user, sign: f.token }[hold]);
  assert.equal(await pending, f.response); assert.deepEqual(f.calls.failures, []);
});
control('body result exact identity reaches synchronous parser', async () => {
  const bodyResult = { publicBody: 'alternate' }; const f = fixture({ bodyResult });
  await f.post(f.req); assert.equal(f.calls.parse[0][0], bodyResult);
});
control('hash and sign results preserve exact synthetic identity', async () => {
  const hash = { publicHash: 'alternate' }, token = { publicToken: 'alternate' }; const f = fixture({ hash, token });
  await f.post(f.req); assert.equal(f.calls.register[0][0].passwordHash, hash); assert.equal(f.calls.set[0][1], token);
});
for (const branch of ['success', 'locked', 'invalid', 'catch']) control(`return assimilation failure bypasses try catch: ${branch}`, async () => {
  const marker = { publicFault: 'return-assimilation' };
  const response = Object.defineProperty({}, 'then', { get() { throw marker; } });
  const f = fixture(branch === 'success' ? { response } : branch === 'locked' ? { open: false, branchResponse: response }
    : branch === 'invalid' ? { invalid: true, branchResponse: response } : { rejectAt: 'ensure:call', failureResponse: response });
  await assert.rejects(f.post(f.req), error => error === marker);
  assert.equal(f.calls.failures.length, branch === 'catch' ? 1 : 0); assert.equal(f.calls.set.length, branch === 'success' ? 1 : 0);
});
control('accountFailure synchronous throw propagates without retry', async () => {
  const f = fixture({ rejectAt: 'ensure:call', failureThrows: true }); await assert.rejects(f.post(f.req), error => error === f.fault);
  assert.equal(f.calls.failures.length, 1); assert.equal(f.calls.json.length, 0);
});
control('accountFailure rejected promise propagates without retry', async () => {
  const marker = { publicFault: 'failure-result' };
  const f = fixture({ rejectAt: 'ensure:call', failureResponse: Promise.reject(marker) });
  await assert.rejects(f.post(f.req), error => error === marker); assert.equal(f.calls.failures.length, 1);
});
control('accountFailure thenable settles as async return value', async () => {
  const result = { publicResult: 'failure-value' };
  const f = fixture({ rejectAt: 'ensure:call', failureResponse: { then(resolve) { resolve(result); } } });
  assert.equal(await f.post(f.req), result); assert.equal(f.calls.failures.length, 1);
});
control('success thenable settles only after cookie call', async () => {
  const result = { publicResult: 'created' };
  const f = fixture({ response: { then(resolve) { assert.equal(f.calls.set.length, 1); resolve(result); } } });
  assert.equal(await f.post(f.req), result); assert.equal(f.calls.failures.length, 0);
});
assert.equal(count, 78);
