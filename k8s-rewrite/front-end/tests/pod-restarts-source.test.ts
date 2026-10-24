import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire, stripTypeScriptTypes } from 'node:module';

// NEW finite PUBLIC SOURCE controls. Only this declaration executes.
// Actual count, neighbors, configuration, credentials and services remain inert.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT || 'typescript');
const source = fs.readFileSync(new URL('../src/lib/deployment-state.ts', import.meta.url), 'utf8');
const ast = ts.createSourceFile('deployment-state.ts', source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((s: any) => ts.isFunctionDeclaration(s) && s.name?.text === 'podRestarts');
assert.equal(selected.length, 1);
assert.equal(ast.parseDiagnostics.length, 0);
const declaration = selected[0].getText(ast);
assert.match(declaration, /^export function podRestarts\(pod: any\): number/);
const body = stripTypeScriptTypes(declaration.replace(/^export /, ''));
const instantiate = new Function('count', `${body}\nreturn podRestarts;`) as (stub: (value: any) => any) => (pod: any) => any;
function subject(values: any[] = []) {
  const calls: any[] = [];
  const restarts = instantiate(value => { const i = calls.length; calls.push(value); return values[i] ?? 0; });
  return { restarts, calls };
}
const pod = (regular: any, init: any) => ({ status: { containerStatuses: regular, initContainerStatuses: init } });

test('selected declaration supplies its sole dependency inertly', () => {
  const x = subject([3, 5, 7]);
  assert.equal(x.restarts(pod([{ restartCount: 'regular-a' }, { restartCount: 'regular-b' }], [{ restartCount: 'init' }])), 15);
  assert.deepEqual(x.calls, ['regular-a', 'regular-b', 'init']);
});
test('absent status returns zero without dependency calls', () => {
  const x = subject(); assert.equal(x.restarts({}), 0); assert.deepEqual(x.calls, []);
});
for (const value of [undefined, null, false, 0, '', NaN]) {
  test(`falsey status ${String(value)} has no entries`, () => {
    const x = subject(); assert.equal(x.restarts({ status: value }), 0); assert.deepEqual(x.calls, []);
  });
  test(`falsey regular and init arrays ${String(value)} use empty fallbacks`, () => {
    const x = subject(); assert.equal(x.restarts(pod(value, value)), 0); assert.deepEqual(x.calls, []);
  });
}
for (const value of [null, undefined]) {
  test(`unguarded nullish pod ${String(value)} propagates TypeError`, () => {
    const x = subject(); assert.throws(() => x.restarts(value), TypeError); assert.deepEqual(x.calls, []);
  });
}
for (const [a, b, expected] of [[[], [], 0], [[0], [], 2], [[], [0], 2], [[0, 1], [2, 3], 20]] as [number[], number[], number][]) {
  test(`regular/init cardinality ${a.length}/${b.length}`, () => {
    const all = [...a, ...b]; const x = subject(all.map(n => (n + 1) * 2));
    assert.equal(x.restarts(pod(a.map(restartCount => ({ restartCount })), b.map(restartCount => ({ restartCount })))), expected);
    assert.deepEqual(x.calls, all);
  });
}
test('raw values reach inert dependency without source coercion', () => {
  const values = [undefined, null, false, 0, '', '7', NaN, Infinity, -1, 1.5, { synthetic: true }];
  const x = subject(values.map(() => 1));
  assert.equal(x.restarts(pod(values.map(restartCount => ({ restartCount })), [])), values.length);
  assert.deepEqual(x.calls, values);
});
test('dependency returns participate in JavaScript addition without extra validation', () => {
  const x = subject([2, '3', 4]); assert.equal(x.restarts(pod([{}, {}, {}], [])), '234');
});
test('dependency NaN remains NaN', () => {
  const restarts = instantiate(() => NaN); assert.ok(Number.isNaN(restarts(pod([{}], []))));
});
test('both status reads are fresh and select independent objects', () => {
  const values = [{ containerStatuses: [{ restartCount: 'first' }] }, { initContainerStatuses: [{ restartCount: 'second' }] }];
  let reads = 0; const x = subject([4, 6]);
  assert.equal(x.restarts({ get status() { return values[reads++]; } }), 10);
  assert.equal(reads, 2); assert.deepEqual(x.calls, ['first', 'second']);
});
test('inherited synthetic status fields and entry fields are read', () => {
  const entry = Object.create({ restartCount: 'inherited' });
  const p = Object.create({ status: Object.create({ containerStatuses: [entry], initContainerStatuses: [] }) });
  const x = subject([9]); assert.equal(x.restarts(p), 9); assert.deepEqual(x.calls, ['inherited']);
});
test('iterable status collections preserve their order', () => {
  const x = subject([2, 3, 5]);
  assert.equal(x.restarts(pod(new Set([{ restartCount: 'a' }, { restartCount: 'b' }]), new Set([{ restartCount: 'c' }]))), 10);
  assert.deepEqual(x.calls, ['a', 'b', 'c']);
});
test('string iterable entries expose undefined restartCount', () => {
  const x = subject([1, 2, 3]); assert.equal(x.restarts(pod('ab', 'c')), 6); assert.deepEqual(x.calls, [undefined, undefined, undefined]);
});
for (const value of [true, 1, {}, { length: 1 }, { [Symbol.iterator]: 3 }]) {
  for (const side of ['regular', 'init']) {
    test(`truthy noniterable ${side} ${JSON.stringify(value)} propagates before reduction`, () => {
      const x = subject(); const regular = side === 'regular' ? value : [{ restartCount: 'unused' }];
      assert.throws(() => x.restarts(pod(regular, side === 'init' ? value : [])), TypeError); assert.deepEqual(x.calls, []);
    });
  }
}
for (const entry of [null, undefined]) {
  test(`nullish captured entry ${String(entry)} refuses at entry read`, () => {
    const x = subject([1]); assert.throws(() => x.restarts(pod([{ restartCount: 'first' }, entry], [])), TypeError); assert.deepEqual(x.calls, ['first']);
  });
}
test('spread materializes array holes as undefined entries', () => {
  const x = subject(); assert.throws(() => x.restarts(pod(new Array(1), [])), TypeError); assert.deepEqual(x.calls, []);
});
test('array collection reduce overrides are never used', () => {
  const regular: any = [{ restartCount: 'a' }]; const init: any = [{ restartCount: 'b' }];
  Object.defineProperty(regular, 'reduce', { get() { throw new Error('unused'); } });
  Object.defineProperty(init, 'reduce', { get() { throw new Error('unused'); } });
  const x = subject([4, 5]); assert.equal(x.restarts(pod(regular, init)), 9); assert.deepEqual(x.calls, ['a', 'b']);
});
test('frozen synthetic inputs stay unchanged', () => {
  const p = pod([Object.freeze({ restartCount: 1 })], [Object.freeze({ restartCount: 2 })]);
  Object.freeze(p.status.containerStatuses); Object.freeze(p.status.initContainerStatuses); Object.freeze(p.status); Object.freeze(p);
  const before = structuredClone(p); assert.equal(subject([3, 4]).restarts(p), 7); assert.deepEqual(p, before);
});
test('captured entry membership is stable while later field reads remain fresh', () => {
  const second = { restartCount: 'before' }; const regular = [{ restartCount: 'first' }, second]; const init = [{ restartCount: 'init' }]; const calls: any[] = [];
  const restarts = instantiate(value => { calls.push(value); if (calls.length === 1) { second.restartCount = 'after'; regular.push({ restartCount: 'not-captured' }); init.length = 0; } return 1; });
  assert.equal(restarts(pod(regular, init)), 3); assert.deepEqual(calls, ['first', 'after', 'init']);
});
test('all iteration completes before count reads begin', () => {
  const entry = { restartCount: 'old' }; const trace: string[] = [];
  const init = { *[Symbol.iterator]() { trace.push('init starts'); entry.restartCount = 'updated'; yield { restartCount: 'init' }; trace.push('init ends'); } };
  const restarts = instantiate(value => { trace.push(value); return 1; });
  assert.equal(restarts(pod([entry], init)), 2); assert.deepEqual(trace, ['init starts', 'init ends', 'updated', 'init']);
});
const expectedTrace = ['pod.status:0', 'regular.field', 'regular.iterator', 'regular.next:0', 'regular.next:1', 'regular.next:2', 'pod.status:1', 'init.field', 'init.iterator', 'init.next:0', 'init.next:1', 'regular0.restartCount', 'count:0', 'regular1.restartCount', 'count:1', 'init0.restartCount', 'count:2'];
function traced(cut = -1) {
  const trace: string[] = []; const fault = new Error('synthetic ordered fault');
  const read = (name: string, value: any) => { trace.push(name); if (trace.length - 1 === cut) throw fault; return value; };
  const entry = (name: string) => ({ get restartCount() { return read(`${name}.restartCount`, name); } });
  const iterable = (name: string, values: any[]) => ({ [Symbol.iterator]() { read(`${name}.iterator`, null); let i = 0; return { next() { read(`${name}.next:${i}`, null); return i < values.length ? { value: values[i++], done: false } : { done: true }; } }; } });
  const regular = iterable('regular', [entry('regular0'), entry('regular1')]); const init = iterable('init', [entry('init0')]);
  const status = { get containerStatuses() { return read('regular.field', regular); }, get initContainerStatuses() { return read('init.field', init); } };
  let statusReads = 0, calls = 0;
  const p = { get status() { return read(`pod.status:${statusReads++}`, status); } };
  const restarts = instantiate(value => { const i = calls++; assert.equal(value, ['regular0', 'regular1', 'init0'][i]); return read(`count:${i}`, i + 1); });
  return { trace, fault, p, restarts };
}
test('recorded source-derived iteration/getter/dependency order is exact', () => {
  const x = traced(); assert.equal(x.restarts(x.p), 6); assert.deepEqual(x.trace, expectedTrace);
});
for (let cut = 0; cut < expectedTrace.length; cut++) {
  test(`ordered failure stops at ${cut} ${expectedTrace[cut]}`, () => {
    const x = traced(cut); assert.throws(() => x.restarts(x.p), error => error === x.fault); assert.deepEqual(x.trace, expectedTrace.slice(0, cut + 1));
  });
}
test('addition coercion fault propagates before later entry reads', () => {
  const fault = new Error('synthetic coercion'); let later = 0;
  const restarts = instantiate(() => ({ [Symbol.toPrimitive]() { throw fault; } }));
  assert.throws(() => restarts(pod([{}, { get restartCount() { later++; return 1; } }], [])), error => error === fault); assert.equal(later, 0);
});
test('repeated calls keep no captured membership or accumulator state', () => {
  let calls = 0; const restarts = instantiate(() => ++calls);
  assert.equal(restarts(pod([{}], [])), 1); assert.equal(restarts({}), 0); assert.equal(restarts(pod([], [{}])), 2); assert.equal(calls, 2);
});
