// Finite PUBLIC source controls: only the selected audit GET callback executes.
// Real imports, Zod schema, authentication, registry and native transports stay inert.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const requireTool = createRequire(import.meta.url);
const ts = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL('../src/app/api/kv/audit/route.ts', import.meta.url), 'utf8');
const syntax = ts.createSourceFile('audit-route.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const declarations = syntax.statements.filter((s: { declarationList?: unknown }) => s.declarationList);
const variables = declarations.flatMap((s: { declarationList: { declarations: unknown[] } }) => s.declarationList.declarations);
const named = (name: string) => variables.find((v: { name: { getText(): string } }) => v.name.getText() === name);
const initializer = named('GET').initializer;
assert.equal(initializer.expression.getText(syntax), 'kvHuman');
assert.equal(initializer.arguments.length, 1);
const callbackText = initializer.arguments[0].getText(syntax);
const javascript = ts.transpileModule('const selected = ' + callbackText + ';', { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Callback = (...args: unknown[]) => Promise<unknown>;
type Hook = (stage: string, args: unknown[], receiver: unknown) => unknown;
const absent = Symbol('absent');
class PublicError extends Error { status: number; constructor(status: number, message: string) { super(message); this.status = status; } }
function harness(hook: Hook = () => absent) {
  const trace: string[] = [];
  const actor = new Proxy({}, { get() { throw new Error('identity internals read'); } });
  const request = new Proxy({ url: 'https://synthetic.invalid/?pathId=p&operationId=o&cursor=c' }, {
    get(target, key) { if (key !== 'url') throw new Error('unrelated request field'); return target.url; },
  });
  const data = { pathId: 'parsed-path', operationId: 'parsed-operation' };
  const result = { success: true, data };
  const cursor = { cursor: 'opaque' };
  const value = { events: [] };
  const call = (stage: string, args: unknown[], receiver: unknown, fallback: unknown) => {
    trace.push(stage); const out = hook(stage, args, receiver); return out === absent ? fallback : out;
  };
  const filters = { safeParse(input: unknown) { return call('parse', [input], this, result); } };
  const registry = { listAudit(...args: unknown[]) { return call('list', args, this, value); } };
  const cursorFn = function(this: unknown, ...args: unknown[]) { return call('cursor', args, this, cursor); };
  const selected: Callback = new Function('URL', 'filters', 'metadataCursor', 'KvError', '"use strict";\n' + javascript + '\nreturn selected;')(URL, filters, cursorFn, PublicError);
  return { selected, actor, request, registry, filters, trace, data, result, cursor, value };
}
const invoke = (h: ReturnType<typeof harness>, request: unknown = h.request, registry: unknown = h.registry) => h.selected(registry, h.actor, request);

test('audit GET finite source boundary', async t => {
  await t.test('exact wrapper and inert schema declaration', () => {
    assert.equal(named('runtime').initializer.text, 'nodejs');
    assert.equal(named('dynamic').initializer.text, 'force-dynamic');
    assert.equal(named('filters').initializer.getText(syntax), 'z.object({ pathId: z.string().uuid().optional(), operationId: z.string().uuid().optional() }).strict()');
    assert.equal(initializer.arguments[0].parameters.length, 3);
    assert.match(callbackText, /^async \(registry, actor, request\) =>/);
    assert.equal(syntax.statements.filter((s: unknown) => ts.isImportDeclaration(s)).length, 3);
  });
  for (const query of ['', '?pathId=p', '?operationId=o', '?cursor=c', '?pathId=p&operationId=o&cursor=c', '?cursor=', '?pathId=&operationId=']) {
    await t.test('query projection ' + query, async () => {
      let parsedInput: unknown;
      const h = harness((stage, args, receiver) => {
        if (stage === 'parse') { parsedInput = args[0]; assert.equal(receiver, h.filters); assert.equal(args.length, 1); }
        if (stage === 'cursor') { assert.equal(receiver, undefined); assert.equal(args.length, 1); assert.equal(args[0], request); }
        if (stage === 'list') { assert.equal(receiver, h.registry); assert.equal(args.length, 2); assert.equal(args[0], h.actor); assert.deepEqual(args[1], { ...h.data, cursor: h.cursor }); }
        return absent;
      });
      const request = { url: 'https://synthetic.invalid/' + query };
      assert.equal(await invoke(h, request), h.value);
      const params = new URL(request.url).searchParams;
      assert.deepEqual(parsedInput, { pathId: params.get('pathId') ?? undefined, operationId: params.get('operationId') ?? undefined });
      assert.deepEqual(h.trace, ['parse', 'cursor', 'list']);
    });
  }
  for (const query of ['?other=x', '?PathId=x', '?pathId=x&pathId=y', '?operationId=x&operationId=y', '?cursor=x&cursor=y', '?%70athId=x&pathId=y', '?=x', '?pathId=x&other=y&cursor=z']) {
    await t.test('invalid query stops before parser ' + query, async () => {
      const h = harness();
      await assert.rejects(invoke(h, { url: 'https://synthetic.invalid/' + query }), (e: unknown) => e instanceof PublicError && e.status === 400 && e.message === 'Invalid audit filters');
      assert.deepEqual(h.trace, []);
    });
  }
  for (const success of [false, null, undefined, 0, '']) {
    await t.test('parse refusal ' + String(success), async () => {
      const h = harness(stage => stage === 'parse' ? { success, get data() { return assert.fail('refused data read'); } } : absent);
      await assert.rejects(invoke(h), (e: unknown) => e instanceof PublicError && e.status === 400);
      assert.deepEqual(h.trace, ['parse']);
    });
  }
  for (const stage of ['parse', 'cursor', 'list']) {
    await t.test('exact thrown sentinel at ' + stage, async () => {
      const sentinel = {};
      const h = harness(s => { if (s === stage) throw sentinel; return absent; });
      await assert.rejects(invoke(h), e => e === sentinel);
      assert.deepEqual(h.trace, ['parse', 'cursor', 'list'].slice(0, ['parse', 'cursor', 'list'].indexOf(stage) + 1));
    });
  }
  for (const request of [null, undefined, {}, { url: 'not an absolute URL' }, { get url() { throw new Error('url sentinel'); } }]) {
    await t.test('URL or request refusal ' + String(request), async () => {
      const h = harness(); await assert.rejects(h.selected(h.registry, h.actor, request)); assert.deepEqual(h.trace, []);
    });
  }
  for (const registry of [null, undefined, {}, { listAudit: null }, { listAudit: 1 }]) {
    await t.test('registry/method refusal ' + String(registry), async () => {
      const h = harness(); await assert.rejects(h.selected(registry, h.actor, h.request), TypeError);
      assert.deepEqual(h.trace, registry == null ? ['parse'] : ['parse', 'cursor']);
    });
  }
  await t.test('list getter captured before parsed data and cursor', async () => {
    const events: string[] = [];
    const data = { get pathId() { events.push('data'); return 'p'; } };
    const h = harness((stage, args, receiver) => {
      events.push(stage);
      if (stage === 'parse') return { get success() { events.push('success'); return true; }, get data() { events.push('data-object'); return data; } };
      if (stage === 'list') { assert.equal(receiver, registry); assert.deepEqual(args[1], { pathId: 'p', cursor: h.cursor }); }
      return absent;
    });
    const registry = { get listAudit() { events.push('method'); return h.registry.listAudit; } };
    assert.equal(await invoke(h, h.request, registry), h.value);
    assert.deepEqual(events, ['parse', 'success', 'method', 'data-object', 'data', 'cursor', 'list']);
  });
  await t.test('method getter refusal stops data spread and cursor', async () => {
    const sentinel = {};
    const h = harness(stage => stage === 'parse' ? { success: true, get data() { return assert.fail('data read after method refusal'); } } : absent);
    await assert.rejects(invoke(h, h.request, { get listAudit() { throw sentinel; } }), e => e === sentinel);
    assert.deepEqual(h.trace, ['parse']);
  });
  await t.test('noncallable method still evaluates data and cursor before TypeError', async () => {
    const h = harness(); await assert.rejects(invoke(h, h.request, { listAudit: 0 }), TypeError);
    assert.deepEqual(h.trace, ['parse', 'cursor']);
  });
  await t.test('own enumerable spread, symbols, cursor override and fresh options', async () => {
    const symbol = Symbol('public metadata');
    const data = Object.assign(Object.create({ inherited: 1 }), { pathId: 'p', cursor: 'discarded', [symbol]: 's' });
    Object.defineProperty(data, 'hidden', { get() { return assert.fail('hidden property read'); } });
    const options: unknown[] = [];
    const h = harness((stage, args) => {
      if (stage === 'parse') return { success: true, data };
      if (stage === 'list') { options.push(args[1]); assert.deepEqual(args[1], { pathId: 'p', cursor: h.cursor, [symbol]: 's' }); }
      return absent;
    });
    await invoke(h); await invoke(h);
    assert.notEqual(options[0], options[1]); assert.notEqual(options[0], data);
  });
  for (const data of [null, undefined, {}, { pathId: 'p' }]) {
    await t.test('native spread operand ' + String(data), async () => {
      const h = harness((stage, args) => {
        if (stage === 'parse') return { success: true, data };
        if (stage === 'list') assert.deepEqual(args[1], { ...data, cursor: h.cursor });
        return absent;
      });
      await invoke(h);
    });
  }
  await t.test('spread getter refusal stops cursor/list', async () => {
    const sentinel = {};
    const h = harness(stage => stage === 'parse' ? { success: true, data: { get pathId() { throw sentinel; } } } : absent);
    await assert.rejects(invoke(h), e => e === sentinel); assert.deepEqual(h.trace, ['parse']);
  });
  await t.test('inherited listAudit receiver remains registry', async () => {
    const h = harness((stage, args, receiver) => { if (stage === 'list') assert.equal(receiver, registry); return absent; });
    const registry = Object.create(h.registry); await invoke(h, h.request, registry);
  });
  await t.test('registry proxy only captures listAudit', async () => {
    const keys: PropertyKey[] = [];
    const h = harness(); const registry = new Proxy(h.registry, { get(target, key, receiver) { keys.push(key); return Reflect.get(target, key, receiver); } });
    await invoke(h, h.request, registry); assert.deepEqual(keys, ['listAudit']);
  });
  for (const stage of ['parse', 'cursor', 'list']) {
    await t.test('fresh call after ' + stage + ' refusal', async () => {
      let first = true; const sentinel = {};
      const h = harness(s => { if (s === stage && first) { first = false; throw sentinel; } return absent; });
      await assert.rejects(invoke(h), e => e === sentinel); assert.equal(await invoke(h), h.value);
    });
  }
  for (const value of [undefined, null, false, 0, 'public-result', { metadata: 1 }]) {
    await t.test('async plain result ' + String(value), async () => {
      const h = harness(stage => stage === 'list' ? value : absent);
      const promise = invoke(h); assert.ok(promise instanceof Promise); assert.equal(await promise, value);
    });
  }
  await t.test('pending result interleaves without sharing options or actor', async () => {
    const releases: ((value: unknown) => void)[] = []; const options: unknown[] = []; const actors: unknown[] = [];
    const h = harness((stage, args) => {
      if (stage === 'list') { options.push(args[1]); actors.push(args[0]); return new Promise(resolve => releases.push(resolve)); }
      return absent;
    });
    const secondActor = {}; const first = invoke(h); const second = h.selected(h.registry, secondActor, h.request);
    assert.equal(releases.length, 2); assert.notEqual(options[0], options[1]); assert.deepEqual(actors, [h.actor, secondActor]);
    releases[1]('second'); assert.equal(await second, 'second'); releases[0]('first'); assert.equal(await first, 'first');
  });
  await t.test('reentrant registry call retains independent arguments', async () => {
    let nested: Promise<unknown> | undefined; let entered = false;
    const h = harness(stage => { if (stage === 'list' && !entered) { entered = true; nested = invoke(h); } return absent; });
    assert.equal(await invoke(h), h.value); assert.equal(await nested, h.value); assert.equal(h.trace.filter(x => x === 'list').length, 2);
  });
  for (const reject of [false, true]) {
    await t.test('thenable adoption ' + reject, async () => {
      const sentinel = {}; let receiver: unknown; let reads = 0;
      const thenable = { get then() { reads++; return function(this: unknown, resolve: (v: unknown) => void, refuse: (v: unknown) => void) { receiver = this; (reject ? refuse : resolve)(sentinel); }; } };
      const h = harness(stage => stage === 'list' ? thenable : absent);
      if (reject) await assert.rejects(invoke(h), e => e === sentinel); else assert.equal(await invoke(h), sentinel);
      assert.equal(reads, 1); assert.equal(receiver, thenable);
    });
  }
  await t.test('then getter rejection retains sentinel', async () => {
    const sentinel = {}; const h = harness(stage => stage === 'list' ? { get then() { throw sentinel; } } : absent);
    await assert.rejects(invoke(h), e => e === sentinel);
  });
});
