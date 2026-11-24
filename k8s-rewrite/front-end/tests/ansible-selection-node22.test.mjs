import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// PUBLIC declaration only; no historical test or application module is imported.
const ts = createRequire(import.meta.url)('typescript');
assert.equal(process.version, 'v22.23.3'); assert.equal(ts.version, '5.9.3');
const raw = readFileSync(new URL('../src/lib/ansible-selection.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
const digest = value => createHash('sha256').update(value).digest('hex');
assert.equal(digest(source), 'a5c7d23d4ab751ae5ea56146b2afbd5b2aec43a5fbee73e56db131fe01a76ead');
// Also bind the historical Windows CRLF authority, without relaxing either hash.
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'bb82df683d0e157b7e1bdec77a169b22a6fdf41c3e50ecc3b75304b8dd195fab');
const ast = ts.createSourceFile('ansible-selection.ts', source, ts.ScriptTarget.ES2022, true);
assert.equal(ast.parseDiagnostics.length, 0);
const nodes = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'ansibleSelection');
assert.equal(nodes.length, 1);
assert.equal(nodes[0].modifiers.filter(node => node.kind === ts.SyntaxKind.ExportKeyword).length, 1);
const selected = nodes[0].getText(ast);
assert.equal(selected, `export function ansibleSelection(playbook: unknown = "site.yml", roles: unknown = []) {
  if (playbook !== "site.yml" || !Array.isArray(roles) || roles.length > ANSIBLE_ROLES.length
      || roles.some(role => typeof role !== "string" || !(ANSIBLE_ROLES as readonly string[]).includes(role))
      || new Set(roles).size !== roles.length) throw new AnsibleSelectionError();
  return { playbook: "site.yml", roles: roles as AnsibleRole[] };
}`);
const emitted = ts.transpileModule(selected.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(emitted.diagnostics.length, 0);
const roles = Object.freeze(['bootstrap', 'kubernetes', 'network', 'dns', 'storage', 'longhorn', 'nfs', 'samba', 'ingress', 'gitops', 'secrets']);
class PublicRefusal extends Error { constructor() { super('Use site.yml and the supported provisioning roles'); } }
function bind(overrides = {}) {
  return vm.runInNewContext(`${emitted.outputText}\nansibleSelection;`, {
    ANSIBLE_ROLES: roles, Array, Set, AnsibleSelectionError: PublicRefusal, ...overrides,
  }, { timeout: 1000, contextCodeGeneration: { strings: false, wasm: false } });
}
const invoke = bind(); let count = 0;
const control = (label, fn) => test(`S${String(++count).padStart(3, '0')} ${label}`, fn);
function result(input, value = invoke('site.yml', input)) {
  assert.equal(value.playbook, 'site.yml'); assert.equal(value.roles, input);
  assert.deepEqual(Object.keys(value), ['playbook', 'roles']);
}
function reject(playbook, input, fn = invoke) {
  assert.throws(() => fn(playbook, input), error => error instanceof PublicRefusal
    && error.message === 'Use site.yml and the supported provisioning roles');
}
control('omission selects the default playbook and empty list', () => {
  const value = invoke(); assert.equal(value.playbook, 'site.yml'); assert.equal(Array.isArray(value.roles), true); assert.equal(value.roles.length, 0);
});
control('explicit undefined retains both defaults', () => {
  const value = invoke(undefined, undefined); assert.equal(value.playbook, 'site.yml'); assert.equal(value.roles.length, 0);
});
control('default playbook keeps the supplied list', () => { const input = ['dns']; result(input, invoke(undefined, input)); });
control('default arrays and responses are independently fresh', () => {
  const a = invoke(), b = invoke(); assert.notEqual(a, b); assert.notEqual(a.roles, b.roles); a.roles.push('dns'); assert.equal(b.roles.length, 0);
});
control('empty supplied array retains identity', () => { result([]); });
control('full reverse registry retains order', () => { const input = [...roles].reverse(); result(input); assert.deepEqual(input, [...roles].reverse()); });
control('frozen supported array retains identity and contents', () => { const input = Object.freeze(['secrets', 'dns']); result(input); assert.deepEqual(input, ['secrets', 'dns']); });
control('fresh responses share the supplied array identity', () => {
  const input = ['bootstrap']; const a = invoke('site.yml', input), b = invoke('site.yml', input); assert.notEqual(a, b); result(input, a); result(input, b);
});
for (const role of roles) {
  control(`singleton ${role}`, () => { result([role]); });
  control(`duplicate ${role} refuses`, () => { reject('site.yml', [role, role]); });
}
const badPlaybooks = [
  ['null', null], ['false', false], ['true', true], ['zero', 0], ['one', 1], ['empty', ''], ['relative', './site.yml'], ['parent', '../site.yml'],
  ['extension', 'site.yaml'], ['case', 'SITE.yml'], ['suffix', 'site.yml '], ['option', '--help'], ['array', ['site.yml']], ['object', {}],
  ['boxed', Object('site.yml')], ['symbol', Symbol('public')], ['bigint', 1n], ['uncoercible', { toString() { assert.fail('coercion'); } }],
];
for (const [label, value] of badPlaybooks) control(`playbook ${label} refuses before role inspection`, () => {
  reject(value, new Proxy([], { get() { assert.fail('premature role read'); } }));
});
const nonLists = [
  ['null', null], ['false', false], ['true', true], ['zero', 0], ['one', 1], ['text', 'dns'], ['empty', ''], ['object', {}],
  ['array-like', { 0: 'dns', length: 1 }], ['set', new Set(['dns'])], ['typed', new Uint8Array([1])], ['function', () => []], ['symbol', Symbol('public')], ['bigint', 1n],
];
for (const [label, value] of nonLists) control(`non-array category ${label}`, () => { reject('site.yml', value); });
for (const spelling of ['', 'DNS', 'dns ', ' dns', '../dns', '--tags', 'unknown', 'dns,storage'])
  control(`unsupported spelling ${JSON.stringify(spelling)}`, () => { reject('site.yml', [spelling]); });
const nonText = [
  ['undefined', undefined], ['null', null], ['boolean', false], ['number', 1], ['bigint', 1n], ['symbol', Symbol('public')], ['object', {}],
  ['array', ['dns']], ['boxed', Object('dns')], ['function', () => 'dns'], ['uncoercible', { toString() { assert.fail('coercion'); } }],
];
for (const [label, value] of nonText) control(`non-string category ${label}`, () => { reject('site.yml', [value]); });
control('oversize stops before some or iterator access', () => {
  const input = new Proxy(new Array(12), { get(target, key, receiver) {
    if (key === 'some' || key === Symbol.iterator) assert.fail('late operation'); return Reflect.get(target, key, receiver);
  } }); reject('site.yml', input);
});
control('unknown role stops before Set construction', () => {
  class UnexpectedSet { constructor() { assert.fail('Set reached'); } } reject('site.yml', ['unknown'], bind({ Set: UnexpectedSet }));
});
control('non-string stops before includes lookup', () => {
  const registry = { length: 11, get includes() { assert.fail('includes reached'); return undefined; } }; reject('site.yml', [null], bind({ ANSIBLE_ROLES: registry }));
});
control('bad playbook stops before Array.isArray lookup', () => {
  reject('other.yml', [], bind({ Array: { get isArray() { assert.fail('Array reached'); return undefined; } } }));
});
control('false isArray stops before both length reads', () => {
  const input = new Proxy([], { get() { assert.fail('input read'); } });
  const registry = { get length() { assert.fail('registry read'); return 0; } };
  reject('site.yml', input, bind({ Array: { isArray: () => false }, ANSIBLE_ROLES: registry }));
});
function recording() {
  const events = [];
  const input = new Proxy(['dns'], { get(target, key, receiver) {
    if (key === 'length') events.push('roles.length');
    if (key === 'some') { events.push('roles.some:get'); return function(predicate) {
      assert.equal(this, input); events.push('roles.some:call'); return predicate('dns');
    }; } return Reflect.get(target, key, receiver);
  } });
  const array = { get isArray() { events.push('Array.isArray:get'); return function(value) {
    assert.equal(this, array); events.push('Array.isArray:call'); return Array.isArray(value);
  }; } };
  const registry = { get length() { events.push('registry.length'); return 11; }, get includes() {
    events.push('registry.includes:get'); return function(value) {
      assert.equal(this, registry); events.push('registry.includes:call'); return value === 'dns';
    };
  } };
  class CountingSet { constructor(value) { events.push('Set:construct'); assert.equal(value, input); }
    get size() { events.push('Set.size'); return 1; } }
  return { input, events, fn: bind({ Array: array, ANSIBLE_ROLES: registry, Set: CountingSet }) };
}
control('source order and immediate receivers match', () => {
  const { input, events, fn } = recording(); result(input, fn('site.yml', input));
  assert.deepEqual(events, ['Array.isArray:get', 'Array.isArray:call', 'roles.length', 'registry.length', 'roles.some:get', 'roles.some:call',
    'registry.includes:get', 'registry.includes:call', 'Set:construct', 'Set.size', 'roles.length']);
});
control('every immediate lookup repeats on the next call', () => {
  const { input, events, fn } = recording(); fn('site.yml', input); const previous = [...events]; events.length = 0; fn('site.yml', input); assert.deepEqual(events, previous);
});
const fault = new Error('PUBLIC immediate fault'); const raise = () => { throw fault; };
const brokenBindings = [
  ['isArray getter', () => ({ Array: { get isArray() { throw fault; } } })], ['isArray call', () => ({ Array: { isArray: raise } })],
  ['registry length', () => ({ ANSIBLE_ROLES: { get length() { throw fault; } } })],
  ['includes getter', () => ({ ANSIBLE_ROLES: { length: 11, get includes() { throw fault; } } })],
  ['includes call', () => ({ ANSIBLE_ROLES: { length: 11, includes: raise } })],
  ['Set construction', () => ({ Set: new Proxy(Set, { construct() { throw fault; } }) })], ['Set size', () => ({ Set: class { get size() { throw fault; } } })],
];
for (const [label, overrides] of brokenBindings) control(`${label} fault escapes by identity`, () => {
  assert.throws(() => bind(overrides())('site.yml', ['dns']), error => error === fault);
});
for (const point of ['length', 'some']) control(`roles ${point} getter fault escapes`, () => {
  const input = new Proxy(['dns'], { get(target, key, receiver) { if (key === point) throw fault; return Reflect.get(target, key, receiver); } });
  assert.throws(() => invoke('site.yml', input), error => error === fault);
});
control('roles.some call fault escapes', () => {
  const input = Object.assign(['dns'], { some: raise }); assert.throws(() => invoke('site.yml', input), error => error === fault);
});
control('second length lookup remains separate', () => {
  let reads = 0; const input = new Proxy(['dns'], { get(target, key, receiver) {
    if (key === 'length' && ++reads === 2) throw fault; if (key === 'some') return () => false; return Reflect.get(target, key, receiver);
  } });
  assert.throws(() => bind({ Set: class { size = 1; } })('site.yml', input), error => error === fault); assert.equal(reads, 2);
});
control('error constructor fault remains unchanged', () => {
  const Constructor = new Proxy(PublicRefusal, { construct() { throw fault; } });
  assert.throws(() => bind({ AnsibleSelectionError: Constructor })('other.yml', []), error => error === fault);
});
control('noncallable some retains JavaScript TypeError', () => {
  const input = Object.assign(['dns'], { some: null });
  assert.throws(() => invoke('site.yml', input), error => error !== null && typeof error === 'object' && error.name === 'TypeError');
});
control('single sparse hole retains JavaScript acceptance', () => { const input = new Array(1); result(input); assert.equal(0 in input, false); });
control('repeated holes fail cardinality', () => { reject('site.yml', new Array(2)); });
control('changed input is validated afresh', () => { const input = ['dns']; result(input); input[0] = 'unknown'; reject('site.yml', input); });
control('changed public registry is observed afresh', () => {
  const registry = ['dns']; const fn = bind({ ANSIBLE_ROLES: registry }); const input = ['dns']; result(input, fn('site.yml', input));
  registry[0] = 'storage'; reject('site.yml', ['dns'], fn);
});
assert.equal(count, 105);
