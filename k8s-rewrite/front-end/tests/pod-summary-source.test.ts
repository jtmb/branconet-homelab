import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire, stripTypeScriptTypes } from 'node:module';

// NEW finite source controls. Only this exact declaration executes; no module import.
// Synthetic Pod fields and an inert podRestarts binding; no services or credentials.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT || 'typescript');
const source = fs.readFileSync(new URL('../src/lib/pod-query.ts', import.meta.url), 'utf8');
const ast = ts.createSourceFile('pod-query.ts', source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((s: any) => ts.isFunctionDeclaration(s) && s.name?.text === 'podSummary');
assert.equal(selected.length, 1);
assert.equal(ast.parseDiagnostics.length, 0);
const declaration = selected[0].getText(ast);
assert.match(declaration, /^export function podSummary\(pod: any\)/);
const body = stripTypeScriptTypes(declaration.replace(/^export /, ''));
const instantiate = new Function('podRestarts', `${body}\nreturn podSummary;`) as (stub: (pod: any) => any) => (pod: any) => any;

function subject(value: any = 17) {
  const calls: any[] = [];
  const summarize = instantiate(pod => { calls.push(pod); return value; });
  return { summarize, calls };
}
function full() {
  return {
    metadata: { namespace: 'synthetic-ns', name: 'synthetic-pod', uid: 'synthetic-uid', creationTimestamp: '2026-01-01T00:00:00Z', labels: { app: 'synthetic' } },
    status: { phase: 'Running', containerStatuses: [{ ready: true }, { ready: false }], podIP: '192.0.2.10' },
    spec: { containers: [{ image: 'synthetic:a' }, { image: 'synthetic:b' }], nodeName: 'synthetic-node' },
  };
}

test('exact selected declaration has its sole immediate dependency supplied inertly', () => {
  const { summarize, calls } = subject(); const pod = full();
  assert.deepEqual(summarize(pod), { id: 'synthetic-uid', name: 'synthetic-pod', namespace: 'synthetic-ns', status: 'Running', ready: '1/2', restarts: 17, image: 'synthetic:a, synthetic:b', ip: '192.0.2.10', node: 'synthetic-node', created: '2026-01-01T00:00:00Z', labels: { app: 'synthetic' } });
  assert.equal(calls.length, 1); assert.equal(calls[0], pod);
});
test('output keys retain source object-literal order and exclude unrelated synthetic fields', () => {
  const pod: any = full(); pod.extra = 'unused'; pod.metadata.annotations = { example: 'unused' };
  assert.deepEqual(Object.keys(subject().summarize(pod)), ['id', 'name', 'namespace', 'status', 'ready', 'restarts', 'image', 'ip', 'node', 'created', 'labels']);
});
test('absent metadata/status/spec take source defaults', () => {
  assert.deepEqual(subject(0).summarize({}), { id: 'default/unknown', name: 'unknown', namespace: 'default', status: 'Unknown', ready: '0/0', restarts: 0, image: '-', ip: '-', node: '-', created: null, labels: {} });
});
for (const value of [undefined, null, false, 0, '']) {
  test(`falsey optional parent ${String(value)} follows defaults`, () => {
    const p = { metadata: value, status: value, spec: value };
    assert.equal(subject().summarize(p).id, 'default/unknown');
    assert.equal(subject().summarize(p).ready, '0/0');
  });
}
for (const value of [undefined, null, false, 0, '']) {
  test(`falsey field defaults ${String(value)}`, () => {
    const p = { metadata: { namespace: value, name: value, uid: value, labels: value, creationTimestamp: value }, status: { phase: value, podIP: value, containerStatuses: value }, spec: { nodeName: value, containers: value } };
    const got = subject().summarize(p);
    assert.deepEqual([got.id, got.name, got.namespace, got.status, got.ready, got.image, got.ip, got.node, got.created, got.labels], ['default/unknown', 'unknown', 'default', 'Unknown', '0/0', '-', '-', '-', null, {}]);
  });
}
for (const [namespace, name, expected] of [['ns', 'pod', 'ns/pod'], ['', 'pod', 'default/pod'], ['ns', '', 'ns/unknown'], ['', '', 'default/unknown']]) {
  test(`fallback identity captures namespace/name ${expected}`, () => assert.equal(subject().summarize({ metadata: { namespace, name } }).id, expected));
}
for (const phase of ['Pending', 'Running', 'Succeeded', 'Failed', 'Unknown']) {
  test(`nonempty phase ${phase} retained`, () => assert.equal(subject().summarize({ status: { phase } }).status, phase));
}
test('empty specified containers fall back to status count for denominator', () => {
  assert.equal(subject().summarize({ status: { containerStatuses: [{ ready: true }, { ready: false }, { ready: true }] }, spec: { containers: [] } }).ready, '2/3');
});
test('specified nonempty containers own denominator even with missing statuses', () => {
  assert.equal(subject().summarize({ spec: { containers: [{ image: 'one' }, { image: 'two' }] } }).ready, '0/2');
});
test('status readiness counts truthiness without calling dependency implementation', () => {
  assert.equal(subject().summarize({ status: { containerStatuses: [true, 1, 'yes', {}, false, 0, '', null, undefined].map(ready => ({ ready })) } }).ready, '4/9');
});
test('status entries without ready are falsey', () => assert.equal(subject().summarize({ status: { containerStatuses: [{}, { ready: true }] } }).ready, '1/2'));
test('container statuses never provide image projection', () => {
  assert.equal(subject().summarize({ status: { containerStatuses: [{ ready: true, image: 'unused' }] } }).image, '-');
});
for (const [images, expected] of [[[], '-'], [['one'], 'one'], [['one', 'two'], 'one, two'], [[undefined], '-'], [[null], '-'], [[undefined, 'two'], ', two'], [['', ''], ', ']] as [any[], string][]) {
  test(`image array join ${JSON.stringify(images)}`, () => assert.equal(subject().summarize({ spec: { containers: images.map(image => ({ image })) } }).image, expected));
}
test('labels retain exact reference, including synthetic inherited entries', () => {
  const labels = Object.assign(Object.create({ inherited: 'synthetic' }), { own: 'synthetic' });
  assert.equal(subject().summarize({ metadata: { labels } }).labels, labels);
});
test('falsey labels create separate empty objects per call', () => {
  const { summarize } = subject(); const a = summarize({}), b = summarize({});
  assert.notEqual(a.labels, b.labels); a.labels.synthetic = 'changed'; assert.deepEqual(b.labels, {});
});
test('frozen synthetic input is unchanged', () => {
  const p = full(); const before = structuredClone(p);
  function freeze(v: any) { if (v && typeof v === 'object') { for (const x of Object.values(v)) freeze(x); Object.freeze(v); } }
  freeze(p); subject().summarize(p); assert.deepEqual(p, before);
});
for (const value of [0, 7, null, undefined, 'synthetic', { synthetic: true }]) {
  test(`inert restarts return retained ${JSON.stringify(value)}`, () => {
    const calls: any[] = []; const summarize = instantiate(p => { calls.push(p); return value; }); const p = {};
    assert.equal(summarize(p).restarts, value); assert.equal(calls.length, 1); assert.equal(calls[0], p);
  });
}

const expectedTrace = ['pod.metadata', 'metadata.namespace', 'pod.metadata', 'metadata.name', 'pod.status', 'status.containerStatuses', 'pod.spec', 'spec.containers', 'pod.metadata', 'metadata.uid', 'pod.status', 'status.phase', 'status0.ready', 'status1.ready', 'podRestarts', 'container0.image', 'container1.image', 'pod.status', 'status.podIP', 'pod.spec', 'spec.nodeName', 'pod.metadata', 'metadata.creationTimestamp', 'pod.metadata', 'metadata.labels'];
function traced(cut = -1) {
  const trace: string[] = [], fault = new Error('synthetic getter or inert dependency fault');
  const read = (name: string, value: any) => { trace.push(name); if (trace.length - 1 === cut) throw fault; return value; };
  // Define ordinary own getters; callbacks exercise only supplied synthetic data.
  const wrap = (name: string, values: Record<string, any>) => {
    const result: Record<string, any> = {};
    for (const [key, value] of Object.entries(values)) Object.defineProperty(result, key, { enumerable: true, get: () => read(`${name}.${key}`, value) });
    return result;
  };
  const metadata = wrap('metadata', { namespace: 'ns', name: 'pod', uid: 'uid', creationTimestamp: 'created', labels: {} });
  const status = wrap('status', { containerStatuses: [wrap('status0', { ready: true }), wrap('status1', { ready: false })], phase: 'Running', podIP: '192.0.2.1' });
  const spec = wrap('spec', { containers: [wrap('container0', { image: 'one' }), wrap('container1', { image: 'two' })], nodeName: 'node' });
  const pod = wrap('pod', { metadata, status, spec });
  const summarize = instantiate(p => { assert.equal(p, pod); return read('podRestarts', 23); });
  return { trace, fault, pod, summarize };
}
test('all observed reads match recorded source order', () => {
  const x = traced(); assert.equal(x.summarize(x.pod).ready, '1/2'); assert.deepEqual(x.trace, expectedTrace);
});
for (let cut = 0; cut < expectedTrace.length; cut++) {
  test(`synthetic fault stops at ordered read ${cut} ${expectedTrace[cut]}`, () => {
    const x = traced(cut); assert.throws(() => x.summarize(x.pod), error => error === x.fault); assert.deepEqual(x.trace, expectedTrace.slice(0, cut + 1));
  });
}
test('independent fresh metadata reads preserve captured namespace/name', () => {
  const sequence = [{ namespace: 'first' }, { name: 'second' }, { uid: '' }, { creationTimestamp: 'fourth' }, { labels: { fifth: 'synthetic' } }];
  let reads = 0; const p = { get metadata() { return sequence[reads++]; } };
  const got = subject().summarize(p); assert.equal(reads, 5); assert.equal(got.id, 'first/second'); assert.equal(got.created, 'fourth'); assert.deepEqual(got.labels, { fifth: 'synthetic' });
});
test('independent fresh status reads preserve captured statuses', () => {
  const sequence = [{ containerStatuses: [{ ready: true }] }, { phase: 'Pending' }, { podIP: '192.0.2.99' }];
  let reads = 0; const got = subject().summarize({ get status() { return sequence[reads++]; } });
  assert.equal(reads, 3); assert.deepEqual([got.status, got.ready, got.ip], ['Pending', '1/1', '192.0.2.99']);
});
test('independent fresh spec reads preserve captured containers', () => {
  const sequence = [{ containers: [{ image: 'first' }] }, { nodeName: 'second' }]; let reads = 0;
  const got = subject().summarize({ get spec() { return sequence[reads++]; } });
  assert.equal(reads, 2); assert.equal(got.image, 'first'); assert.equal(got.node, 'second');
});
test('dependency-time changes affect only later reads of captured references and fresh parents', () => {
  const p = full(); const summarize = instantiate(q => { q.status.phase = 'Failed'; q.status.podIP = '192.0.2.20'; q.spec.containers[0].image = 'changed'; q.spec.nodeName = 'changed-node'; q.metadata.labels = { changed: 'synthetic' }; return 9; });
  const got = summarize(p); assert.equal(got.status, 'Running'); assert.equal(got.ready, '1/2'); assert.equal(got.ip, '192.0.2.20'); assert.equal(got.image, 'changed, synthetic:b'); assert.equal(got.node, 'changed-node'); assert.deepEqual(got.labels, { changed: 'synthetic' });
});
for (const p of [null, undefined]) {
  test(`nullish root ${p} refuses before inert dependency`, () => { const x = subject(); assert.throws(() => x.summarize(p), TypeError); assert.equal(x.calls.length, 0); });
}
for (const malformed of [{}, 'synthetic', 1, true]) {
  test(`truthy malformed statuses ${JSON.stringify(malformed)} characterize JS refusal`, () => {
    const x = subject(); assert.throws(() => x.summarize({ status: { containerStatuses: malformed } }), TypeError); assert.equal(x.calls.length, 0);
  });
}
test('null status entry refuses during ready callback before dependency', () => {
  const x = subject(); assert.throws(() => x.summarize({ status: { containerStatuses: [null] } }), TypeError); assert.equal(x.calls.length, 0);
});
test('null container entry refuses during image callback after dependency', () => {
  const x = subject(); assert.throws(() => x.summarize({ spec: { containers: [null] } }), TypeError); assert.equal(x.calls.length, 1);
});
test('sparse synthetic arrays preserve filter/map semantics', () => {
  const statuses = new Array(3); statuses[1] = { ready: true }; const containers = new Array(3); containers[1] = { image: 'middle' };
  const got = subject().summarize({ status: { containerStatuses: statuses }, spec: { containers } }); assert.equal(got.ready, '1/3'); assert.equal(got.image, ', middle, ');
});
test('ready method and denominator length precede dependency and image methods', () => {
  const trace: string[] = [];
  const statuses = { filter(fn: (v: any) => boolean) { trace.push('filter'); assert.equal(fn({ ready: true }), true); return { get length() { trace.push('filtered.length'); return 2; } }; }, get length() { trace.push('statuses.length'); return 3; } };
  const containers = { get length() { trace.push('containers.length'); return 0; }, map(fn: (v: any) => any) { trace.push('map'); assert.equal(fn({ image: 'one' }), 'one'); return { join(separator: string) { trace.push('join'); assert.equal(separator, ', '); return 'one'; } }; } };
  const summarize = instantiate(() => { trace.push('dependency'); return 4; });
  assert.equal(summarize({ status: { containerStatuses: statuses }, spec: { containers } }).ready, '2/3');
  assert.deepEqual(trace, ['filter', 'filtered.length', 'containers.length', 'statuses.length', 'dependency', 'map', 'join']);
});
test('nonzero denominator avoids fallback statuses.length', () => {
  const statuses = { filter() { return []; }, get length() { throw new Error('must shortcircuit'); } };
  assert.equal(subject().summarize({ status: { containerStatuses: statuses }, spec: { containers: [{ image: 'one' }] } }).ready, '0/1');
});
