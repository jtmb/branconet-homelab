import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE projection only. No original module or database implementation is loaded.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/account-store.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.equal(createHash("sha256").update(source).digest("hex"), "0d5d1504f018891d76e9fcfa4801e5ffbd3f31a657eec6f23319ef40b639786f");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
const ast = ts.createSourceFile("account-store.ts", source, ts.ScriptTarget.Latest, true);
const classes = ast.statements.filter((n: { name?: { text: string } }) => ts.isClassDeclaration(n) && n.name?.text === "AccountStore");
assert.equal(classes.length, 1);
const constructors = classes[0].members.filter((n: unknown) => ts.isConstructorDeclaration(n));
assert.equal(constructors.length, 1);
const declaration = constructors[0].getText(ast);
assert.equal(declaration, "constructor(private readonly db: PrismaClient) {}");
assert.equal(constructors[0].body.statements.length, 0);
// The type name is inert. No Prisma import, binding, method, query, initializer or neighbour enters the shell.
const shell = "class SelectedConstructor {\n" + declaration + "\n}";
const javascript = ts.transpileModule(shell, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None, useDefineForClassFields: true } }).outputText.trim();
assert.equal(javascript, "class SelectedConstructor {\n    db;\n    constructor(db) {\n        this.db = db;\n    }\n}");
type Constructor = new (...args: unknown[]) => Record<string, unknown>;
const load = (): Constructor => vm.runInNewContext("(" + javascript + ")", {});
const metadata = () => Object.freeze({ publicIdentity: Symbol("inert database binding") });
function check(value: unknown) {
  const Class = load(); const instance = new Class(value);
  assert.equal(instance.db, value);
  assert.deepEqual(Reflect.ownKeys(instance), ["db"]);
  assert.deepEqual(Object.getOwnPropertyDescriptor(instance, "db"), { value, writable: true, enumerable: true, configurable: true });
  assert.equal(Object.getPrototypeOf(instance), Class.prototype);
  return { Class, instance };
}

test("selected declaration and exact ES2022 native-field projection are pinned", () => {
  assert.equal(declaration, "constructor(private readonly db: PrismaClient) {}");
  assert.equal(javascript.includes("this.db = db;"), true);
  const Class = load(); assert.equal(Class.length, 1); assert.equal(Class.name, "SelectedConstructor");
  assert.deepEqual(Reflect.ownKeys(Class.prototype), ["constructor"]);
  assert.equal(Object.hasOwn(Class, "db"), false); assert.equal(Object.hasOwn(Class.prototype, "db"), false);
});
test("stores one exact inert metadata identity in a native own field", () => { check(metadata()); });
const inertCases = [
  ["undefined", undefined], ["null", null], ["false", false], ["zero", 0],
  ["negative zero", -0], ["NaN", NaN], ["text", "PUBLIC IDENTITY ONLY"],
  ["bigint", 7n], ["symbol", Symbol("public identity")], ["frozen metadata", Object.freeze({ publicIdentity: "frozen" })],
] as const;
for (const [name, value] of inertCases) test("runtime-only synthetic binding keeps exact identity without validation: " + name, () => { check(value); });
test("omitted argument creates db with undefined rather than omitting the field", () => {
  const instance = new (load())(); assert.equal(Object.hasOwn(instance, "db"), true); assert.equal(instance.db, undefined);
});
test("extra arguments remain unobserved", () => {
  const value = metadata(); const extra = new Proxy({}, { get() { assert.fail("extra argument member read"); } });
  assert.equal(new (load())(value, extra).db, value);
});
test("opaque metadata input has no member, prototype, key or descriptor reads", () => {
  const value = new Proxy({}, { get() { assert.fail("db get"); }, getPrototypeOf() { assert.fail("db prototype"); }, ownKeys() { assert.fail("db keys"); }, getOwnPropertyDescriptor() { assert.fail("db descriptor"); } });
  const instance = new (load())(value); assert.equal(instance.db, value);
});
test("revoked proxy binding is retained without inspection", () => {
  const { proxy, revoke } = Proxy.revocable({}, {}); revoke(); assert.equal(new (load())(proxy).db, proxy);
});
test("thenable, coercion and iterator hooks on metadata are inert", () => {
  const value = Object.defineProperties({}, { then: { get() { assert.fail("then"); } }, [Symbol.toPrimitive]: { get() { assert.fail("coercion"); } }, [Symbol.iterator]: { get() { assert.fail("iterator"); } } });
  assert.equal(new (load())(value).db, value);
});
test("construction neither clones nor freezes metadata", () => {
  const value = { publicIdentity: "before" }; const instance = new (load())(value); value.publicIdentity = "after";
  assert.equal(instance.db, value); assert.equal((instance.db as typeof value).publicIdentity, "after"); assert.equal(Object.isFrozen(value), false);
});
test("separate constructions have separate own fields with unchanged input identity", () => {
  const Class = load(); const value = metadata(); const a = new Class(value); const b = new Class(value);
  assert.notEqual(a, b); assert.equal(a.db, value); assert.equal(b.db, value); a.db = "PUBLIC REPLACEMENT"; assert.equal(b.db, value);
});
test("private and readonly modifiers impose no runtime write restriction", () => {
  const { instance } = check(metadata()); instance.db = "PUBLIC REPLACEMENT"; assert.equal(instance.db, "PUBLIC REPLACEMENT");
});
test("native own field bypasses inherited accessor without invoking it", () => {
  const Class = load(); Object.defineProperty(Class.prototype, "db", { get() { assert.fail("prototype get"); }, set() { assert.fail("prototype set"); }, configurable: true });
  const value = metadata(); assert.equal(new Class(value).db, value);
});
test("inherited frozen data property cannot block native own field", () => {
  const Class = load(); Object.defineProperty(Class.prototype, "db", { value: "INHERITED", writable: false, configurable: false });
  const value = metadata(); const instance = new Class(value); assert.equal(instance.db, value); assert.equal(Object.hasOwn(instance, "db"), true);
});
test("readonly parameter-property remains runtime configurable", () => {
  const { instance } = check(metadata()); assert.equal(Reflect.deleteProperty(instance, "db"), true); assert.equal(Object.hasOwn(instance, "db"), false);
});
test("ordinary synthetic subclass sees assigned identity before its own fields and body", () => {
  const Class = load(); const value = metadata(); const events: unknown[] = [];
  class Child extends Class { observed = (events.push(this.db), this.db); constructor(binding: unknown) { super(binding); events.push(this.observed); } }
  const instance = new Child(value); assert.equal(instance.db, value); assert.equal(instance.observed, value); assert.deepEqual(events, [value, value]); assert.equal(Object.getPrototypeOf(instance), Child.prototype);
});
test("synthetic subclass field override occurs after selected constructor assignment", () => {
  const Class = load(); class Child extends Class { db = "PUBLIC CHILD FIELD"; }
  assert.equal(new Child(metadata()).db, "PUBLIC CHILD FIELD");
});
test("Reflect.construct retains an explicit synthetic newTarget prototype", () => {
  const Class = load(); const prototype = Object.freeze({ publicPrototype: true }); const target = function SyntheticTarget() {}; target.prototype = prototype;
  const value = metadata(); const instance = Reflect.construct(Class, [value], target); assert.equal(Object.getPrototypeOf(instance), prototype); assert.equal(instance.db, value);
});
test("newTarget prototype is read once before field assignment without database inspection", () => {
  const Class = load(); const value = metadata(); const prototype = {}; let reads = 0;
  const target = new Proxy(function SyntheticTarget() {}, { get(object, key, receiver) { if (key === "prototype") { reads++; return prototype; } return Reflect.get(object, key, receiver); } });
  const instance = Reflect.construct(Class, [value], target); assert.equal(reads, 1); assert.equal(instance.db, value); assert.equal(Object.getPrototypeOf(instance), prototype);
});
test("exact synchronous newTarget prototype fault propagates once before construction", () => {
  const Class = load(); const fault = Object.freeze({ publicFault: "prototype" }); let reads = 0;
  const target = new Proxy(function SyntheticTarget() {}, { get(object, key, receiver) { if (key === "prototype") { reads++; throw fault; } return Reflect.get(object, key, receiver); } });
  assert.throws(() => Reflect.construct(Class, [metadata()], target), e => e === fault); assert.equal(reads, 1);
});
test("class invocation without new refuses before a metadata read", () => {
  const value = new Proxy({}, { get() { assert.fail("metadata read"); } });
  assert.throws(() => Reflect.apply(load(), undefined, [value]), (e: unknown) => e !== null && typeof e === "object" && (e as { name?: unknown }).name === "TypeError");
});
test("constructor result is its instance and inherited then getter is not assimilated", () => {
  const Class = load(); Object.defineProperty(Class.prototype, "then", { get() { assert.fail("result then"); } });
  const value = metadata(); const instance = new Class(value); assert.equal(instance.db, value); assert.equal(instance instanceof Class, true);
});
