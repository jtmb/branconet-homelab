import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire, stripTypeScriptTypes } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

// PUBLIC SOURCE only: select one declaration, never import the production module.
// Source order was recorded before these finite controls were authored.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!) as typeof import('typescript');
const source = readFileSync(path.resolve('src/lib/deployment-state.ts'), 'utf8');
const ast = ts.createSourceFile('deployment-state.ts', source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((node): node is import('typescript').FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === 'deploymentPods' &&
  !!node.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(declarations.length, 1);
const selected = declarations[0].getText(ast).replace(/^export\s+/, '');
const executable = stripTypeScriptTypes(selected, { mode: 'strip' });
type Metadata = Record<string, unknown>;
type Item = { metadata?: Metadata; [key: string]: unknown };
type Selector = (deployment: unknown, pods: unknown, replicaSets: unknown) => Item[];
const select = (bindings: Record<string, unknown> = {}): Selector =>
  vm.runInNewContext(`${executable}\ndeploymentPods;`, bindings, { timeout: 1000 });
const owner = (kind = 'Deployment', uid: unknown = 'd', controller: unknown = true) => ({ kind, uid, controller });
const deployment = () => ({ metadata: { namespace: 'n', uid: 'd' } });
const rs = (uid: unknown = 'r', namespace: unknown = 'n', refs: unknown = [owner()]) =>
  ({ metadata: { uid, namespace, ownerReferences: refs } });
const pod = (name = 'p', namespace: unknown = 'n', refs: unknown = [owner('ReplicaSet', 'r')]) =>
  ({ metadata: { name, namespace, ownerReferences: refs } });
const identities = (actual: Item[], expected: Item[]) => {
  assert.equal(actual.length, expected.length);
  expected.forEach((item, i) => assert.equal(actual[i], item));
};
const poison = (message = 'public synthetic stop') => Object.defineProperty({}, 'metadata', {
  get(): never { throw new Error(message); },
});
const throwsSame = (run: () => unknown, error: Error) => assert.throws(run, e => e === error);

test('exact selected export accepts Pod -> ReplicaSet -> Deployment controller chain', () => {
  const p = pod(); identities(select()(deployment(), [p], [rs()]), [p]);
});
test('labels alone never establish ownership and unrelated matching labels stay excluded', () => {
  const p = { metadata: { namespace: 'n', labels: { app: 'same' } } };
  identities(select()(deployment(), [p], [rs()]), []);
});
test('selection preserves Pod identity, order and duplicates without sorting', () => {
  const a = pod('z'), b = pod('a'); identities(select()(deployment(), [b, a, b], [rs()]), [b, a, b]);
});
test('two owned ReplicaSets include both rollout generations without duplicate Pods', () => {
  const a = pod(), b = pod('b', 'n', [owner('ReplicaSet', 'r2')]);
  identities(select()(deployment(), [a, b], [rs(), rs('r2'), rs()]), [a, b]);
});
test('missing deployment UID returns a fresh array on every call before input access', () => {
  const f = select({ Set: class { constructor() { assert.fail('Set must remain inert'); } } });
  const a = f({}, poison(), poison()), b = f({}, poison(), poison());
  identities(a, []); identities(b, []); assert.notEqual(a, b);
});
for (const uid of [undefined, null, false, 0, '', NaN]) {
  test(`falsy deployment UID ${String(uid)} skips both arrays`, () => {
    identities(select()({ metadata: { namespace: 'n', uid } }, null, null), []);
  });
}
for (const d of [null, undefined]) {
  test(`nullish deployment ${String(d)} throws before arrays`, () => {
    assert.throws(() => select()(d, [], []), { name: 'TypeError' });
  });
}
test('deployment namespace precedes second fresh metadata UID read', () => {
  const log: string[] = []; let reads = 0;
  const d = { get metadata() { log.push(`metadata${++reads}`); return reads === 1 ?
    { get namespace() { log.push('namespace'); return 'n'; } } :
    { get uid() { log.push('uid'); return 'd'; } }; } };
  identities(select()(d, [], []), []);
  assert.deepEqual(log, ['metadata1', 'namespace', 'metadata2', 'uid']);
});
test('first deployment metadata getter fault prevents all later reads', () => {
  const e = new Error('deployment getter'); throwsSame(() => select()({ get metadata(): never { throw e; } }, [], []), e);
});
test('namespace getter error propagates before captured UID read', () => {
  const e = new Error('namespace'); let reads = 0;
  const d = { get metadata() { reads++; return { get namespace(): never { throw e; } }; } };
  throwsSame(() => select()(d, [], []), e); assert.equal(reads, 1);
});
test('UID captured once is used even when synthetic deployment metadata later changes', () => {
  const d = deployment(), p = pod(); const r = rs();
  Object.defineProperty(r.metadata, 'uid', { get() { d.metadata.uid = 'different'; return 'r'; } });
  identities(select()(d, [p], [r]), [p]);
});
for (const [label, r] of [
  ['absent metadata', {}], ['null metadata', { metadata: null }],
  ['falsy uid', rs('')], ['different namespace', rs('r', 'other')],
  ['missing owners', { metadata: { uid: 'r', namespace: 'n' } }], ['null owners', rs('r', 'n', null)],
  ['wrong kind', rs('r', 'n', [owner('deployment')])],
  ['wrong deployment uid', rs('r', 'n', [owner('Deployment', 'other')])],
  ['noncontroller', rs('r', 'n', [owner('Deployment', 'd', false)])],
  ['truthy nonboolean controller', rs('r', 'n', [owner('Deployment', 'd', 1)])],
] as const) {
  test(`ReplicaSet refuses ${label}`, () => identities(select()(deployment(), [pod()], [r]), []));
}
for (const [label, p] of [
  ['absent metadata', {}], ['null metadata', { metadata: null }],
  ['different namespace', pod('x', 'other')], ['null owners', pod('x', 'n', null)],
  ['wrong kind', pod('x', 'n', [owner('Pod', 'r')])],
  ['unowned ReplicaSet', pod('x', 'n', [owner('ReplicaSet', 'foreign')])],
  ['direct Deployment owner', pod('x', 'n', [owner()])],
  ['false controller', pod('x', 'n', [owner('ReplicaSet', 'r', false)])],
  ['string controller', pod('x', 'n', [owner('ReplicaSet', 'r', 'true')])],
] as const) {
  test(`Pod refuses ${label}`, () => identities(select()(deployment(), [p], [rs()]), []));
}
test('strict namespace equality distinguishes string and number', () => {
  identities(select()({ metadata: { namespace: 1, uid: 'd' } }, [pod('x', '1')], [rs('r', 1)]), []);
});
test('strict owner UID equality distinguishes string and number', () => {
  identities(select()({ metadata: { namespace: 'n', uid: 1 } }, [pod()], [rs()]), []);
});
test('ReplicaSet some accepts later matching controller and stops before poison', () => {
  const bad = { get kind(): never { return assert.fail('later owner'); } };
  const p = pod(); identities(select()(deployment(), [p], [rs('r', 'n', [owner('Other'), owner(), bad])]), [p]);
});
test('Pod some accepts later matching controller and stops before poison', () => {
  const bad = { get kind(): never { return assert.fail('later owner'); } };
  const p = pod('x', 'n', [owner('Other'), owner('ReplicaSet', 'r'), bad]);
  identities(select()(deployment(), [p], [rs()]), [p]);
});
test('ReplicaSet wrong kind skips UID and controller getters', () => {
  const o = { kind: 'Other', get uid(): never { return assert.fail('uid'); }, get controller(): never { return assert.fail('controller'); } };
  identities(select()(deployment(), [pod()], [rs('r', 'n', [o])]), []);
});
test('ReplicaSet wrong owner UID skips controller getter', () => {
  const o = { kind: 'Deployment', uid: 'other', get controller(): never { return assert.fail('controller'); } };
  identities(select()(deployment(), [], [rs('r', 'n', [o])]), []);
});
test('Pod wrong kind and false controller skip UID getter', () => {
  const o = { kind: 'Other', get controller(): never { return assert.fail('controller'); }, get uid(): never { return assert.fail('uid'); } };
  const q = { kind: 'ReplicaSet', controller: false, get uid(): never { return assert.fail('uid'); } };
  identities(select()(deployment(), [pod('x', 'n', [o, q])], [rs()]), []);
});
test('ReplicaSet falsy UID skips subsequent metadata reads', () => {
  let reads = 0; const r = { get metadata() { assert.equal(++reads, 1); return { uid: '' }; } };
  identities(select()(deployment(), [], [r]), []); assert.equal(reads, 1);
});
test('ReplicaSet namespace mismatch skips ownerReferences metadata read', () => {
  let reads = 0; const r = { get metadata() { assert.ok(++reads <= 2); return { uid: 'r', namespace: 'other' }; } };
  identities(select()(deployment(), [], [r]), []); assert.equal(reads, 2);
});
test('Pod namespace mismatch skips second metadata read', () => {
  let reads = 0; const p = { get metadata() { assert.equal(++reads, 1); return { namespace: 'other' }; } };
  identities(select()(deployment(), [p], [rs()]), []); assert.equal(reads, 1);
});
test('accepted ReplicaSet mapping rereads metadata UID after filter', () => {
  let reads = 0; const r = { get metadata() { reads++; return { uid: reads === 4 ? 'mapped' : 'r', namespace: 'n', ownerReferences: [owner()] }; } };
  const a = pod(), b = pod('b', 'n', [owner('ReplicaSet', 'mapped')]);
  identities(select()(deployment(), [a, b], [r]), [b]); assert.equal(reads, 4);
});
test('all ReplicaSet filtering and mapping finishes before Pod filter getter', () => {
  const log: string[] = []; const r = rs();
  Object.defineProperty(r.metadata, 'uid', { get() { log.push('rs uid'); return 'r'; } });
  const pods = { get filter() { log.push('pod filter'); return () => []; } };
  identities(select()(deployment(), pods, [r]), []); assert.deepEqual(log, ['rs uid', 'rs uid', 'pod filter']);
});
test('constructor consumes mapped iterable before Pod filter', () => {
  const log: string[] = [];
  class ImmediateSet extends Set<unknown> { constructor(values: Iterable<unknown>) { log.push('construct'); super(values); } has(x: unknown) { log.push(`has ${String(x)}`); return super.has(x); } }
  const p = pod(); identities(select({ Set: ImmediateSet })(deployment(), [p], [rs()]), [p]);
  assert.deepEqual(log, ['construct', 'has r']);
});
test('Set constructor failure prevents Pod array access', () => {
  const e = new Error('Set constructor'); class ImmediateSet { constructor() { throw e; } }
  throwsSame(() => select({ Set: ImmediateSet })(deployment(), poison(), []), e);
});
test('owned.has error propagates only for a candidate controller Pod owner', () => {
  const e = new Error('Set has'); class ImmediateSet { has(): never { throw e; } }
  throwsSame(() => select({ Set: ImmediateSet })(deployment(), [pod()], [rs()]), e);
});
test('Set has is skipped for false Pod controller', () => {
  class ImmediateSet { has(): never { return assert.fail('has'); } }
  identities(select({ Set: ImmediateSet })(deployment(), [pod('x', 'n', [owner('ReplicaSet', 'r', false)])], [rs()]), []);
});
for (const [label, input] of [['null', null], ['object', {}]] as const) {
  test(`malformed ReplicaSet array ${label} propagates TypeError before Pods`, () => assert.throws(() => select()(deployment(), poison(), input), { name: 'TypeError' }));
  test(`malformed Pod array ${label} propagates TypeError after ReplicaSets`, () => assert.throws(() => select()(deployment(), input, []), { name: 'TypeError' }));
}
test('ReplicaSet filter getter error propagates unchanged', () => {
  const e = new Error('filter'); throwsSame(() => select()(deployment(), [], { get filter(): never { throw e; } }), e);
});
test('ReplicaSet map getter error propagates unchanged before Pods', () => {
  const e = new Error('map'); throwsSame(() => select()(deployment(), [], { filter: () => ({ get map(): never { throw e; } }) }), e);
});
test('mapped iterable error propagates before Pods', () => {
  const e = new Error('iterator'); const value = { get [Symbol.iterator](): never { throw e; } };
  throwsSame(() => select()(deployment(), [], { filter: () => ({ map: () => value }) }), e);
});
test('Pod filter getter error propagates after Set creation', () => {
  const e = new Error('pod filter'); throwsSame(() => select()(deployment(), { get filter(): never { throw e; } }, []), e);
});
test('null owner entries propagate TypeError rather than gaining ownership', () => {
  assert.throws(() => select()(deployment(), [], [rs('r', 'n', [null])]), { name: 'TypeError' });
  assert.throws(() => select()(deployment(), [pod('x', 'n', [null])], [rs()]), { name: 'TypeError' });
});
test('nonarray ownerReferences some binding error propagates', () => {
  assert.throws(() => select()(deployment(), [], [rs('r', 'n', {})]), { name: 'TypeError' });
  assert.throws(() => select()(deployment(), [pod('x', 'n', {})], [rs()]), { name: 'TypeError' });
});
test('sparse arrays skip holes and still preserve the surviving Pod identity', () => {
  const p = pod(), pods = Array<Item>(3), replicas = Array<Item>(3); pods[2] = p; replicas[1] = rs();
  identities(select()(deployment(), pods, replicas), [p]);
});
test('frozen public arrays and objects are read without mutation', () => {
  const p = Object.freeze(pod()), r = Object.freeze(rs()), d = Object.freeze(deployment());
  identities(select()(d, Object.freeze([p]), Object.freeze([r])), [p]);
});
test('successive calls have fresh ownership without caching', () => {
  const f = select(), p = pod(); identities(f(deployment(), [p], [rs()]), [p]); identities(f(deployment(), [p], []), []);
});
