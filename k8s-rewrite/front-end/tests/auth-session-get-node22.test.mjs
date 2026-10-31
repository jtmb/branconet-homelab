import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

// Distinct supported PUBLIC declaration projection. Historical86/packaging1
// remain frozen. No route module/import/initializer or real callee executes.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const raw = readFileSync(new URL('../src/app/api/auth/session/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
const digest = value => createHash('sha256').update(value).digest('hex');
assert.equal(digest(source), '0fa65aaa70406f438168c8560f921dc524b13d1fc33b767c354babaff29db945');
assert.equal(digest(source.replaceAll('\n', '\r\n')), '2c13e5bbb98075487dfca2ecf4691d3f94e3076f6d178e8a44d0b18752d4002d');
const ast = ts.createSourceFile('selected-session.ts', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
assert.equal(ast.parseDiagnostics.length, 0);
const nodes = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'GET');
assert.equal(nodes.length, 1);
for (const kind of [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword])
  assert.equal(nodes[0].modifiers.filter(modifier => modifier.kind === kind).length, 1);
const selected = nodes[0].getText(ast);
assert.equal(selected, `export async function GET() {
  try {
    await ensureJwtSecret();

    const user = await getSessionAccount();
    const userCount = await prisma.user.count();

    let registrationOpen = userCount === 0 || process.env.ALLOW_REGISTRATION === "true";
    if (!registrationOpen) {
      const dbSetting = await prisma.appSetting.findUnique({
        where: { key: "allow_registration" },
      });
      if (dbSetting?.value === "true") registrationOpen = true;
    }

    if (user) {
      return NextResponse.json({
        authenticated: true,
        username: user.username,
        role: user.role,
        engineAdmin: user.role === "write" && user.engineAdmin,
        hasUsers: userCount > 0,
        registrationOpen,
        capabilities: runtimeCapabilities(),
      });
    }

    return NextResponse.json({
      authenticated: false,
      hasUsers: userCount > 0,
      registrationOpen,
      capabilities: runtimeCapabilities(),
    });
  } catch (err) {
    return NextResponse.json(
      { authenticated: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}`);
const emitted = ts.transpileModule(selected.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(emitted.diagnostics.length, 0);
// Same-realm async/await preserves receiver and response rejection semantics.
const factory = new Function('ensureJwtSecret', 'getSessionAccount', 'prisma', 'process', 'NextResponse', 'runtimeCapabilities',
  '"use strict";\n' + emitted.outputText + '\nreturn GET;');
class PublicResponse {
  constructor(body, options = {}) { this.body = body; this.options = options; }
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function setup(o = {}) {
  const events = [];
  const calls = { ready: [], account: [], count: [], setting: [], caps: [], responses: [] };
  const sentinel = Object.freeze({ publicFault: true });
  const seen = new Map();
  const own = (key, fallback) => Object.hasOwn(o, key) ? o[key] : fallback;
  function mark(name) {
    events.push(name); const count = (seen.get(name) ?? 0) + 1; seen.set(name, count);
    if (o.faultAt === name && count === (o.faultOccurrence ?? 1)) throw sentinel;
  }
  function prop(target, key, event, value) {
    Object.defineProperty(target, key, { get() { mark(event); return value(); } });
  }
  const user = {}, prisma = {}, users = {}, settings = {}, proc = {}, env = {}, setting = {}, response = {};
  prop(user, 'username', 'user.username', () => own('username', 'public-account'));
  let roleReads = 0;
  prop(user, 'role', 'user.role', () => o.roles ? o.roles[roleReads++] : own('role', 'write'));
  prop(user, 'engineAdmin', 'user.admin', () => own('admin', true));
  prop(prisma, 'user', 'prisma.user', () => users);
  prop(users, 'count', 'count.get', () => function(...args) {
    assert.equal(this, users); mark('count.call'); calls.count.push(args);
    return o.countPromise ?? Promise.resolve(own('count', 1));
  });
  prop(prisma, 'appSetting', 'prisma.setting', () => settings);
  prop(settings, 'findUnique', 'setting.get', () => function(...args) {
    assert.equal(this, settings); mark('setting.call'); calls.setting.push(args);
    return o.settingPromise ?? Promise.resolve(own('setting', setting));
  });
  prop(setting, 'value', 'setting.value', () => own('value', 'false'));
  prop(proc, 'env', 'process.env', () => env);
  prop(env, 'ALLOW_REGISTRATION', 'env.registration', () => own('env', 'false'));
  const ready = function(...args) { assert.equal(this, undefined); mark('ready.call'); calls.ready.push(args); return o.readyPromise ?? Promise.resolve(); };
  const account = function(...args) { assert.equal(this, undefined); mark('account.call'); calls.account.push(args); return o.accountPromise ?? Promise.resolve(own('user', user)); };
  const caps = function(...args) { assert.equal(this, undefined); mark('caps.call'); calls.caps.push(args); return own('capabilities', { publicCapability: true }); };
  prop(response, 'json', 'response.get', () => function(...args) {
    assert.equal(this, response); mark('response.call'); calls.responses.push(args);
    return o.response ? o.response(args[0], args[1], calls.responses.length) : new PublicResponse(args[0], args[1]);
  });
  const handler = factory(ready, account, prisma, proc, response, caps);
  return { run: () => handler(), events, calls, sentinel, user, setting };
}
const base = ['ready.call', 'account.call', 'prisma.user', 'count.get', 'count.call'];
const environment = ['process.env', 'env.registration'];
const setting = ['prisma.setting', 'setting.get', 'setting.call', 'setting.value'];
const memberFields = ['user.username', 'user.role', 'user.role', 'user.admin'];
const failure = { authenticated: false, error: 'Internal server error' };
function reply(value, status, body) {
  assert.ok(value instanceof PublicResponse);
  assert.equal(value.options.status ?? 200, status); assert.deepEqual(value.body, body);
}
const body = (registrationOpen = false, hasUsers = true) => ({ authenticated: true, username: 'public-account', role: 'write', engineAdmin: true, hasUsers, registrationOpen, capabilities: { publicCapability: true } });
async function flush() { for (let i = 0; i < 16; i++) await Promise.resolve(); }
let count = 0;
const control = (label, run) => test(`S${String(++count).padStart(2, '0')} ${label}`, run);

control('complete authenticated source order, receivers and arguments', async () => {
  const s = setup(); reply(await s.run(), 200, body());
  assert.deepEqual(s.events, [...base, ...environment, ...setting, 'response.get', ...memberFields, 'caps.call', 'response.call']);
  for (const key of ['ready', 'account', 'count', 'caps']) assert.deepEqual(s.calls[key], [[]]);
  assert.deepEqual(s.calls.setting, [[{ where: { key: 'allow_registration' } }]]);
  assert.equal(s.calls.responses[0].length, 1);
});
control('zero users short-circuits every environment and setting member', async () => {
  const s = setup({ count: 0, faultAt: 'process.env' }); reply(await s.run(), 200, body(true, false));
  assert.deepEqual(s.events, [...base, 'response.get', ...memberFields, 'caps.call', 'response.call']);
});
control('exact environment true skips setting members', async () => {
  const s = setup({ env: 'true', faultAt: 'prisma.setting' }); reply(await s.run(), 200, body(true));
  assert.deepEqual(s.events, [...base, ...environment, 'response.get', ...memberFields, 'caps.call', 'response.call']);
});
for (const value of [undefined, null, '', 'TRUE', 'True', 'false', '1', true, false, 1]) {
  control('environment uses strict string true: ' + String(value), async () => {
    const s = setup({ env: value, value: 'true' }); reply(await s.run(), 200, body(true));
    assert.equal(s.calls.setting.length, 1);
  });
}
for (const value of [undefined, null, '', 'TRUE', 'false', true, false, 1]) {
  control('setting uses strict string true: ' + String(value), async () => {
    const s = setup({ value }); reply(await s.run(), 200, body(false)); assert.equal(s.calls.setting.length, 1);
  });
}
for (const value of [null, undefined]) {
  control('nullish setting omits value access: ' + String(value), async () => {
    const s = setup({ setting: value }); reply(await s.run(), 200, body()); assert.ok(!s.events.includes('setting.value'));
  });
}
for (const value of [null, undefined, false, 0, '']) {
  control('falsy session uses anonymous metadata without account fields: ' + String(value), async () => {
    const s = setup({ user: value }); reply(await s.run(), 200, { authenticated: false, hasUsers: true, registrationOpen: false, capabilities: { publicCapability: true } });
    assert.deepEqual(s.events, [...base, ...environment, ...setting, 'response.get', 'caps.call', 'response.call']);
  });
}
for (const role of ['readonly', 'WRITE', '', undefined, null, false]) {
  control('non-write role short-circuits engineAdmin: ' + String(role), async () => {
    const s = setup({ role, faultAt: 'user.admin' });
    reply(await s.run(), 200, { ...body(), role, engineAdmin: false });
    assert.equal(s.events.filter(event => event === 'user.role').length, 2); assert.ok(!s.events.includes('user.admin'));
  });
}
for (const admin of [false, undefined, null, 0, '', true, 'public-admin-marker']) {
  control('write role preserves raw engineAdmin conjunction result: ' + String(admin), async () => {
    const s = setup({ admin }); reply(await s.run(), 200, { ...body(), engineAdmin: admin });
  });
}
control('role is read independently for role and engineAdmin', async () => {
  const s = setup({ roles: ['readonly', 'write'] }); reply(await s.run(), 200, { ...body(), role: 'readonly', engineAdmin: true });
});
control('second role read can short-circuit admin after initial write', async () => {
  const s = setup({ roles: ['write', 'readonly'], faultAt: 'user.admin' }); reply(await s.run(), 200, { ...body(), engineAdmin: false });
});
for (const count of [-1, 2, '0', '2', null, undefined, false]) {
  control('strict empty-count and ordinary hasUsers comparison: ' + String(count), async () => {
    const s = setup({ count }); reply(await s.run(), 200, body(false, count > 0)); assert.equal(s.calls.setting.length, 1);
  });
}
control('hasUsers comparison occurs after account members and before capabilities', async () => {
  const coercions = []; const count = { [Symbol.toPrimitive](hint) { coercions.push(hint); return 2; } };
  const s = setup({ count, capabilities: null }); const result = await s.run();
  reply(result, 200, { ...body(), capabilities: null }); assert.deepEqual(coercions, ['number']); assert.equal(s.calls.setting.length, 1);
});
for (const stage of ['ready', 'account', 'count', 'setting']) {
  control('await fence: ' + stage, async () => {
    const hold = deferred(); const opts = { [stage + 'Promise']: hold.promise };
    const s = setup(opts); let settled = false; const promise = s.run().finally(() => { settled = true; });
    await flush();
    const expected = stage === 'ready' ? ['ready.call'] : stage === 'account' ? base.slice(0, 2) : stage === 'count' ? base : [...base, ...environment, ...setting.slice(0, 3)];
    assert.deepEqual(s.events, expected); assert.equal(settled, false);
    hold.resolve(stage === 'account' ? null : stage === 'count' ? 1 : stage === 'setting' ? null : undefined);
    await promise; assert.equal(settled, true);
  });
  control('awaited rejection becomes fixed500: ' + stage, async () => {
    const hold = deferred(); const s = setup({ [stage + 'Promise']: hold.promise });
    const promise = s.run(); await flush(); hold.reject(s.sentinel); reply(await promise, 500, failure);
  });
}
for (const faultAt of [...base, ...environment, ...setting, 'response.get', 'user.username', 'user.role', 'user.admin', 'caps.call', 'response.call']) {
  control('synchronous immediate fault becomes fixed500: ' + faultAt, async () => {
    const s = setup({ faultAt }); reply(await s.run(), 500, failure);
    assert.deepEqual(s.calls.responses.at(-1), [failure, { status: 500 }]);
  });
}
control('second role getter fault is caught before capabilities', async () => {
  const s = setup({ faultAt: 'user.role', faultOccurrence: 2 }); reply(await s.run(), 500, failure); assert.equal(s.calls.caps.length, 0);
});
control('hasUsers coercion fault is caught before capabilities', async () => {
  const sentinel = { publicFault: 'comparison' };
  const s = setup({ count: { [Symbol.toPrimitive]() { throw sentinel; } } }); reply(await s.run(), 500, failure); assert.equal(s.calls.caps.length, 0);
});
control('capability metadata is forwarded unchanged', async () => {
  const capabilities = Object.freeze({ provisioning: false, operatorShell: false, podExec: false });
  const s = setup({ capabilities }); const result = await s.run(); assert.ok(result instanceof PublicResponse); assert.equal(result.body.capabilities, capabilities);
});
control('response identity is retained', async () => {
  const response = Object.freeze({ publicResponse: true }); const s = setup({ response: () => response }); assert.equal(await s.run(), response);
});
control('returned response promise is adopted without another response', async () => {
  const hold = deferred(); const s = setup({ response: () => hold.promise }); let done = false;
  const promise = s.run().finally(() => { done = true; }); await flush(); assert.equal(done, false);
  const response = { publicResponse: true }; hold.resolve(response); assert.equal(await promise, response); assert.equal(s.calls.responses.length, 1);
});
control('returned success response rejection bypasses catch', async () => {
  const hold = deferred(); const s = setup({ response: () => hold.promise }); const promise = s.run(); await flush(); hold.reject(s.sentinel);
  await assert.rejects(promise, error => error === s.sentinel); assert.equal(s.calls.responses.length, 1);
});
control('catch response getter failure propagates', async () => {
  const hold = deferred(); const s = setup({ readyPromise: hold.promise, faultAt: 'response.get' });
  const promise = s.run(); hold.reject({ publicFault: 'readiness' }); await assert.rejects(promise, error => error === s.sentinel);
});
control('catch response call failure propagates', async () => {
  const hold = deferred(); const s = setup({ readyPromise: hold.promise, faultAt: 'response.call' });
  const promise = s.run(); hold.reject({ publicFault: 'readiness' }); await assert.rejects(promise, error => error === s.sentinel);
});
control('catch response promise rejection propagates', async () => {
  const ready = deferred(), response = deferred(); const s = setup({ readyPromise: ready.promise, response: () => response.promise });
  const promise = s.run(); ready.reject({ publicFault: 'readiness' }); await flush(); response.reject(s.sentinel);
  await assert.rejects(promise, error => error === s.sentinel); assert.equal(s.calls.responses.length, 1);
});
control('fresh invocation re-reads every immediate binding', async () => {
  const s = setup(); reply(await s.run(), 200, body()); reply(await s.run(), 200, body());
  for (const key of ['ready', 'account', 'count', 'setting', 'caps']) assert.equal(s.calls[key].length, 2);
});
assert.equal(count, 86);
