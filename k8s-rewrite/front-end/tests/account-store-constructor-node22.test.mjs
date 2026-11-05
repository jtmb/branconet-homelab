import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// A separately authored supported-runtime projection. Never load AccountStore,
// Prisma, its imports, neighbours, methods, initializers or transactions.
const ts = createRequire(import.meta.url)('typescript');
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
const raw = readFileSync(new URL('../src/lib/account-store.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(createHash('sha256').update(source).digest('hex'), '0d5d1504f018891d76e9fcfa4801e5ffbd3f31a657eec6f23319ef40b639786f');
const ast = ts.createSourceFile('account-store.ts', source, ts.ScriptTarget.ES2022, true);
assert.equal(ast.parseDiagnostics.length, 0);
const owners = ast.statements.filter(node => ts.isClassDeclaration(node) && node.name?.text === 'AccountStore');
assert.equal(owners.length, 1);
const constructors = owners[0].members.filter(ts.isConstructorDeclaration);
assert.equal(constructors.length, 1);
const selected = constructors[0].getText(ast);
assert.equal(selected, 'constructor(private readonly db: PrismaClient) {}');
assert.equal(constructors[0].body.statements.length, 0);
const shell = `type PrismaClient = unknown;\nclass SelectedConstructor {\n${selected}\n}`;
const emitted = ts.transpileModule(shell, { reportDiagnostics: true, compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None, useDefineForClassFields: true,
} });
assert.equal(emitted.diagnostics.length, 0);
const javascript = emitted.outputText.trim();
assert.equal(javascript, 'class SelectedConstructor {\n    db;\n    constructor(db) {\n        this.db = db;\n    }\n}');
const load = () => vm.runInNewContext(`(${javascript})`, Object.create(null), {
  timeout: 1000, contextCodeGeneration: { strings: false, wasm: false },
});
const identity = () => Object.freeze({ publicBinding: Symbol('inert') });
const refuse = label => () => assert.fail(`Unexpected metadata operation: ${label}`);
function verify(value) {
  const Constructor = load(); const instance = new Constructor(value);
  assert.equal(instance.db, value);
  assert.deepEqual(Reflect.ownKeys(instance), ['db']);
  assert.deepEqual(Object.getOwnPropertyDescriptor(instance, 'db'), { value, writable: true, enumerable: true, configurable: true });
  assert.equal(Object.getPrototypeOf(instance), Constructor.prototype);
  return { Constructor, instance };
}

test('C01 exact empty declaration produces only a native field and assignment', () => {
  assert.equal(selected, 'constructor(private readonly db: PrismaClient) {}');
  const Constructor = load();
  assert.equal(Constructor.length, 1); assert.equal(Constructor.name, 'SelectedConstructor');
  assert.deepEqual(Reflect.ownKeys(Constructor.prototype), ['constructor']);
  assert.equal(Object.hasOwn(Constructor, 'db'), false);
  assert.equal(Object.hasOwn(Constructor.prototype, 'db'), false);
});
test('C02 opaque public binding is stored with its complete native descriptor', () => { verify(identity()); });
const categories = [
  ['undefined', undefined], ['null', null], ['false', false], ['zero', 0],
  ['negative zero', -0], ['NaN', NaN], ['text', 'PUBLIC BINDING'],
  ['bigint', 17n], ['symbol', Symbol('binding')], ['frozen object', Object.freeze({ publicBinding: true })],
];
for (const [index, [label, value]] of categories.entries())
  test(`C${String(index + 3).padStart(2, '0')} identity category ${label} is unvalidated`, () => { verify(value); });
test('C13 omitted input still defines db with undefined', () => {
  const instance = new (load())();
  assert.deepEqual(Object.getOwnPropertyDescriptor(instance, 'db'), { value: undefined, writable: true, enumerable: true, configurable: true });
});
test('C14 surplus arguments are never inspected', () => {
  const value = identity(); const surplus = new Proxy({}, { get: refuse('surplus read') });
  assert.equal(new (load())(value, surplus).db, value);
});
test('C15 binding reflection and reads remain inert', () => {
  const value = new Proxy({}, { get: refuse('get'), getPrototypeOf: refuse('prototype'), ownKeys: refuse('keys'), getOwnPropertyDescriptor: refuse('descriptor') });
  assert.equal(new (load())(value).db, value);
});
test('C16 a revoked binding proxy remains an opaque identity', () => {
  const revocable = Proxy.revocable({}, {}); revocable.revoke();
  assert.equal(new (load())(revocable.proxy).db, revocable.proxy);
});
test('C17 metadata then, primitive and iterator getters are untouched', () => {
  const value = Object.defineProperties({}, { then: { get: refuse('then') },
    [Symbol.toPrimitive]: { get: refuse('primitive') }, [Symbol.iterator]: { get: refuse('iterator') } });
  assert.equal(new (load())(value).db, value);
});
test('C18 the binding stays mutable and is neither cloned nor frozen', () => {
  const value = { publicBinding: 'first' }; const { instance } = verify(value);
  value.publicBinding = 'second';
  assert.equal(instance.db, value); assert.equal(instance.db.publicBinding, 'second');
  assert.equal(Object.isFrozen(value), false);
});
test('C19 instances own independent slots holding the same binding', () => {
  const Constructor = load(); const value = identity();
  const first = new Constructor(value); const second = new Constructor(value);
  assert.notEqual(first, second); assert.equal(first.db, value); assert.equal(second.db, value);
  first.db = 'PUBLIC NEW SLOT'; assert.equal(second.db, value);
});
test('C20 private readonly is erased and the own slot remains writable', () => {
  const { instance } = verify(identity()); instance.db = 'PUBLIC REPLACEMENT';
  assert.equal(instance.db, 'PUBLIC REPLACEMENT');
});
test('C21 native field definition bypasses both inherited accessor hooks', () => {
  const Constructor = load();
  Object.defineProperty(Constructor.prototype, 'db', { get: refuse('inherited get'), set: refuse('inherited set'), configurable: true });
  const value = identity(); assert.equal(new Constructor(value).db, value);
});
test('C22 inherited nonwritable nonconfigurable data cannot prevent own field definition', () => {
  const Constructor = load(); Object.defineProperty(Constructor.prototype, 'db', { value: 'INHERITED', writable: false, configurable: false });
  const value = identity(); const instance = new Constructor(value);
  assert.equal(instance.db, value); assert.equal(Object.hasOwn(instance, 'db'), true);
});
test('C23 the readonly slot remains configurable and deletable', () => {
  const { instance } = verify(identity()); assert.equal(Reflect.deleteProperty(instance, 'db'), true);
  assert.equal(Object.hasOwn(instance, 'db'), false);
});
test('C24 assignment completes before synthetic derived fields and constructor body', () => {
  const Constructor = load(); const value = identity(); const observations = [];
  class Derived extends Constructor {
    observed = (observations.push(this.db), this.db);
    constructor(binding) { super(binding); observations.push(this.observed); }
  }
  const instance = new Derived(value);
  assert.equal(instance.db, value); assert.equal(instance.observed, value);
  assert.deepEqual(observations, [value, value]); assert.equal(Object.getPrototypeOf(instance), Derived.prototype);
});
test('C25 a later derived field replaces the assigned binding', () => {
  const Constructor = load(); class Derived extends Constructor { db = 'PUBLIC DERIVED'; }
  assert.equal(new Derived(identity()).db, 'PUBLIC DERIVED');
});
test('C26 explicit newTarget retains its own synthetic prototype', () => {
  const Constructor = load(); const prototype = Object.freeze({ publicPrototype: true });
  function Target() {} Target.prototype = prototype;
  const value = identity(); const instance = Reflect.construct(Constructor, [value], Target);
  assert.equal(Object.getPrototypeOf(instance), prototype); assert.equal(instance.db, value);
});
test('C27 newTarget prototype is obtained exactly once before binding assignment', () => {
  const Constructor = load(); const value = identity(); const prototype = {}; const observations = [];
  const Target = new Proxy(function Target() {}, { get(target, key, receiver) {
    if (key === 'prototype') { observations.push('prototype'); return prototype; }
    return Reflect.get(target, key, receiver);
  } });
  const instance = Reflect.construct(Constructor, [value], Target);
  assert.deepEqual(observations, ['prototype']); assert.equal(instance.db, value);
  assert.equal(Object.getPrototypeOf(instance), prototype);
});
test('C28 an exact synchronous newTarget fault escapes once without binding inspection', () => {
  const Constructor = load(); const fault = Object.freeze({ publicFault: 'prototype' }); let attempts = 0;
  const Target = new Proxy(function Target() {}, { get(target, key, receiver) {
    if (key === 'prototype') { attempts++; throw fault; }
    return Reflect.get(target, key, receiver);
  } });
  const value = new Proxy({}, { get: refuse('fault-path binding read') });
  assert.throws(() => Reflect.construct(Constructor, [value], Target), error => error === fault);
  assert.equal(attempts, 1);
});
test('C29 calling the class without new refuses before reading any binding', () => {
  const value = new Proxy({}, { get: refuse('call binding read') });
  assert.throws(() => Reflect.apply(load(), undefined, [value]), error => error !== null && typeof error === 'object' && error.name === 'TypeError');
});
test('C30 the returned instance never assimilates an inherited then getter', () => {
  const Constructor = load(); Object.defineProperty(Constructor.prototype, 'then', { get: refuse('instance then') });
  const value = identity(); const instance = new Constructor(value);
  assert.equal(instance.db, value); assert.equal(instance instanceof Constructor, true);
});
