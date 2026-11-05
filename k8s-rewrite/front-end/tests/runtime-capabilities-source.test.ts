import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';

// Only this declaration is compiled. No application module or real process
// metadata enters its VM. The TypeScript binding is qualification infrastructure.
const typescriptPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(typescriptPath, 'explicit TypeScript infrastructure binding required');
const ts = createRequire(import.meta.url)(typescriptPath);
const text = readFileSync(new URL('../src/lib/runtime-capabilities.ts', import.meta.url), 'utf8');
const source = ts.createSourceFile('runtime-capabilities.ts', text, ts.ScriptTarget.Latest, true);
type Declaration = { name?: { text?: string }; getText: (file: unknown) => string };
const declarations = source.statements.filter((node: Declaration) =>
  ts.isFunctionDeclaration(node) && node.name?.text === 'runtimeCapabilities');
assert.equal(declarations.length, 1);
assert.equal(source.statements.length, 1, 'no neighbor statements admitted');
const selected = declarations[0].getText(source);
assert.match(selected, /^export function runtimeCapabilities\(/);
const javascript = ts.transpileModule(selected.replace(/^export /, ''), {
  compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None },
}).outputText;

type Env = Readonly<Record<string, string | undefined>>;
type Capabilities = { provisioning: boolean; operatorShell: boolean; podExec: boolean };
type Runtime = (env?: Env, platform?: NodeJS.Platform) => Capabilities;
const flagKeys = ['BORTUS_DISABLE_PROVISIONING', 'BORTUS_DISABLE_OPERATOR_SHELL', 'BORTUS_DISABLE_POD_EXEC'] as const;
const reads = [flagKeys[0], 'KUBERNETES_SERVICE_HOST', flagKeys[1], flagKeys[2]];
const enabled = { provisioning: true, operatorShell: true, podExec: true };

function load(processBinding: unknown = Object.freeze({ env: Object.freeze({}), platform: 'linux' })): Runtime {
  const context = vm.createContext({ process: processBinding });
  return new vm.Script(`${javascript}\nruntimeCapabilities`, { filename: 'selected-runtime-capabilities.js' }).runInContext(context) as Runtime;
}

function result(actual: Capabilities, expected: Capabilities) {
  assert.deepEqual({ ...actual }, expected);
  assert.deepEqual(Reflect.ownKeys(actual), ['provisioning', 'operatorShell', 'podExec']);
  for (const key of Object.keys(expected)) {
    const descriptor = Object.getOwnPropertyDescriptor(actual, key);
    assert.ok(descriptor);
    assert.equal(typeof descriptor.value, 'boolean');
    assert.equal(descriptor.enumerable, true);
    assert.equal(descriptor.writable, true);
    assert.equal(descriptor.configurable, true);
  }
}

function tracked(values: Record<string, unknown>, events: string[], fail?: string, fault?: unknown): Env {
  return new Proxy(values, {
    get(target, key, receiver) {
      events.push(String(key));
      if (key === fail) throw fault;
      return Reflect.get(target, key, receiver);
    },
    ownKeys() { throw new Error('input enumeration is outside the declaration'); },
    set() { throw new Error('input mutation is outside the declaration'); },
  }) as Env;
}

// Supported string/undefined metadata: the complete five-boolean truth table.
for (let mask = 0; mask < 32; mask++) {
  test(`supported capability truth table ${mask}`, () => {
    const provisionOff = Boolean(mask & 1);
    const inCluster = Boolean(mask & 2);
    const windows = Boolean(mask & 4);
    const shellOff = Boolean(mask & 8);
    const execOff = Boolean(mask & 16);
    const env = Object.freeze({
      BORTUS_DISABLE_PROVISIONING: provisionOff ? 'true' : undefined,
      KUBERNETES_SERVICE_HOST: inCluster ? 'public-host.invalid' : undefined,
      BORTUS_DISABLE_OPERATOR_SHELL: shellOff ? 'true' : undefined,
      BORTUS_DISABLE_POD_EXEC: execOff ? 'true' : undefined,
    });
    result(load()(env, windows ? 'win32' : 'linux'), {
      provisioning: !provisionOff && !inCluster,
      operatorShell: !windows && !shellOff,
      podExec: !execOff,
    });
  });
}

for (const key of flagKeys) {
  for (const value of ['', 'false', 'TRUE', ' true ', '1']) {
    test(`supported exact flag spelling ${key} ${JSON.stringify(value)}`, () => {
      result(load()(Object.freeze({ [key]: value }), 'linux'), enabled);
    });
  }
}

const platforms: NodeJS.Platform[] = ['aix', 'android', 'darwin', 'freebsd', 'haiku', 'linux', 'openbsd', 'sunos', 'win32', 'cygwin', 'netbsd'];
for (const platform of platforms) {
  test(`supported platform ${platform}`, () => {
    result(load()(Object.freeze({}), platform), { ...enabled, operatorShell: platform !== 'win32' });
  });
}

test('supported empty host is absent; nonempty host is present without trimming', () => {
  const runtime = load();
  result(runtime({ KUBERNETES_SERVICE_HOST: '' }, 'linux'), enabled);
  for (const host of ['0', 'false', ' ', 'public-host.invalid']) {
    result(runtime({ KUBERNETES_SERVICE_HOST: host }, 'linux'), { ...enabled, provisioning: false });
  }
});

test('supported repeated calls reread metadata and return independent objects', () => {
  const runtime = load();
  const env: Record<string, string | undefined> = {};
  const first = runtime(env, 'linux');
  env.BORTUS_DISABLE_POD_EXEC = 'true';
  const second = runtime(env, 'linux');
  assert.notEqual(first, second);
  result(first, enabled);
  result(second, { ...enabled, podExec: false });
  first.provisioning = false;
  result(second, { ...enabled, podExec: false });
});

test('supported inherited metadata is read without input enumeration', () => {
  const env = Object.create(Object.freeze({ BORTUS_DISABLE_POD_EXEC: 'true' })) as Env;
  result(load()(env, 'linux'), { ...enabled, podExec: false });
});

test('synthetic getters follow the source property order once each', () => {
  const events: string[] = [];
  result(load()(tracked({}, events), 'linux'), enabled);
  assert.deepEqual(events, reads);
});

for (const [name, values, platform, expectedReads, expected] of [
  ['provisioning short-circuit', { BORTUS_DISABLE_PROVISIONING: 'true' }, 'linux', [reads[0], reads[2], reads[3]], { ...enabled, provisioning: false }],
  ['Windows short-circuit', {}, 'win32', [reads[0], reads[1], reads[3]], { ...enabled, operatorShell: false }],
  ['both short-circuits', { BORTUS_DISABLE_PROVISIONING: 'true' }, 'win32', [reads[0], reads[3]], { provisioning: false, operatorShell: false, podExec: true }],
] as const) {
  test(`synthetic ${name} omits only the skipped getter`, () => {
    const events: string[] = [];
    result(load()(tracked(values, events), platform), expected);
    assert.deepEqual(events, expectedReads);
  });
}

for (let i = 0; i < reads.length; i++) {
  test(`synthetic getter failure at ${reads[i]} escapes before later expressions`, () => {
    const events: string[] = [];
    const fault = Object.freeze({ publicFault: reads[i] });
    assert.throws(() => load()(tracked({}, events, reads[i], fault), 'linux'), error => error === fault);
    assert.deepEqual(events, reads.slice(0, i + 1));
  });
}

for (const [values, platform, skipped] of [
  [{ BORTUS_DISABLE_PROVISIONING: 'true' }, 'linux', 'KUBERNETES_SERVICE_HOST'],
  [{}, 'win32', 'BORTUS_DISABLE_OPERATOR_SHELL'],
] as const) {
  test(`synthetic skipped ${skipped} getter cannot throw`, () => {
    const events: string[] = [];
    load()(tracked(values, events, skipped, new Error('skipped')), platform);
    assert.equal(events.includes(skipped), false);
  });
}

for (const [label, argumentsMode, defaultReads] of [
  ['both omitted', 'omit', ['env', 'platform']],
  ['both undefined', 'undefined', ['env', 'platform']],
  ['explicit env', 'env', ['platform']],
  ['explicit platform', 'platform', ['env']],
  ['both explicit', 'both', []],
] as const) {
  test(`synthetic default process bindings: ${label}`, () => {
    const events: string[] = [];
    const env = tracked({}, events);
    const defaults = {
      get env() { events.push('env'); return env; },
      get platform() { events.push('platform'); return 'linux'; },
    };
    const runtime = load(defaults);
    assert.deepEqual(events, [], 'declaration creation does not read defaults');
    let actual: Capabilities;
    if (argumentsMode === 'omit') actual = runtime();
    else if (argumentsMode === 'undefined') actual = runtime(undefined, undefined);
    else if (argumentsMode === 'env') actual = runtime(env);
    else if (argumentsMode === 'platform') actual = runtime(undefined, 'linux');
    else actual = runtime(env, 'linux');
    result(actual, enabled);
    assert.deepEqual(events, [...defaultReads, ...reads]);
  });
}

for (const fail of ['env', 'platform']) {
  test(`synthetic process ${fail} failure precedes body reads`, () => {
    const events: string[] = [];
    const env = tracked({}, events);
    const fault = new Error('public synthetic fault');
    const defaults = new Proxy({ env, platform: 'linux' }, {
      get(target, key, receiver) {
        events.push(String(key));
        if (key === fail) throw fault;
        return Reflect.get(target, key, receiver);
      },
    });
    assert.throws(() => load(defaults)(), error => error === fault);
    assert.deepEqual(events, fail === 'env' ? ['env'] : ['env', 'platform']);
  });
}

test('synthetic default env capture precedes platform side effects', () => {
  const events: string[] = [];
  const original = tracked({}, events);
  const defaults = {
    env: original,
    get platform() {
      events.push('platform');
      this.env = tracked({ BORTUS_DISABLE_POD_EXEC: 'true' }, events);
      return 'linux';
    },
  };
  result(load(defaults)(), enabled);
  assert.deepEqual(events, ['platform', ...reads]);
});

test('synthetic changing getter results are not cached between calls', () => {
  let accesses = 0;
  const env = { get BORTUS_DISABLE_POD_EXEC() { return accesses++ === 0 ? undefined : 'true'; } };
  const runtime = load();
  result(runtime(env, 'linux'), enabled);
  result(runtime(env, 'linux'), { ...enabled, podExec: false });
  assert.equal(accesses, 2);
});

// The following malformed inputs characterize JavaScript, not supported config.
for (const [index, value] of [true, 1, null, Symbol('public'), Object.freeze({ toString() { throw new Error('no coercion'); } })].entries()) {
  test(`JavaScript-only strict flag comparison ${index} ${typeof value}`, () => {
    result(load()({ BORTUS_DISABLE_POD_EXEC: value } as unknown as Env, 'linux'), enabled);
  });
}

test('JavaScript-only host truthiness performs no object coercion', () => {
  const host = { [Symbol.toPrimitive]() { throw new Error('no host coercion'); } };
  result(load()({ KUBERNETES_SERVICE_HOST: host } as unknown as Env, 'linux'), { ...enabled, provisioning: false });
});

test('JavaScript-only platform strict comparison performs no coercion', () => {
  const platform = { [Symbol.toPrimitive]() { throw new Error('no platform coercion'); } };
  result(load()({}, platform as unknown as NodeJS.Platform), enabled);
});

test('JavaScript-only null env is not defaulted and fails before body continuation', () => {
  const events: string[] = [];
  const runtime = load({ get env() { throw new Error('must not default null'); }, get platform() { events.push('platform'); return 'linux'; } });
  assert.throws(() => runtime(null as unknown as Env), error => (error as Error).name === 'TypeError');
  assert.deepEqual(events, ['platform']);
});

test('JavaScript-only primitive env uses property access without enumeration', () => {
  for (const env of [false, 0, 'public']) result(load()(env as unknown as Env, 'linux'), enabled);
});
