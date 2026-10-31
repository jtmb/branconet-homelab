import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { test } from 'node:test';

const requireTool = createRequire(import.meta.url);
const ts = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL('../src/lib/metadata-query.ts', import.meta.url), 'utf8');
const ast = ts.createSourceFile('metadata-query.ts', source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((n: { name?: { text?: string } }) =>
  ts.isFunctionDeclaration(n) && n.name?.text === 'isSharedMetadataQuery');
assert.equal(selected.length, 1);
const declaration = selected[0].getText(ast);
assert.ok(declaration.startsWith('export function isSharedMetadataQuery(url: string): boolean'));
const emitted = ts.transpileModule(declaration, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;

type Bindings = {
  url?: unknown;
  decode?: unknown;
  kv?: (url: string) => boolean;
};
function load(bindings: Bindings = {}) {
  const calls: string[] = [];
  const kvCalls: unknown[] = [];
  const URLBinding = bindings.url ?? class {
    constructor(value: string, base: string) {
      calls.push(`URL:${value}:${base}`);
      return new URL(value, base);
    }
  };
  const context = vm.createContext({
    exports: {}, URL: URLBinding,
    decodeURIComponent: bindings.decode ?? ((path: string) => {
      calls.push(`decode:${path}`);
      return decodeURIComponent(path);
    }),
    isKvMetadataQuery: (url: string) => {
      kvCalls.push(url);
      return bindings.kv?.(url) ?? false;
    },
  }, { codeGeneration: { strings: false, wasm: false } });
  vm.runInContext(emitted, context, { timeout: 1000 });
  const fn = (context.exports as { isSharedMetadataQuery: (url: string) => boolean }).isSharedMetadataQuery;
  return { fn, calls, kvCalls };
}

const allowed = ['/api/auth/session', '/api/nodes', '/api/users', '/api/settings', '/api/vars',
  '/api/secret-references', '/api/secrets', '/api/deploy/history'];
for (const path of allowed) {
  test(`exact route ${path}`, () => {
    const h = load(); assert.equal(h.fn(path), true); assert.deepEqual(h.kvCalls, []);
  });
  test(`route is exact ${path}/`, () => assert.equal(load().fn(path + '/'), false));
}
for (const path of ['/api/cluster/', '/api/cluster/pods', '/api/cluster/pods/ns/item', '/api/flux/', '/api/flux/repos', '/api/flux/repos/id/sync']) {
  test(`prefix classification ${path}`, () => assert.equal(load().fn(path), true));
}
for (const path of ['', '/', 'api/nodes', 'https://bortus.invalid/api/nodes', '//bortus.invalid/api/nodes', '/API/nodes', '/api', '/api/', '/api/cluster', '/api/flux', '/api/clustered/pods', '/api/fluxed/repos', '/api/auth/login', '/api/users/id', '/api/secrets/id', '/api/deploy/history/id']) {
  test(`refuse ${JSON.stringify(path)}`, () => assert.equal(load().fn(path), false));
}
for (const path of ['/api/cluster/pods/yaml', '/api/cluster/pods/logs', '/api/cluster/pods/exec', '/api/cluster/yaml/child', '/api/flux/logs/child', '/api/flux/exec', '/api/cluster/pods/%6cogs', '/api/cluster/pods%2Fexec/child', '/api/cluster/%79aml']) {
  test(`private decoded segment ${path}`, () => assert.equal(load().fn(path), false));
}
for (const path of ['/api/cluster/catalogs', '/api/cluster/logs-summary', '/api/cluster/execute', '/api/cluster/Logs', '/api/flux/yamlx']) {
  test(`segment boundary/case ${path}`, () => assert.equal(load().fn(path), true));
}
for (const path of ['/api/secrets?key=', '/api/secrets?key=value', '/api/secrets?%6bey=value', '/api/secrets?key=a&key=b', '/api/deploy/history?jobId=', '/api/deploy/history?jobId=item', '/api/deploy/history?%6aobId=item']) {
  test(`private query key ${path}`, () => assert.equal(load().fn(path), false));
}
for (const path of ['/api/secrets?Key=a', '/api/secrets?x=key', '/api/secrets?jobId=a', '/api/deploy/history?jobid=a', '/api/deploy/history?key=a', '/api/nodes?key=a&jobId=b', '/api/cluster/pods?key=a', '/api/flux/repos?jobId=b', '/api/nodes?x=a&x=b', '/api/nodes?', '/api/nodes#fragment', '/api/secrets#?key=a']) {
  test(`query/fragment classification only ${path}`, () => assert.equal(load().fn(path), true));
}
for (const path of ['/api/%6eodes', '/api/cluster/../nodes', '/api/cluster/./pods', '/api/cluster%2Fpods', '/api/nodes\n', '/api/nodes\t']) {
  test(`URL/decoded path semantics ${JSON.stringify(path)}`, () => assert.equal(load().fn(path), true));
}
for (const path of ['/api/cluster/%', '/api/cluster/%FF', '/api/cluster/%E0%A4', '/api/%00nodes', '/api/nodes%2F', '/api/%252Fcluster/pods']) {
  test(`decode refusal or exactness ${path}`, () => assert.equal(load().fn(path), false));
}
for (const answer of [false, true]) {
  test(`KV delegation returns inert answer ${answer}`, () => {
    const input = '/api/kv/paths?synthetic=1#fragment';
    const h = load({ kv: () => answer });
    assert.equal(h.fn(input), answer); assert.deepEqual(h.kvCalls, [input]);
  });
  test(`decoded KV delegates original text ${answer}`, () => {
    const input = '/api/%6bv/paths'; const h = load({ kv: () => answer });
    assert.equal(h.fn(input), answer); assert.deepEqual(h.kvCalls, [input]);
  });
}
test('prefix refusal precedes constructor and decoder', () => {
  const h = load({ url: class { constructor() { throw new Error('inert URL forbidden'); } }, decode: () => { throw new Error('inert decode forbidden'); } });
  assert.equal(h.fn('/outside'), false); assert.deepEqual(h.kvCalls, []);
});
test('constructor receives exact original input and fixed inert base before decode', () => {
  const h = load(); assert.equal(h.fn('/api/nodes'), true);
  assert.deepEqual(h.calls, ['URL:/api/nodes:https://bortus.invalid', 'decode:/api/nodes']);
});
test('constructor faults outside decode catch propagate as JavaScript only', () => {
  const fault = new Error('inert constructor fault');
  assert.throws(() => load({ url: class { constructor() { throw fault; } } }).fn('/api/nodes'), e => e === fault);
});
test('pathname getter faults inside decode catch fail closed', () => {
  const h = load({ url: class { get pathname() { throw new Error('inert pathname fault'); } } });
  assert.equal(h.fn('/api/nodes'), false); assert.deepEqual(h.kvCalls, []);
});
test('decoder fault fails closed before delegation', () => {
  const h = load({ decode: () => { throw new Error('inert decoder fault'); } });
  assert.equal(h.fn('/api/kv/paths'), false); assert.deepEqual(h.kvCalls, []);
});
test('KV result shortcircuits final regex and searchParams', () => {
  const h = load({ url: class {
    pathname = '/api/kv/logs';
    get searchParams() { throw new Error('inert params forbidden'); }
  }, kv: () => true });
  assert.equal(h.fn('/api/kv/logs'), true); assert.deepEqual(h.kvCalls, ['/api/kv/logs']);
});
test('KV dependency fault propagates outside decode catch', () => {
  const fault = new Error('inert KV fault'); const h = load({ kv: () => { throw fault; } });
  assert.throws(() => h.fn('/api/kv/paths'), e => e === fault);
});
for (const path of ['/api/unlisted', '/api/cluster/logs', '/api/cluster/pods', '/api/nodes']) {
  test(`no searchParams access for ${path}`, () => {
    const h = load({ url: class { pathname = path; get searchParams() { throw new Error('inert params forbidden'); } } });
    assert.equal(h.fn(path), path === '/api/cluster/pods' || path === '/api/nodes');
  });
}
for (const [path, key] of [['/api/secrets', 'key'], ['/api/deploy/history', 'jobId']]) {
  for (const has of [false, true]) {
    test(`exact final key ${path} ${has}`, () => {
      const observed: string[] = [];
      const h = load({ url: class { pathname = path; get searchParams() {
        observed.push('params'); return { has(k: string) { observed.push(k); return has; } };
      } } });
      assert.equal(h.fn(path), !has); assert.deepEqual(observed, ['params', key]);
    });
  }
  test(`final params getter fault ${path} propagates as JavaScript only`, () => {
    const fault = new Error('inert params fault');
    const h = load({ url: class { pathname = path; get searchParams() { throw fault; } } });
    assert.throws(() => h.fn(path), e => e === fault);
  });
  test(`final has fault ${path} propagates as JavaScript only`, () => {
    const fault = new Error('inert has fault');
    const h = load({ url: class { pathname = path; searchParams = { has() { throw fault; } }; } });
    assert.throws(() => h.fn(path), e => e === fault);
  });
}
test('fresh isolated calls do not reuse classification or delegated result', () => {
  let answer = true; const h = load({ kv: () => answer });
  assert.equal(h.fn('/api/kv/paths'), true); answer = false;
  assert.equal(h.fn('/api/kv/paths'), false); assert.equal(h.fn('/api/nodes'), true);
  assert.deepEqual(h.kvCalls, ['/api/kv/paths', '/api/kv/paths']);
});
