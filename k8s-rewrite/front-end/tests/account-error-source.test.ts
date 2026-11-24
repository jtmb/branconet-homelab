import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const source = readFileSync(fileURLToPath(new URL("../src/lib/account-store.ts", import.meta.url)), "utf8").replaceAll("\r\n", "\n");
assert.equal(createHash("sha256").update(source).digest("hex"), "0d5d1504f018891d76e9fcfa4801e5ffbd3f31a657eec6f23319ef40b639786f");
const ast = ts.createSourceFile("account-store.ts", source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((n: { name?: { text: string } }) => ts.isClassDeclaration(n) && n.name?.text === "AccountError");
assert.equal(selected.length, 1);
const declaration = selected[0].getText(ast);
assert.equal(declaration, "export class AccountError extends Error {\n  constructor(public readonly status: number, message: string) { super(message); }\n}");
const javascript = ts.transpileModule(declaration.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None, useDefineForClassFields: true } }).outputText.trim();
type Constructor = new (...args: unknown[]) => Record<string, unknown>;
const load = (Error: unknown): Constructor => vm.runInNewContext("(" + javascript + ")", { Error });
type Event = [string, ...unknown[]];

function fixture() {
  const events: Event[] = [];
  const target: Record<string, unknown> = {};
  const result = new Proxy(target, {
    defineProperty(object, key, descriptor) { events.push(["define", key, { ...descriptor }]); return Reflect.defineProperty(object, key, descriptor); },
    set(object, key, value, receiver) { events.push(["set", key, value, receiver]); return Reflect.set(object, key, value, receiver); },
  });
  const parent = new Proxy(function PublicSuperclass() { assert.fail("only synthetic construct trap may run"); }, {
    get(object, key, receiver) { if (key === "prototype") events.push(["prototype"]); return Reflect.get(object, key, receiver); },
    construct(_object, args, newTarget) { events.push(["super", [...args], newTarget]); return result; },
  });
  const Class = load(parent);
  return { events, target, result, parent, Class };
}
const labels = (events: Event[]) => events.map(e => e[0]);
function check(f: ReturnType<typeof fixture>, status: unknown, message: unknown) {
  f.events.length = 0;
  const instance = new f.Class(status, message);
  assert.equal(instance, f.result);
  assert.deepEqual(labels(f.events), ["super", "define", "set", "define"]);
  assert.equal((f.events[0][1] as unknown[]).length, 1);
  assert.equal((f.events[0][1] as unknown[])[0], message);
  assert.equal(f.events[0][2], f.Class);
  assert.deepEqual(f.events[1], ["define", "status", { value: undefined, writable: true, enumerable: true, configurable: true }]);
  assert.deepEqual(f.events[2], ["set", "status", status, f.result]);
  assert.deepEqual(f.events[3], ["define", "status", { value: status }]);
  assert.equal(instance.status, status);
  assert.deepEqual(Object.getOwnPropertyDescriptor(instance, "status"), { value: status, writable: true, enumerable: true, configurable: true });
}

test("declaration captures synthetic superclass prototype without construction", () => {
  const f = fixture(); assert.deepEqual(labels(f.events), ["prototype"]);
  assert.equal(Object.getPrototypeOf(f.Class), f.parent);
  assert.equal(f.Class.name, "AccountError"); assert.equal(f.Class.length, 2);
});
test("super precedes native status field definition and parameter-property assignment", () => check(fixture(), 409, "Synthetic public message"));

const statusCases = [
  ["undefined", undefined], ["null", null], ["false", false], ["zero", 0],
  ["negative", -1], ["fraction", 2.5], ["NaN", NaN], ["infinity", Infinity],
  ["text", "PUBLIC"], ["symbol", Symbol("public status")], ["object", Object.freeze({ publicStatus: true })],
] as const;
for (const [name, value] of statusCases) test("selected projection stores exact synthetic status without coercion: " + name, () => check(fixture(), value, "Synthetic public message"));
const messageCases = [
  ["undefined", undefined], ["null", null], ["false", false], ["zero", 0],
  ["empty", ""], ["text", "Synthetic public message"], ["bigint", 7n],
  ["symbol", Symbol("public message")], ["object", Object.freeze({ publicMessage: true })],
] as const;
for (const [name, value] of messageCases) test("selected projection forwards one exact synthetic message argument: " + name, () => check(fixture(), 409, value));

test("omitted arguments still forward one undefined message and assign undefined status", () => {
  const f = fixture(); f.events.length = 0; const instance = new f.Class();
  assert.equal(instance, f.result); assert.deepEqual(f.events[0], ["super", [undefined], f.Class]);
  assert.equal(Object.hasOwn(instance, "status"), true); assert.equal(instance.status, undefined);
});
test("extra arguments are not forwarded to immediate superclass", () => {
  const f = fixture(); f.events.length = 0; new f.Class(409, "PUBLIC", "UNSELECTED");
  assert.deepEqual(f.events[0], ["super", ["PUBLIC"], f.Class]);
});
test("status is not coerced and its then member is never read", () => {
  const status = Object.defineProperties({}, { [Symbol.toPrimitive]: { get() { assert.fail("status coercion"); } }, then: { get() { assert.fail("status then"); } } });
  check(fixture(), status, "PUBLIC");
});
test("message is neither coerced nor assimilated by selected constructor", () => {
  const message = Object.defineProperties({}, { [Symbol.toPrimitive]: { get() { assert.fail("message coercion"); } }, then: { get() { assert.fail("message then"); } } });
  check(fixture(), 409, message);
});
test("synthetic superclass returned object is preserved without then assimilation", () => {
  const f = fixture(); Object.defineProperty(f.target, "then", { get() { assert.fail("instance then"); } });
  check(f, 409, "PUBLIC");
});
test("synthetic superclass completes before status is created", () => {
  const result = {}; let calls = 0;
  const parent = new Proxy(function PublicSuperclass() {}, { construct(_target, args) { calls++; assert.deepEqual([...args], ["PUBLIC"]); assert.equal(Object.hasOwn(result, "status"), false); return result; } });
  assert.equal(new (load(parent))(409, "PUBLIC"), result); assert.equal(calls, 1); assert.equal((result as Record<string, unknown>).status, 409);
});
test("exact synchronous superclass fault propagates once before field initialization", () => {
  const marker = Object.freeze({ publicFault: "super" }); let calls = 0;
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { calls++; throw marker; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => e === marker); assert.equal(calls, 1);
});
test("exact native field-definition fault propagates before assignment", () => {
  const marker = Object.freeze({ publicFault: "define" }); const events: string[] = [];
  const result = new Proxy({}, { defineProperty() { events.push("define"); throw marker; }, set() { events.push("set"); return true; } });
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { events.push("super"); return result; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => e === marker); assert.deepEqual(events, ["super", "define"]);
});
test("exact status-assignment fault propagates after successful native field definition", () => {
  const marker = Object.freeze({ publicFault: "set" }); const events: string[] = [];
  const result = new Proxy({}, { defineProperty(target, key, descriptor) { events.push("define"); return Reflect.defineProperty(target, key, descriptor); }, set() { events.push("set"); throw marker; } });
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { events.push("super"); return result; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => e === marker); assert.deepEqual(events, ["super", "define", "set"]);
});
test("false field-definition trap refuses construction before assignment", () => {
  let sets = 0; const result = new Proxy({}, { defineProperty() { return false; }, set() { sets++; return true; } });
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { return result; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => (e as Error).name === "TypeError"); assert.equal(sets, 0);
});
test("false assignment trap refuses synchronous construction", () => {
  let sets = 0; const result = new Proxy({}, { set() { sets++; return false; } });
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { return result; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => (e as Error).name === "TypeError"); assert.equal(sets, 1);
});
test("nonextensible superclass result refuses native status field", () => {
  const result = Object.preventExtensions({}); const parent = new Proxy(function PublicSuperclass() {}, { construct() { return result; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => (e as Error).name === "TypeError"); assert.equal(Object.hasOwn(result, "status"), false);
});
test("nonconfigurable superclass status cannot be overwritten by native field definition", () => {
  const result = Object.defineProperty({}, "status", { value: "PUBLIC ORIGINAL", writable: true, configurable: false });
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { return result; } });
  assert.throws(() => new (load(parent))(409, "PUBLIC"), e => (e as Error).name === "TypeError"); assert.equal((result as Record<string, unknown>).status, "PUBLIC ORIGINAL");
});
test("configurable superclass status accessor is replaced without getter or setter calls", () => {
  const result = Object.defineProperty({}, "status", { configurable: true, get() { assert.fail("old getter"); }, set() { assert.fail("old setter"); } });
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { return result; } });
  const instance = new (load(parent))(409, "PUBLIC"); assert.equal(instance.status, 409);
  assert.deepEqual(Object.getOwnPropertyDescriptor(instance, "status"), { value: 409, writable: true, enumerable: true, configurable: true });
});
test("inherited status accessor is bypassed by own field definition", () => {
  const result = Object.create(Object.defineProperty({}, "status", { get() { assert.fail("inherited getter"); }, set() { assert.fail("inherited setter"); } }));
  const parent = new Proxy(function PublicSuperclass() {}, { construct() { return result; } });
  const instance = new (load(parent))(409, "PUBLIC"); assert.equal(instance.status, 409); assert.equal(Object.hasOwn(instance, "status"), true);
});
test("readonly annotation does not make emitted status nonwritable", () => {
  const f = fixture(); const instance = new f.Class(409, "PUBLIC"); instance.status = 418; assert.equal(instance.status, 418);
});
test("unrelated synthetic superclass metadata remains unchanged", () => {
  const f = fixture(); const marker = Object.freeze({ publicMarker: true });
  Object.defineProperty(f.target, "message", { value: marker, configurable: false }); Object.defineProperty(f.target, "name", { value: "PublicBase", writable: false });
  const instance = new f.Class(409, "PUBLIC"); assert.equal(instance.message, marker); assert.equal(instance.name, "PublicBase");
  assert.deepEqual(Object.keys(instance), ["status"]);
});
test("ordinary inert superclass establishes derived prototype and per-instance status", () => {
  class PublicBase { message: unknown; constructor(message: unknown) { this.message = message; } }
  const Class = load(PublicBase); const first = new Class(409, "FIRST"); const second = new Class(418, "SECOND");
  assert.equal(Object.getPrototypeOf(first), Class.prototype); assert.equal(Object.getPrototypeOf(Class.prototype), PublicBase.prototype);
  assert.ok(first instanceof Class); assert.ok(first instanceof PublicBase); assert.equal(first.message, "FIRST"); assert.equal(second.message, "SECOND");
  assert.equal(first.status, 409); assert.equal(second.status, 418); assert.notEqual(first, second);
});
test("derived subclass new.target is forwarded and its field sees assigned status", () => {
  class PublicBase { constructor(_message: unknown) {} }
  const Class = load(PublicBase); class Child extends Class { observed = this.status; }
  const instance = new Child(409, "PUBLIC"); assert.equal(instance.observed, 409); assert.equal(Object.getPrototypeOf(instance), Child.prototype);
  const f = fixture(); class ProxyChild extends f.Class {} f.events.length = 0; new ProxyChild(418, "PUBLIC"); assert.equal(f.events[0][2], ProxyChild);
});
test("captured superclass survives replacement of the lexical binding", () => {
  const f = fixture(); const context = vm.createContext({ Error: f.parent });
  const Class: Constructor = vm.runInContext("(" + javascript + ")", context); context.Error = function Replacement() { assert.fail("replacement binding"); };
  assert.equal(new Class(409, "PUBLIC"), f.result);
});
test("prototype getter fault aborts declaration evaluation exactly once", () => {
  const marker = Object.freeze({ publicFault: "prototype" }); let calls = 0;
  const parent = new Proxy(function PublicSuperclass() {}, { get(target, key, receiver) { if (key === "prototype") { calls++; throw marker; } return Reflect.get(target, key, receiver); } });
  assert.throws(() => load(parent), e => e === marker); assert.equal(calls, 1);
});
test("null synthetic superclass prototype is accepted without normalizing returned object", () => {
  const result = {}; const parent = new Proxy(function PublicSuperclass() {}, { get(target, key, receiver) { return key === "prototype" ? null : Reflect.get(target, key, receiver); }, construct() { return result; } });
  const Class = load(parent); assert.equal(Object.getPrototypeOf(Class.prototype), null); assert.equal(new Class(409, "PUBLIC"), result); assert.equal((result as Record<string, unknown>).status, 409);
});
test("primitive synthetic superclass prototype refuses declaration", () => {
  const parent = new Proxy(function PublicSuperclass() {}, { get(target, key, receiver) { return key === "prototype" ? 1 : Reflect.get(target, key, receiver); } });
  assert.throws(() => load(parent), e => (e as Error).name === "TypeError");
});
