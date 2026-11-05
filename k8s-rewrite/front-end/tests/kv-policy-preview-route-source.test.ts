// Finite PUBLIC source controls: only the exact policy-preview POST callback executes.
// Real imports, body/schema parsing, authentication, registry and transports stay inert.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const requireTool = createRequire(import.meta.url);
const ts = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL('../src/app/api/kv/policies/preview/route.ts', import.meta.url), 'utf8');
const syntax = ts.createSourceFile('policy-preview-route.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const variables = syntax.statements.filter((s: { declarationList?: unknown }) => s.declarationList)
  .flatMap((s: { declarationList: { declarations: unknown[] } }) => s.declarationList.declarations);
const named = (name: string) => variables.find((v: { name: { getText(): string } }) => v.name.getText() === name);
const initializer = named('POST').initializer;
assert.equal(initializer.expression.getText(syntax), 'kvHuman');
assert.equal(initializer.arguments.length, 1);
const callbackText = initializer.arguments[0].getText(syntax);
const javascript = ts.transpileModule('const selected = ' + callbackText + ';', {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText;

type Callback = (...args: unknown[]) => Promise<unknown>;
type Hook = (stage: string, args: unknown[], receiver: unknown) => unknown;
const absent = Symbol('no override');
function harness(action: unknown, hook: Hook = () => absent) {
  const trace: string[] = [];
  const opaque = (name: string) => new Proxy({}, { get() { throw new Error(name + ' internals read'); } });
  const actor = opaque('actor');
  const request = opaque('request');
  const schema = opaque('schema');
  const input = { action, id: 'public-id', revision: 7, cursor: 'public-cursor', effect: 'allow', actions: ['list'] };
  const value = { preview: 'public-only' };
  const call = (stage: string, args: unknown[], receiver: unknown, fallback: unknown) => {
    trace.push(stage); const out = hook(stage, args, receiver); return out === absent ? fallback : out;
  };
  const body = function(this: unknown, ...args: unknown[]) { return call('body', args, this, input); };
  const registry = { previewPolicy(...args: unknown[]) { return call('preview', args, this, value); } };
  const selected: Callback = new Function('kvBody', 'policyPreview', '"use strict";\n' + javascript + '\nreturn selected;')(body, schema);
  return { selected, registry, actor, request, schema, input, value, trace };
}
type Harness = ReturnType<typeof harness>;
const invoke = (h: Harness, registry: unknown = h.registry) => h.selected(registry, h.actor, h.request);
const branches = ['delete', 'create', 'update'] as const;

test('policy-preview POST finite source boundary', async t => {
  await t.test('exact default wrapper and inert imports', () => {
    assert.equal(named('runtime').initializer.text, 'nodejs');
    assert.equal(named('dynamic'), undefined);
    assert.deepEqual(variables.map((v: { name: { getText(): string } }) => v.name.getText()), ['runtime', 'POST']);
    assert.equal(syntax.statements.filter((s: unknown) => ts.isImportDeclaration(s)).length, 2);
    assert.equal(initializer.arguments[0].parameters.length, 3);
    assert.match(callbackText, /^async \(registry, actor, request\) =>/);
    assert.match(callbackText, /const input = await kvBody\(request, policyPreview\);/);
  });
  for (const action of [...branches, 'unknown', '', null, undefined, 0, false]) {
    await t.test('exact branch projection ' + String(action), async () => {
      const h = harness(action, (stage, args, receiver) => {
        if (stage === 'body') { assert.equal(receiver, undefined); assert.equal(args.length, 2); assert.equal(args[0], h.request); assert.equal(args[1], h.schema); }
        if (stage === 'preview') {
          assert.equal(receiver, h.registry); assert.equal(args.length, 5); assert.equal(args[0], h.actor);
          if (action === 'delete') assert.deepEqual(args.slice(1), [null, h.input.id, h.input.revision, h.input.cursor]);
          else if (action === 'create') assert.deepEqual(args.slice(1), [{ id: h.input.id, revision: h.input.revision, effect: 'allow', actions: h.input.actions }, undefined, undefined, h.input.cursor]);
          else assert.deepEqual(args.slice(1), [{ effect: 'allow', actions: h.input.actions }, h.input.id, h.input.revision, h.input.cursor]);
        }
        return absent;
      });
      assert.equal(await invoke(h), h.value); assert.deepEqual(h.trace, ['body', 'preview']);
    });
  }
  for (const action of branches) {
    await t.test(action + ' exact getter/evaluation order', async () => {
      const events: string[] = [];
      const input = Object.defineProperties({}, Object.fromEntries(['action', 'id', 'revision', 'cursor', 'field'].map(key => [key, {
        enumerable: true, get() { events.push(key); return key === 'action' ? action : key; },
      }])));
      const registry = { get previewPolicy() { events.push('method'); return function(this: unknown, ...args: unknown[]) { events.push('call'); assert.equal(this, registry); assert.equal(args.length, 5); return 'done'; }; } };
      const h = harness(action, stage => { if (stage === 'body') { events.push('body'); return input; } return absent; });
      assert.equal(await invoke(h, registry), 'done');
      assert.deepEqual(events, action === 'delete'
        ? ['body', 'action', 'method', 'id', 'revision', 'cursor', 'call']
        : action === 'create'
          ? ['body', 'action', 'action', 'action', 'cursor', 'id', 'revision', 'field', 'method', 'call']
          : ['body', 'action', 'action', 'action', 'id', 'revision', 'cursor', 'field', 'method', 'call']);
    });
  }
  for (const action of branches) {
    for (const registry of [null, undefined, {}, { previewPolicy: null }, { previewPolicy: 1 }]) {
      await t.test(action + ' native registry/method refusal ' + String(registry), async () => {
        const h = harness(action); await assert.rejects(h.selected(registry, h.actor, h.request), TypeError); assert.deepEqual(h.trace, ['body']);
      });
    }
  }
  for (const action of branches) {
    for (const stage of ['body', 'preview']) {
      await t.test(action + ' original thrown sentinel ' + stage, async () => {
        const sentinel = {};
        const h = harness(action, s => { if (s === stage) throw sentinel; return absent; });
        await assert.rejects(invoke(h), e => e === sentinel);
        assert.deepEqual(h.trace, stage === 'body' ? ['body'] : ['body', 'preview']);
      });
    }
    for (const stage of ['body', 'preview']) {
      await t.test(action + ' original async rejection ' + stage, async () => {
        const sentinel = {};
        const h = harness(action, s => s === stage ? Promise.reject(sentinel) : absent);
        await assert.rejects(invoke(h), e => e === sentinel);
        assert.deepEqual(h.trace, stage === 'body' ? ['body'] : ['body', 'preview']);
      });
    }
  }
  for (const input of [null, undefined]) {
    await t.test('nullish body result refuses ' + String(input), async () => {
      const h = harness('update', stage => stage === 'body' ? input : absent);
      await assert.rejects(invoke(h), TypeError); assert.deepEqual(h.trace, ['body']);
    });
  }
  for (const at of [1, 2, 3]) {
    await t.test('action getter refusal read ' + at, async () => {
      const sentinel = {}; let reads = 0;
      const input = { get action() { if (++reads === at) throw sentinel; return 'update'; } };
      const h = harness('update', stage => stage === 'body' ? input : absent);
      await assert.rejects(invoke(h), e => e === sentinel); assert.equal(reads, at); assert.deepEqual(h.trace, ['body']);
    });
  }
  for (const action of branches) {
    for (const key of ['id', 'revision', 'cursor']) {
      await t.test(action + ' binding/argument getter refusal ' + key, async () => {
        const sentinel = {}; let methods = 0;
        const input = { action, id: 'i', revision: 1, cursor: 'c' };
        Object.defineProperty(input, key, { enumerable: true, get() { throw sentinel; } });
        const registry = { get previewPolicy() { methods++; return () => assert.fail('call after refused argument'); } };
        const h = harness(action, stage => stage === 'body' ? input : absent);
        await assert.rejects(invoke(h, registry), e => e === sentinel); assert.equal(methods, action === 'delete' ? 1 : 0);
      });
    }
    await t.test(action + ' method getter refusal and field-read boundary', async () => {
      const sentinel = {}; const reads: string[] = [];
      const input = { action, get id() { reads.push('id'); return 'i'; }, get revision() { reads.push('revision'); return 1; }, get cursor() { reads.push('cursor'); return 'c'; }, get field() { reads.push('field'); return 'f'; } };
      const h = harness(action, stage => stage === 'body' ? input : absent);
      await assert.rejects(invoke(h, { get previewPolicy() { throw sentinel; } }), e => e === sentinel);
      assert.deepEqual(reads, action === 'delete' ? [] : action === 'create' ? ['cursor', 'id', 'revision', 'field'] : ['id', 'revision', 'cursor', 'field']);
    });
    await t.test(action + ' noncallable method evaluates arguments', async () => {
      const reads: string[] = [];
      const input = { action, get id() { reads.push('id'); return 'i'; }, get revision() { reads.push('revision'); return 1; }, get cursor() { reads.push('cursor'); return 'c'; } };
      const h = harness(action, stage => stage === 'body' ? input : absent);
      await assert.rejects(invoke(h, { previewPolicy: false }), TypeError);
      assert.deepEqual(reads, action === 'create' ? ['cursor', 'id', 'revision'] : ['id', 'revision', 'cursor']);
    });
    await t.test(action + ' inherited method receiver and one capture', async () => {
      const h = harness(action); let gets = 0;
      const registry = Object.create({ get previewPolicy() { gets++; return function(this: unknown, ...args: unknown[]) { assert.equal(this, registry); assert.equal(args[0], h.actor); return h.value; }; } });
      assert.equal(await invoke(h, registry), h.value); assert.equal(gets, 1);
    });
    await t.test(action + ' proxy registry preserves receiver', async () => {
      const h = harness(action); const keys: PropertyKey[] = [];
      const registry = new Proxy({}, { get(_target, key, receiver) { keys.push(key); assert.equal(receiver, registry); return function(this: unknown) { assert.equal(this, registry); return h.value; }; } });
      assert.equal(await invoke(h, registry), h.value); assert.deepEqual(keys, ['previewPolicy']);
    });
  }
  for (const action of ['create', 'update'] as const) {
    await t.test(action + ' own enumerable rest, symbols, exclusions and prototype safety', async () => {
      const symbol = Symbol('public field'); const inherited = { action, id: 'inherited-id', revision: 9, cursor: 'inherited-cursor', ignored: true };
      const input = Object.assign(Object.create(inherited), { field: 'f', [symbol]: 's' });
      Object.defineProperty(input, '__proto__', { value: 'own-data', enumerable: true });
      Object.defineProperty(input, 'hidden', { get() { return assert.fail('hidden read'); } });
      const fields: object[] = [];
      const h = harness(action, (stage, args) => {
        if (stage === 'body') return input;
        if (stage === 'preview') {
          fields.push(args[1] as object); assert.equal(Object.getPrototypeOf(args[1]), Object.prototype);
          assert.deepEqual(Reflect.ownKeys(args[1] as object), ['field', '__proto__', symbol]);
          assert.equal(Object.getOwnPropertyDescriptor(args[1], '__proto__')?.value, 'own-data');
          assert.deepEqual(args.slice(2), action === 'create' ? [undefined, undefined, 'inherited-cursor'] : ['inherited-id', 9, 'inherited-cursor']);
        }
        return absent;
      });
      await invoke(h); await invoke(h); assert.notEqual(fields[0], fields[1]); assert.notEqual(fields[0], input);
      assert.equal(Object.getPrototypeOf(input), inherited);
    });
    for (const trap of ['ownKeys', 'getOwnPropertyDescriptor', 'get'] as const) {
      await t.test(action + ' rest proxy refusal ' + trap, async () => {
        const sentinel = {}; let methods = 0;
        const target = { action, field: 'f' };
        const input = new Proxy(target, {
          ownKeys(t) { if (trap === 'ownKeys') throw sentinel; return Reflect.ownKeys(t); },
          getOwnPropertyDescriptor(t, k) { if (trap === 'getOwnPropertyDescriptor' && k === 'field') throw sentinel; return Reflect.getOwnPropertyDescriptor(t, k); },
          get(t, k, r) { if (trap === 'get' && k === 'field') throw sentinel; return Reflect.get(t, k, r); },
        });
        const h = harness(action, stage => stage === 'body' ? input : absent);
        await assert.rejects(invoke(h, { get previewPolicy() { methods++; return () => 0; } }), e => e === sentinel); assert.equal(methods, 0);
      });
    }
  }
  await t.test('delete never enumerates unrelated input fields', async () => {
    const input = new Proxy({ action: 'delete', id: 'i', revision: 1, cursor: 'c' }, {
      ownKeys() { return assert.fail('delete enumerated input'); }, get(t, k, r) { if (!['action', 'id', 'revision', 'cursor', 'then'].includes(String(k))) return assert.fail('unrelated input read'); return Reflect.get(t, k, r); },
    });
    const h = harness('delete', stage => stage === 'body' ? input : absent); assert.equal(await invoke(h), h.value);
  });
  for (const action of branches) {
    await t.test(action + ' pending body defers all input and registry reads', async () => {
      let resolve!: (value: unknown) => void; let methods = 0;
      const pending = new Promise(r => { resolve = r; });
      const h = harness(action, stage => stage === 'body' ? pending : absent);
      const registry = { get previewPolicy() { methods++; return h.registry.previewPolicy; } };
      const result = invoke(h, registry); assert.ok(result instanceof Promise); await Promise.resolve();
      assert.deepEqual(h.trace, ['body']); assert.equal(methods, 0);
      resolve(h.input); assert.equal(await result, h.value); assert.equal(methods, 1);
    });
    await t.test(action + ' body thenable adoption and original identities', async () => {
      let calls = 0;
      const thenable = { then(resolve: (value: unknown) => void) { calls++; assert.equal(this, thenable); resolve(h.input); } };
      const h = harness(action, stage => stage === 'body' ? thenable : absent);
      assert.equal(await invoke(h), h.value); assert.equal(calls, 1);
    });
    await t.test(action + ' result thenable adoption', async () => {
      let calls = 0; const value = {};
      const thenable = { then(resolve: (v: unknown) => void) { calls++; assert.equal(this, thenable); resolve(value); } };
      const h = harness(action, stage => stage === 'preview' ? thenable : absent);
      assert.equal(await invoke(h), value); assert.equal(calls, 1);
    });
    for (const stage of ['body', 'preview']) {
      await t.test(action + ' then getter refusal ' + stage, async () => {
        const sentinel = {}; const thenable = { get then() { throw sentinel; } };
        const h = harness(action, s => s === stage ? thenable : absent); await assert.rejects(invoke(h), e => e === sentinel);
      });
    }
    await t.test(action + ' pending registry result remains pending', async () => {
      let resolve!: (v: unknown) => void; let settled = false; const value = {};
      const pending = new Promise(r => { resolve = r; });
      const h = harness(action, stage => stage === 'preview' ? pending : absent);
      const result = invoke(h); void result.then(() => { settled = true; });
      await Promise.resolve(); await Promise.resolve(); assert.equal(settled, false);
      resolve(value); assert.equal(await result, value);
    });
    await t.test(action + ' reentrant independent callback', async () => {
      const nested = harness(action); let child!: Promise<unknown>;
      const h = harness(action, stage => { if (stage === 'preview') child = invoke(nested); return absent; });
      assert.equal(await invoke(h), h.value); assert.equal(await child, nested.value);
      assert.deepEqual(h.trace, ['body', 'preview']); assert.deepEqual(nested.trace, ['body', 'preview']);
    });
  }
  await t.test('interleaved bodies preserve per-request fields and actors', async () => {
    let resolveA!: (v: unknown) => void; let resolveB!: (v: unknown) => void;
    const a = harness('create', s => s === 'body' ? new Promise(r => { resolveA = r; }) : absent);
    const b = harness('update', s => s === 'body' ? new Promise(r => { resolveB = r; }) : absent);
    const pa = invoke(a); const pb = invoke(b);
    resolveB(b.input); assert.equal(await pb, b.value); assert.deepEqual(a.trace, ['body']);
    resolveA(a.input); assert.equal(await pa, a.value); assert.notEqual(a.actor, b.actor);
  });
  await t.test('same callback reentrant calls retain fresh field objects', async () => {
    const fields: unknown[] = []; let entered = false; let child!: Promise<unknown>;
    const h = harness('update', (stage, args) => {
      if (stage === 'preview') {
        fields.push(args[1]);
        if (!entered) { entered = true; child = invoke(h); }
      }
      return absent;
    });
    assert.equal(await invoke(h), h.value); assert.equal(await child, h.value);
    assert.equal(fields.length, 2); assert.notEqual(fields[0], fields[1]);
  });
  await t.test('same callback interleaved requests bind their own inputs and actors', async () => {
    const requestA = {}; const requestB = {}; const actorA = {}; const actorB = {};
    let resolveA!: (v: unknown) => void; let resolveB!: (v: unknown) => void;
    const records: unknown[][] = [];
    const h = harness('update', (stage, args) => {
      if (stage === 'body') return new Promise(r => { if (args[0] === requestA) resolveA = r; else { assert.equal(args[0], requestB); resolveB = r; } });
      if (stage === 'preview') records.push(args);
      return absent;
    });
    const pa = h.selected(h.registry, actorA, requestA); const pb = h.selected(h.registry, actorB, requestB);
    resolveB({ action: 'delete', id: 'b', revision: 2, cursor: 'cb' }); assert.equal(await pb, h.value);
    resolveA({ action: 'create', field: 'a', cursor: 'ca' }); assert.equal(await pa, h.value);
    assert.deepEqual(records, [[actorB, null, 'b', 2, 'cb'], [actorA, { field: 'a' }, undefined, undefined, 'ca']]);
  });
});
