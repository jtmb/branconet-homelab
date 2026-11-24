import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { declaration } from './support/node22-source-harness.mjs';

const compile = declaration('account-store.ts', '0d5d1504f018891d76e9fcfa4801e5ffbd3f31a657eec6f23319ef40b639786f', 'AccountError',
  'export class AccountError extends Error {\n  constructor(public readonly status: number, message: string) { super(message); }\n}');
function instrument(target = {}) {
  const trace = [];
  const result = new Proxy(target, {
    defineProperty(object, key, descriptor) { trace.push(['field', key, { ...descriptor }]); return Reflect.defineProperty(object, key, descriptor); },
    set(object, key, value, receiver) { trace.push(['assign', key, value, receiver]); return Reflect.set(object, key, value, receiver); },
  });
  const base = new Proxy(function PublicParent() { assert.fail('direct parent call'); }, {
    get(object, key, receiver) { if (key === 'prototype') trace.push(['prototype']); return Reflect.get(object, key, receiver); },
    construct(_object, args, newTarget) { trace.push(['construct', args, newTarget]); return result; },
  });
  const Class = compile({ Error: base });
  return { Class, base, result, trace, target };
}
const kinds = f => f.trace.map(event => event[0]);
function observe(status, message, args = [status, message]) {
  const f = instrument(); f.trace.length = 0;
  assert.equal(Reflect.construct(f.Class, args), f.result);
  assert.deepEqual(kinds(f), ['construct', 'field', 'assign', 'field']);
  assert.equal(f.trace[0][1].length, 1); assert.equal(f.trace[0][1][0], message); assert.equal(f.trace[0][2], f.Class);
  assert.deepEqual(f.trace[1], ['field', 'status', { value: undefined, writable: true, enumerable: true, configurable: true }]);
  assert.deepEqual(f.trace[2], ['assign', 'status', status, f.result]);
  assert.deepEqual(f.trace[3], ['field', 'status', { value: status }]);
  assert.deepEqual(Object.getOwnPropertyDescriptor(f.result, 'status'), { value: status, writable: true, enumerable: true, configurable: true });
}
const row = (id, body) => test(`N22-E${id}: ${body.name || 'public constructor contract'}`, body);
row('01', function declarationIdentity() { const f = instrument(); assert.deepEqual(kinds(f), ['prototype']); assert.equal(Object.getPrototypeOf(f.Class), f.base); assert.equal(f.Class.name, 'AccountError'); assert.equal(f.Class.length, 2); });
row('02', function nativeFieldOrder() { observe(422, 'PUBLIC N22'); });
const statuses = [undefined, null, false, 0, -3, 0.25, NaN, Infinity, 'N22', Symbol('status22'), Object.freeze({ status22: true })];
statuses.forEach((value, i) => row(String(i + 3).padStart(2, '0'), () => observe(value, 'PUBLIC N22')));
const messages = [undefined, null, false, 0, '', 'PUBLIC N22', 19n, Symbol('message22'), Object.freeze({ message22: true })];
messages.forEach((value, i) => row(String(i + 14).padStart(2, '0'), () => observe(422, value)));
row('23', function absentArguments() { observe(undefined, undefined, []); });
row('24', function trailingArguments() { observe(422, 'PUBLIC N22', [422, 'PUBLIC N22', Symbol('extra22')]); });
const opaque = () => Object.defineProperties({}, { then: { get() { assert.fail('then read'); } }, [Symbol.toPrimitive]: { get() { assert.fail('coercion read'); } } });
row('25', function opaqueStatus() { observe(opaque(), 'PUBLIC N22'); });
row('26', function opaqueMessage() { observe(422, opaque()); });
row('27', function opaqueReturnedObject() { const f = instrument(opaque()); assert.equal(new f.Class(422, 'N22'), f.result); });
row('28', function fieldAfterParent() {
  const target = {}; let calls = 0;
  const base = new Proxy(function PublicParent() {}, { construct(_base, args) { calls++; assert.deepEqual(Array.from(args), ['N22']); assert.equal(Object.hasOwn(target, 'status'), false); return target; } });
  assert.equal(new (compile({ Error: base }))(422, 'N22'), target); assert.equal(calls, 1); assert.equal(target.status, 422);
});
for (const [id, stage, expected] of [['29', 'super', ['super']], ['30', 'field', ['super', 'field']], ['31', 'assign', ['super', 'field', 'assign']]]) row(id, () => {
  const marker = Object.freeze({ stage }); const events = [];
  const fault = label => { events.push(label); if (stage === label) throw marker; };
  const result = new Proxy({}, { defineProperty(object, key, descriptor) { fault('field'); return Reflect.defineProperty(object, key, descriptor); }, set() { fault('assign'); return true; } });
  const base = new Proxy(function PublicParent() {}, { construct() { fault('super'); return result; } });
  assert.throws(() => new (compile({ Error: base }))(422, 'N22'), error => error === marker); assert.deepEqual(events, expected);
});
for (const [id, refused, expectedSets] of [['32', 'field', 0], ['33', 'assign', 1]]) row(id, () => {
  let sets = 0; const target = new Proxy({}, { defineProperty(object, key, descriptor) { return refused === 'field' ? false : Reflect.defineProperty(object, key, descriptor); }, set() { sets++; return false; } });
  const base = new Proxy(function PublicParent() {}, { construct() { return target; } });
  assert.throws(() => new (compile({ Error: base }))(422, 'N22'), error => error.name === 'TypeError'); assert.equal(sets, expectedSets);
});
row('34', function nonextensibleResult() { const target = Object.preventExtensions({}); const base = new Proxy(function PublicParent() {}, { construct() { return target; } }); assert.throws(() => new (compile({ Error: base }))(422, 'N22'), error => error.name === 'TypeError'); assert.equal(Object.hasOwn(target, 'status'), false); });
row('35', function fixedStatus() { const target = Object.defineProperty({}, 'status', { value: 'N22 original', writable: true, configurable: false }); const base = new Proxy(function PublicParent() {}, { construct() { return target; } }); assert.throws(() => new (compile({ Error: base }))(422, 'N22'), error => error.name === 'TypeError'); assert.equal(target.status, 'N22 original'); });
const accessor = { configurable: true, get() { assert.fail('status get'); }, set() { assert.fail('status set'); } };
row('36', function replaceOwnAccessor() { const target = Object.defineProperty({}, 'status', accessor); const f = instrument(target); new f.Class(422, 'N22'); assert.deepEqual(Object.getOwnPropertyDescriptor(target, 'status'), { value: 422, writable: true, enumerable: true, configurable: true }); });
row('37', function bypassInheritedAccessor() { const target = Object.create(Object.defineProperty({}, 'status', accessor)); const f = instrument(target); new f.Class(422, 'N22'); assert.equal(Object.hasOwn(target, 'status'), true); assert.equal(target.status, 422); });
row('38', function runtimeWritable() { const f = instrument(); const value = new f.Class(422, 'N22'); value.status = 451; assert.equal(value.status, 451); });
row('39', function otherProperties() { const target = Object.defineProperties({}, { message: { value: Object.freeze({ public22: true }) }, name: { value: 'PublicParent22' } }); const f = instrument(target); assert.equal(new f.Class(422, 'N22'), f.result); assert.equal(f.result.message, target.message); assert.equal(f.result.name, 'PublicParent22'); assert.deepEqual(Object.keys(target), ['status']); });
row('40', function independentInstances() {
  class Parent22 { constructor(message) { this.message = message; } }
  const Class = compile({ Error: Parent22 }); const a = new Class(422, 'A22'); const b = new Class(451, 'B22');
  assert.equal(Object.getPrototypeOf(a), Class.prototype); assert.equal(Object.getPrototypeOf(Class.prototype), Parent22.prototype);
  assert.ok(a instanceof Class && a instanceof Parent22); assert.notEqual(a, b); assert.equal(a.message, 'A22'); assert.equal(b.message, 'B22'); assert.equal(a.status, 422); assert.equal(b.status, 451);
});
row('41', function descendantTarget() { const f = instrument(); class Child22 extends f.Class { observed = this.status; } f.trace.length = 0; const result = new Child22(422, 'N22'); assert.equal(f.trace[0][2], Child22); assert.equal(result.observed, 422); const Class = compile({ Error: class Parent22 {} }); class OrdinaryChild22 extends Class {} assert.equal(Object.getPrototypeOf(new OrdinaryChild22(422, 'N22')), OrdinaryChild22.prototype); });
row('42', function capturedLexicalParent() { const f = instrument(); const context = vm.createContext({ Error: f.base }); const Class = compile(context); context.Error = function Replaced22() { assert.fail('replaced parent'); }; assert.equal(new Class(422, 'N22'), f.result); });
row('43', function declarationFault() { let reads = 0; const marker = Object.freeze({ prototype22: true }); const base = new Proxy(function PublicParent() {}, { get(object, key, receiver) { if (key === 'prototype') { reads++; throw marker; } return Reflect.get(object, key, receiver); } }); assert.throws(() => compile({ Error: base }), error => error === marker); assert.equal(reads, 1); });
row('44', function nullParentPrototype() { const target = {}; const base = new Proxy(function PublicParent() {}, { get(object, key, receiver) { return key === 'prototype' ? null : Reflect.get(object, key, receiver); }, construct() { return target; } }); const Class = compile({ Error: base }); assert.equal(Object.getPrototypeOf(Class.prototype), null); assert.equal(new Class(422, 'N22'), target); assert.equal(target.status, 422); });
row('45', function invalidParentPrototype() { const base = new Proxy(function PublicParent() {}, { get(object, key, receiver) { return key === 'prototype' ? 22 : Reflect.get(object, key, receiver); } }); assert.throws(() => compile({ Error: base }), error => error.name === 'TypeError'); });
