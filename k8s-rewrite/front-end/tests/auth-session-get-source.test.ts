import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

// PUBLIC SOURCE only. No application module or real authentication/database runs.
assert.equal(process.version, 'v24.18.0');
const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compiler);
const ts = createRequire(import.meta.url)(compiler);
const source = readFileSync(new URL('../src/app/api/auth/session/route.ts', import.meta.url), 'utf8');
assert.equal(createHash('sha256').update(source).digest('hex'), '2c13e5bbb98075487dfca2ecf4691d3f94e3076f6d178e8a44d0b18752d4002d');
const ast = ts.createSourceFile('selected-session.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const nodes = ast.statements.filter((n: { kind: number; name?: { text: string } }) => n.kind === ts.SyntaxKind.FunctionDeclaration && n.name?.text === 'GET');
assert.equal(nodes.length, 1);
const selected = nodes[0];
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.AsyncKeyword));
const declaration = source.slice(selected.getStart(ast), selected.end);
const js = ts.transpileModule(declaration.replace(/^export /, ''), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Handler = () => Promise<unknown>;
const factory = new Function('ensureJwtSecret', 'getSessionAccount', 'prisma', 'process', 'NextResponse', 'runtimeCapabilities', js + '\nreturn GET;') as (...args: unknown[]) => Handler;
class PublicResponse {
  readonly body: unknown;
  readonly options: { status?: number };
  constructor(body: unknown, options: { status?: number } = {}) { this.body = body; this.options = options; }
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
type Options = {
  user?: unknown; count?: unknown; env?: unknown; setting?: unknown; value?: unknown;
  role?: unknown; roles?: unknown[]; username?: unknown; admin?: unknown; capabilities?: unknown;
  readyPromise?: Promise<unknown>; accountPromise?: Promise<unknown>; countPromise?: Promise<unknown>; settingPromise?: Promise<unknown>;
  faultAt?: string; faultOccurrence?: number; response?: (body: unknown, options: unknown, call: number) => unknown;
};
function setup(o: Options = {}) {
  const events: string[] = [];
  const calls: Record<'ready' | 'account' | 'count' | 'setting' | 'caps' | 'responses', unknown[][]> = { ready: [], account: [], count: [], setting: [], caps: [], responses: [] };
  const sentinel = Object.freeze({ publicFault: true });
  const seen = new Map<string, number>();
  const own = (k: keyof Options, fallback: unknown) => Object.hasOwn(o, k) ? o[k] : fallback;
  function mark(n: string) {
    events.push(n); const count = (seen.get(n) ?? 0) + 1; seen.set(n, count);
    if (o.faultAt === n && count === (o.faultOccurrence ?? 1)) throw sentinel;
  }
  function prop(target: object, key: string, event: string, value: () => unknown) {
    Object.defineProperty(target, key, { get() { mark(event); return value(); } });
  }
  const user = {}, prisma = {}, users = {}, settings = {}, proc = {}, env = {}, setting = {}, response = {};
  prop(user, 'username', 'user.username', () => own('username', 'public-account'));
  let roleReads = 0;
  prop(user, 'role', 'user.role', () => o.roles ? o.roles[roleReads++] : own('role', 'write'));
  prop(user, 'engineAdmin', 'user.admin', () => own('admin', true));
  prop(prisma, 'user', 'prisma.user', () => users);
  prop(users, 'count', 'count.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, users); mark('count.call'); calls.count.push(args);
    return o.countPromise ?? Promise.resolve(own('count', 1));
  });
  prop(prisma, 'appSetting', 'prisma.setting', () => settings);
  prop(settings, 'findUnique', 'setting.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, settings); mark('setting.call'); calls.setting.push(args);
    return o.settingPromise ?? Promise.resolve(own('setting', setting));
  });
  prop(setting, 'value', 'setting.value', () => own('value', 'false'));
  prop(proc, 'env', 'process.env', () => env);
  prop(env, 'ALLOW_REGISTRATION', 'env.registration', () => own('env', 'false'));
  const ready = function(this: unknown, ...args: unknown[]) { assert.equal(this, undefined); mark('ready.call'); calls.ready.push(args); return o.readyPromise ?? Promise.resolve(); };
  const account = function(this: unknown, ...args: unknown[]) { assert.equal(this, undefined); mark('account.call'); calls.account.push(args); return o.accountPromise ?? Promise.resolve(own('user', user)); };
  const caps = function(this: unknown, ...args: unknown[]) { assert.equal(this, undefined); mark('caps.call'); calls.caps.push(args); return own('capabilities', { publicCapability: true }); };
  prop(response, 'json', 'response.get', () => function(this: unknown, ...args: unknown[]) {
    assert.equal(this, response); mark('response.call'); calls.responses.push(args);
    return o.response ? o.response(args[0], args[1], calls.responses.length) : new PublicResponse(args[0], args[1] as { status?: number } | undefined);
  });
  const handler = factory(ready, account, prisma, proc, response, caps);
  return { run: () => handler(), events, calls, sentinel, user, setting };
}
const base = ['ready.call', 'account.call', 'prisma.user', 'count.get', 'count.call'];
const environment = ['process.env', 'env.registration'];
const setting = ['prisma.setting', 'setting.get', 'setting.call', 'setting.value'];
const memberFields = ['user.username', 'user.role', 'user.role', 'user.admin'];
const failure = { authenticated: false, error: 'Internal server error' };
function reply(value: unknown, status: number, body: unknown) {
  assert.ok(value instanceof PublicResponse);
  assert.equal(value.options.status ?? 200, status); assert.deepEqual(value.body, body);
}
const body = (registrationOpen = false, hasUsers = true) => ({ authenticated: true, username: 'public-account', role: 'write', engineAdmin: true, hasUsers, registrationOpen, capabilities: { publicCapability: true } });
async function flush() { for (let i = 0; i < 16; i++) await Promise.resolve(); }

test('complete authenticated source order, receivers and arguments', async () => {
  const s = setup(); reply(await s.run(), 200, body());
  assert.deepEqual(s.events, [...base, ...environment, ...setting, 'response.get', ...memberFields, 'caps.call', 'response.call']);
  for (const k of ['ready', 'account', 'count', 'caps'] as const) assert.deepEqual(s.calls[k], [[]]);
  assert.deepEqual(s.calls.setting, [[{ where: { key: 'allow_registration' } }]]);
  assert.equal(s.calls.responses[0].length, 1);
});
test('zero users short-circuits every environment and setting member', async () => {
  const s = setup({ count: 0, faultAt: 'process.env' }); reply(await s.run(), 200, body(true, false));
  assert.deepEqual(s.events, [...base, 'response.get', ...memberFields, 'caps.call', 'response.call']);
});
test('exact environment true skips setting members', async () => {
  const s = setup({ env: 'true', faultAt: 'prisma.setting' }); reply(await s.run(), 200, body(true));
  assert.deepEqual(s.events, [...base, ...environment, 'response.get', ...memberFields, 'caps.call', 'response.call']);
});
for (const value of [undefined, null, '', 'TRUE', 'True', 'false', '1', true, false, 1]) {
  test('environment uses strict string true: ' + String(value), async () => {
    const s = setup({ env: value, value: 'true' }); reply(await s.run(), 200, body(true));
    assert.equal(s.calls.setting.length, 1);
  });
}
for (const value of [undefined, null, '', 'TRUE', 'false', true, false, 1]) {
  test('setting uses strict string true: ' + String(value), async () => {
    const s = setup({ value }); reply(await s.run(), 200, body(false)); assert.equal(s.calls.setting.length, 1);
  });
}
for (const value of [null, undefined]) {
  test('nullish setting omits value access: ' + String(value), async () => {
    const s = setup({ setting: value }); reply(await s.run(), 200, body()); assert.ok(!s.events.includes('setting.value'));
  });
}
for (const value of [null, undefined, false, 0, '']) {
  test('falsy session uses anonymous metadata without account fields: ' + String(value), async () => {
    const s = setup({ user: value }); reply(await s.run(), 200, { authenticated: false, hasUsers: true, registrationOpen: false, capabilities: { publicCapability: true } });
    assert.deepEqual(s.events, [...base, ...environment, ...setting, 'response.get', 'caps.call', 'response.call']);
  });
}
for (const role of ['readonly', 'WRITE', '', undefined, null, false]) {
  test('non-write role short-circuits engineAdmin: ' + String(role), async () => {
    const s = setup({ role, faultAt: 'user.admin' });
    reply(await s.run(), 200, { ...body(), role, engineAdmin: false });
    assert.equal(s.events.filter(x => x === 'user.role').length, 2); assert.ok(!s.events.includes('user.admin'));
  });
}
for (const admin of [false, undefined, null, 0, '', true, 'public-admin-marker']) {
  test('write role preserves raw engineAdmin conjunction result: ' + String(admin), async () => {
    const s = setup({ admin }); reply(await s.run(), 200, { ...body(), engineAdmin: admin });
  });
}
test('role is read independently for role and engineAdmin', async () => {
  const s = setup({ roles: ['readonly', 'write'] }); reply(await s.run(), 200, { ...body(), role: 'readonly', engineAdmin: true });
});
test('second role read can short-circuit admin after initial write', async () => {
  const s = setup({ roles: ['write', 'readonly'], faultAt: 'user.admin' }); reply(await s.run(), 200, { ...body(), engineAdmin: false });
});
for (const count of [-1, 2, '0', '2', null, undefined, false]) {
  test('strict empty-count and ordinary hasUsers comparison: ' + String(count), async () => {
    const s = setup({ count }); reply(await s.run(), 200, body(false, (count as number) > 0)); assert.equal(s.calls.setting.length, 1);
  });
}
test('hasUsers comparison occurs after account members and before capabilities', async () => {
  const coercions: string[] = []; const count = { [Symbol.toPrimitive](hint: string) { coercions.push(hint); return 2; } };
  const s = setup({ count, capabilities: null }); const result = await s.run();
  reply(result, 200, { ...body(), capabilities: null }); assert.deepEqual(coercions, ['number']); assert.equal(s.calls.setting.length, 1);
});
for (const stage of ['ready', 'account', 'count', 'setting'] as const) {
  test('await fence: ' + stage, async () => {
    const hold = deferred(); const opts = { [stage + 'Promise']: hold.promise } as Options;
    const s = setup(opts); let settled = false; const promise = s.run().finally(() => { settled = true; });
    await flush();
    const expected = stage === 'ready' ? ['ready.call'] : stage === 'account' ? base.slice(0, 2) : stage === 'count' ? base : [...base, ...environment, ...setting.slice(0, 3)];
    assert.deepEqual(s.events, expected); assert.equal(settled, false);
    hold.resolve(stage === 'account' ? null : stage === 'count' ? 1 : stage === 'setting' ? null : undefined);
    await promise; assert.equal(settled, true);
  });
  test('awaited rejection becomes fixed500: ' + stage, async () => {
    const hold = deferred(); const s = setup({ [stage + 'Promise']: hold.promise } as Options);
    const promise = s.run(); await flush(); hold.reject(s.sentinel); reply(await promise, 500, failure);
  });
}
for (const faultAt of [...base, ...environment, ...setting, 'response.get', 'user.username', 'user.role', 'user.admin', 'caps.call', 'response.call']) {
  test('synchronous immediate fault becomes fixed500: ' + faultAt, async () => {
    const s = setup({ faultAt }); reply(await s.run(), 500, failure);
    assert.deepEqual(s.calls.responses.at(-1), [failure, { status: 500 }]);
  });
}
test('second role getter fault is caught before capabilities', async () => {
  const s = setup({ faultAt: 'user.role', faultOccurrence: 2 }); reply(await s.run(), 500, failure); assert.equal(s.calls.caps.length, 0);
});
test('hasUsers coercion fault is caught before capabilities', async () => {
  const sentinel = { publicFault: 'comparison' };
  const s = setup({ count: { [Symbol.toPrimitive]() { throw sentinel; } } }); reply(await s.run(), 500, failure); assert.equal(s.calls.caps.length, 0);
});
test('capability metadata is forwarded unchanged', async () => {
  const capabilities = Object.freeze({ provisioning: false, operatorShell: false, podExec: false });
  const s = setup({ capabilities }); const result = await s.run(); assert.ok(result instanceof PublicResponse); assert.equal((result.body as { capabilities: unknown }).capabilities, capabilities);
});
test('response identity is retained', async () => {
  const response = Object.freeze({ publicResponse: true }); const s = setup({ response: () => response }); assert.equal(await s.run(), response);
});
test('returned response promise is adopted without another response', async () => {
  const hold = deferred(); const s = setup({ response: () => hold.promise }); let done = false;
  const promise = s.run().finally(() => { done = true; }); await flush(); assert.equal(done, false);
  const response = { publicResponse: true }; hold.resolve(response); assert.equal(await promise, response); assert.equal(s.calls.responses.length, 1);
});
test('returned success response rejection bypasses catch', async () => {
  const hold = deferred(); const s = setup({ response: () => hold.promise }); const promise = s.run(); await flush(); hold.reject(s.sentinel);
  await assert.rejects(promise, e => e === s.sentinel); assert.equal(s.calls.responses.length, 1);
});
test('catch response getter failure propagates', async () => {
  const hold = deferred(); const s = setup({ readyPromise: hold.promise, faultAt: 'response.get' });
  const promise = s.run(); hold.reject({ publicFault: 'readiness' }); await assert.rejects(promise, e => e === s.sentinel);
});
test('catch response call failure propagates', async () => {
  const hold = deferred(); const s = setup({ readyPromise: hold.promise, faultAt: 'response.call' });
  const promise = s.run(); hold.reject({ publicFault: 'readiness' }); await assert.rejects(promise, e => e === s.sentinel);
});
test('catch response promise rejection propagates', async () => {
  const ready = deferred(), response = deferred(); const s = setup({ readyPromise: ready.promise, response: () => response.promise });
  const promise = s.run(); ready.reject({ publicFault: 'readiness' }); await flush(); response.reject(s.sentinel);
  await assert.rejects(promise, e => e === s.sentinel); assert.equal(s.calls.responses.length, 1);
});
test('fresh invocation re-reads every immediate binding', async () => {
  const s = setup(); reply(await s.run(), 200, body()); reply(await s.run(), 200, body());
  for (const k of ['ready', 'account', 'count', 'setting', 'caps'] as const) assert.equal(s.calls[k].length, 2);
});
// NEW packaging inverse metadata control; original86 remain frozen.
test('packaging inverse restores exact original86 callbacks and loader', () => {
  const current = readFileSync(new URL('./auth-session-get-source.test.ts', import.meta.url));
  const marker = Buffer.from("// NEW packaging inverse metadata control; original86 remain frozen.\n");
  const start = current.indexOf(marker);
  assert.ok(start > 0); assert.equal(current.indexOf(marker, start + marker.length), -1);
  const restored = Buffer.concat([current.subarray(0, start), Buffer.from("\n")]);
  assert.equal(createHash('sha256').update(restored).digest('hex'), '47598230a7b7fc6ce3a71ee7f660b14d77947e95fb121141418bff9a236f24f2');
  assert.ok(current.subarray(-2).equals(Buffer.from("}\x29;\n").subarray(-2)));
  assert.ok(!current.subarray(-2).equals(Buffer.from("\n\n")));
});
