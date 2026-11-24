import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct PUBLIC selected-declaration controls; historical65 remain frozen.
// Module/imports/initializers/neighbours/Kubernetes/HTTP/backend/recovery stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/lib/deployment-state.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), '4cc5bd9d3a53f0777839292504d7be172bac1324ef8c2f1ca16544536407a8a6');
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'eb25470584dd1c24ebf032bbb75d2d825e5f59b6e77e287eb6ace8e04a7a71f6');
const ast = ts.createSourceFile('deployment-state.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'deploymentPods');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword]);
assert.deepEqual(node.parameters.map(node => node.getText(ast)), ['deployment: any', 'pods: any[]', 'replicaSets: any[]']);
const declaration = node.getText(ast);
assert.equal(declaration, "export function deploymentPods(deployment: any, pods: any[], replicaSets: any[]) {\n  const namespace = deployment.metadata?.namespace, uid = deployment.metadata?.uid;\n  if (!uid) return [];\n  const owned = new Set(replicaSets.filter(rs => rs.metadata?.uid && rs.metadata?.namespace === namespace && rs.metadata?.ownerReferences?.some((owner: any) => owner.kind === \"Deployment\" && owner.uid === uid && owner.controller === true)).map(rs => rs.metadata.uid));\n  return pods.filter(pod => pod.metadata?.namespace === namespace && pod.metadata?.ownerReferences?.some((owner: any) => owner.kind === \"ReplicaSet\" && owner.controller === true && owned.has(owner.uid)));\n}");
assert.equal(digest(declaration), '9773c082683d1151eab6a46ff5d715c8774efcc641d16b8f743e99f150b1480a');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '42dfa81343593eebd903c522a4ba098c96300cde78ec3a23439bea696d7c2bed');
const selected = declaration.replace(/^export\s+/, '');
const compiled = ts.transpileModule(selected, { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const executable = compiled.outputText;
assert.ok(!executable.includes('import(') && !executable.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const select = (bindings = {}) => vm.runInNewContext(`${executable}\ndeploymentPods;`, bindings, { timeout: 1000 });
const owner = (kind = 'Deployment', uid = 'd', controller = true) => ({ kind, uid, controller });
const deployment = () => ({ metadata: { namespace: 'n', uid: 'd' } });
const rs = (uid = 'r', namespace = 'n', refs = [owner()]) => ({ metadata: { uid, namespace, ownerReferences: refs } });
const pod = (name = 'p', namespace = 'n', refs = [owner('ReplicaSet', 'r')]) => ({ metadata: { name, namespace, ownerReferences: refs } });
const identities = (actual, expected) => {
    assert.equal(actual.length, expected.length);
    expected.forEach((item, i) => assert.equal(actual[i], item));
};
const poison = (message = 'public synthetic stop') => Object.defineProperty({}, 'metadata', {
    get() { throw new Error(message); },
});
const throwsSame = (run, error) => assert.throws(run, e => e === error);
control('exact selected export accepts Pod -> ReplicaSet -> Deployment controller chain', () => {
    const p = pod();
    identities(select()(deployment(), [p], [rs()]), [p]);
});
control('labels alone never establish ownership and unrelated matching labels stay excluded', () => {
    const p = { metadata: { namespace: 'n', labels: { app: 'same' } } };
    identities(select()(deployment(), [p], [rs()]), []);
});
control('selection preserves Pod identity, order and duplicates without sorting', () => {
    const a = pod('z'), b = pod('a');
    identities(select()(deployment(), [b, a, b], [rs()]), [b, a, b]);
});
control('two owned ReplicaSets include both rollout generations without duplicate Pods', () => {
    const a = pod(), b = pod('b', 'n', [owner('ReplicaSet', 'r2')]);
    identities(select()(deployment(), [a, b], [rs(), rs('r2'), rs()]), [a, b]);
});
control('missing deployment UID returns a fresh array on every call before input access', () => {
    const f = select({ Set: class {
            constructor() { assert.fail('Set must remain inert'); }
        } });
    const a = f({}, poison(), poison()), b = f({}, poison(), poison());
    identities(a, []);
    identities(b, []);
    assert.notEqual(a, b);
});
for (const uid of [undefined, null, false, 0, '', NaN]) {
    control(`falsy deployment UID ${String(uid)} skips both arrays`, () => {
        identities(select()({ metadata: { namespace: 'n', uid } }, null, null), []);
    });
}
for (const d of [null, undefined]) {
    control(`nullish deployment ${String(d)} throws before arrays`, () => {
        assert.throws(() => select()(d, [], []), { name: 'TypeError' });
    });
}
control('deployment namespace precedes second fresh metadata UID read', () => {
    const log = [];
    let reads = 0;
    const d = { get metadata() {
            log.push(`metadata${++reads}`);
            return reads === 1 ?
                { get namespace() { log.push('namespace'); return 'n'; } } :
                { get uid() { log.push('uid'); return 'd'; } };
        } };
    identities(select()(d, [], []), []);
    assert.deepEqual(log, ['metadata1', 'namespace', 'metadata2', 'uid']);
});
control('first deployment metadata getter fault prevents all later reads', () => {
    const e = new Error('deployment getter');
    throwsSame(() => select()({ get metadata() { throw e; } }, [], []), e);
});
control('namespace getter error propagates before captured UID read', () => {
    const e = new Error('namespace');
    let reads = 0;
    const d = { get metadata() { reads++; return { get namespace() { throw e; } }; } };
    throwsSame(() => select()(d, [], []), e);
    assert.equal(reads, 1);
});
control('UID captured once is used even when synthetic deployment metadata later changes', () => {
    const d = deployment(), p = pod();
    const r = rs();
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
]) {
    control(`ReplicaSet refuses ${label}`, () => identities(select()(deployment(), [pod()], [r]), []));
}
for (const [label, p] of [
    ['absent metadata', {}], ['null metadata', { metadata: null }],
    ['different namespace', pod('x', 'other')], ['null owners', pod('x', 'n', null)],
    ['wrong kind', pod('x', 'n', [owner('Pod', 'r')])],
    ['unowned ReplicaSet', pod('x', 'n', [owner('ReplicaSet', 'foreign')])],
    ['direct Deployment owner', pod('x', 'n', [owner()])],
    ['false controller', pod('x', 'n', [owner('ReplicaSet', 'r', false)])],
    ['string controller', pod('x', 'n', [owner('ReplicaSet', 'r', 'true')])],
]) {
    control(`Pod refuses ${label}`, () => identities(select()(deployment(), [p], [rs()]), []));
}
control('strict namespace equality distinguishes string and number', () => {
    identities(select()({ metadata: { namespace: 1, uid: 'd' } }, [pod('x', '1')], [rs('r', 1)]), []);
});
control('strict owner UID equality distinguishes string and number', () => {
    identities(select()({ metadata: { namespace: 'n', uid: 1 } }, [pod()], [rs()]), []);
});
control('ReplicaSet some accepts later matching controller and stops before poison', () => {
    const bad = { get kind() { return assert.fail('later owner'); } };
    const p = pod();
    identities(select()(deployment(), [p], [rs('r', 'n', [owner('Other'), owner(), bad])]), [p]);
});
control('Pod some accepts later matching controller and stops before poison', () => {
    const bad = { get kind() { return assert.fail('later owner'); } };
    const p = pod('x', 'n', [owner('Other'), owner('ReplicaSet', 'r'), bad]);
    identities(select()(deployment(), [p], [rs()]), [p]);
});
control('ReplicaSet wrong kind skips UID and controller getters', () => {
    const o = { kind: 'Other', get uid() { return assert.fail('uid'); }, get controller() { return assert.fail('controller'); } };
    identities(select()(deployment(), [pod()], [rs('r', 'n', [o])]), []);
});
control('ReplicaSet wrong owner UID skips controller getter', () => {
    const o = { kind: 'Deployment', uid: 'other', get controller() { return assert.fail('controller'); } };
    identities(select()(deployment(), [], [rs('r', 'n', [o])]), []);
});
control('Pod wrong kind and false controller skip UID getter', () => {
    const o = { kind: 'Other', get controller() { return assert.fail('controller'); }, get uid() { return assert.fail('uid'); } };
    const q = { kind: 'ReplicaSet', controller: false, get uid() { return assert.fail('uid'); } };
    identities(select()(deployment(), [pod('x', 'n', [o, q])], [rs()]), []);
});
control('ReplicaSet falsy UID skips subsequent metadata reads', () => {
    let reads = 0;
    const r = { get metadata() { assert.equal(++reads, 1); return { uid: '' }; } };
    identities(select()(deployment(), [], [r]), []);
    assert.equal(reads, 1);
});
control('ReplicaSet namespace mismatch skips ownerReferences metadata read', () => {
    let reads = 0;
    const r = { get metadata() { assert.ok(++reads <= 2); return { uid: 'r', namespace: 'other' }; } };
    identities(select()(deployment(), [], [r]), []);
    assert.equal(reads, 2);
});
control('Pod namespace mismatch skips second metadata read', () => {
    let reads = 0;
    const p = { get metadata() { assert.equal(++reads, 1); return { namespace: 'other' }; } };
    identities(select()(deployment(), [p], [rs()]), []);
    assert.equal(reads, 1);
});
control('accepted ReplicaSet mapping rereads metadata UID after filter', () => {
    let reads = 0;
    const r = { get metadata() { reads++; return { uid: reads === 4 ? 'mapped' : 'r', namespace: 'n', ownerReferences: [owner()] }; } };
    const a = pod(), b = pod('b', 'n', [owner('ReplicaSet', 'mapped')]);
    identities(select()(deployment(), [a, b], [r]), [b]);
    assert.equal(reads, 4);
});
control('all ReplicaSet filtering and mapping finishes before Pod filter getter', () => {
    const log = [];
    const r = rs();
    Object.defineProperty(r.metadata, 'uid', { get() { log.push('rs uid'); return 'r'; } });
    const pods = { get filter() { log.push('pod filter'); return () => []; } };
    identities(select()(deployment(), pods, [r]), []);
    assert.deepEqual(log, ['rs uid', 'rs uid', 'pod filter']);
});
control('constructor consumes mapped iterable before Pod filter', () => {
    const log = [];
    class ImmediateSet extends Set {
        constructor(values) { log.push('construct'); super(values); }
        has(x) { log.push(`has ${String(x)}`); return super.has(x); }
    }
    const p = pod();
    identities(select({ Set: ImmediateSet })(deployment(), [p], [rs()]), [p]);
    assert.deepEqual(log, ['construct', 'has r']);
});
control('Set constructor failure prevents Pod array access', () => {
    const e = new Error('Set constructor');
    class ImmediateSet {
        constructor() { throw e; }
    }
    throwsSame(() => select({ Set: ImmediateSet })(deployment(), poison(), []), e);
});
control('owned.has error propagates only for a candidate controller Pod owner', () => {
    const e = new Error('Set has');
    class ImmediateSet {
        has() { throw e; }
    }
    throwsSame(() => select({ Set: ImmediateSet })(deployment(), [pod()], [rs()]), e);
});
control('Set has is skipped for false Pod controller', () => {
    class ImmediateSet {
        has() { return assert.fail('has'); }
    }
    identities(select({ Set: ImmediateSet })(deployment(), [pod('x', 'n', [owner('ReplicaSet', 'r', false)])], [rs()]), []);
});
for (const [label, input] of [['null', null], ['object', {}]]) {
    control(`malformed ReplicaSet array ${label} propagates TypeError before Pods`, () => assert.throws(() => select()(deployment(), poison(), input), { name: 'TypeError' }));
    control(`malformed Pod array ${label} propagates TypeError after ReplicaSets`, () => assert.throws(() => select()(deployment(), input, []), { name: 'TypeError' }));
}
control('ReplicaSet filter getter error propagates unchanged', () => {
    const e = new Error('filter');
    throwsSame(() => select()(deployment(), [], { get filter() { throw e; } }), e);
});
control('ReplicaSet map getter error propagates unchanged before Pods', () => {
    const e = new Error('map');
    throwsSame(() => select()(deployment(), [], { filter: () => ({ get map() { throw e; } }) }), e);
});
control('mapped iterable error propagates before Pods', () => {
    const e = new Error('iterator');
    const value = { get [Symbol.iterator]() { throw e; } };
    throwsSame(() => select()(deployment(), [], { filter: () => ({ map: () => value }) }), e);
});
control('Pod filter getter error propagates after Set creation', () => {
    const e = new Error('pod filter');
    throwsSame(() => select()(deployment(), { get filter() { throw e; } }, []), e);
});
control('null owner entries propagate TypeError rather than gaining ownership', () => {
    assert.throws(() => select()(deployment(), [], [rs('r', 'n', [null])]), { name: 'TypeError' });
    assert.throws(() => select()(deployment(), [pod('x', 'n', [null])], [rs()]), { name: 'TypeError' });
});
control('nonarray ownerReferences some binding error propagates', () => {
    assert.throws(() => select()(deployment(), [], [rs('r', 'n', {})]), { name: 'TypeError' });
    assert.throws(() => select()(deployment(), [pod('x', 'n', {})], [rs()]), { name: 'TypeError' });
});
control('sparse arrays skip holes and still preserve the surviving Pod identity', () => {
    const p = pod(), pods = Array(3), replicas = Array(3);
    pods[2] = p;
    replicas[1] = rs();
    identities(select()(deployment(), pods, replicas), [p]);
});
control('frozen public arrays and objects are read without mutation', () => {
    const p = Object.freeze(pod()), r = Object.freeze(rs()), d = Object.freeze(deployment());
    identities(select()(d, Object.freeze([p]), Object.freeze([r])), [p]);
});
control('successive calls have fresh ownership without caching', () => {
    const f = select(), p = pod();
    identities(f(deployment(), [p], [rs()]), [p]);
    identities(f(deployment(), [p], []), []);
});
assert.equal(count, 65);
