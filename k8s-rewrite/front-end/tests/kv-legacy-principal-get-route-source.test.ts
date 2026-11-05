import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import vm from "node:vm";
import { createRequire } from "node:module";
const ts: typeof import("typescript") = createRequire(import.meta.url)(process.env.BORTUS_PUBLIC_TYPESCRIPT ?? "typescript");

// PUBLIC SOURCE ONLY. Never import or execute the real wrapper, registry, schema,
// constructor or state method. PATCH is captured but never invoked.
type Call = (...args: unknown[]) => unknown;
type Bag = Record<PropertyKey, unknown>;
type Wrapped = { args: unknown[]; token: object };
const routePath = fileURLToPath(new URL("../src/app/api/kv/legacy/route.ts", import.meta.url));
const raw = readFileSync(routePath, "utf8");
const js = ts.transpileModule(raw, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
}}).outputText;
function unreachable(): never { throw new Error("unselected implementation reached"); }
function unread(): object {
  return new Proxy(Object.create(null) as object, {
    get: unreachable, ownKeys: unreachable, getOwnPropertyDescriptor: unreachable,
    getPrototypeOf: unreachable, set: unreachable, has: unreachable,
  });
}
function load(legacy: Bag) {
  const wraps: Wrapped[] = [];
  const human = (...args: unknown[]) => {
    const token = Object.freeze({ wrapper: wraps.length });
    wraps.push({ args, token }); return token;
  };
  const http = Object.defineProperties({}, {
    kvHuman: { value: human }, kvAdminMetadataBody: { get: unreachable },
  });
  const schemas = Object.defineProperty({}, "legacyPrincipal", { get: unreachable });
  const sandboxModule: { exports: Bag } = { exports: {} };
  const requireStub = (id: string) => {
    if (id === "@/lib/kv-http") return http;
    if (id === "@/lib/kv-legacy-access") return legacy;
    if (id === "@/lib/kv-schemas") return schemas;
    throw new Error("unexpected import");
  };
  vm.runInNewContext(js, { module: sandboxModule, exports: sandboxModule.exports, require: requireStub }, { timeout: 1000 });
  assert.equal(wraps.length, 2);
  const callback = wraps[0].args[0] as Call;
  return { callback, wraps, exports: sandboxModule.exports };
}
function constructorFor(instance: object, onConstruct?: (args: unknown[], target: unknown) => void): object {
  const target = function () {};
  return new Proxy(target, { construct: (_target, args, newTarget) => {
    onConstruct?.(args, newTarget); return instance;
  } });
}
function exactThrow(action: () => unknown, expected: unknown) {
  let thrown = false;
  try { action(); } catch (error) { thrown = true; assert.equal(error, expected); }
  assert.equal(thrown, true);
}
function typeError(action: () => unknown) {
  assert.throws(action, (error: unknown) => (error as Error)?.name === "TypeError");
}
const scalarCases: [string, unknown][] = [
  ["undefined", undefined], ["null", null], ["false", false], ["zero", 0],
  ["negative zero", -0], ["NaN", NaN], ["empty", ""], ["string", "public"],
  ["symbol", Symbol("public")], ["bigint", 7n], ["unread object", unread()],
];

test("human legacy-principal GET finite PUBLIC source controls", async (fullContext) => {
  const selected = new Set([
    "constructor lookup, construct, state lookup, call order and exact receiver/arguments",
    "fresh calls reread constructor and construct new instances",
    "reentrant construct call preserves outer receiver and identities",
    "reentrant state.get call preserves outer receiver and identities",
    "reentrant state.call call preserves outer receiver and identities",
  ]);
  const t = {
    test(name: string, callback: () => void | Promise<void>) {
      if (process.env.BORTUS_PUBLIC_CORRECTION_ONLY !== "five-vm-argument-cases" || selected.has(name)) {
        return fullContext.test(name, callback);
      }
      return Promise.resolve();
    },
  };
  await t.test("exact exports and default-status wrappers; PATCH and schema remain inert", () => {
    const h = load(Object.defineProperty({}, "KvLegacyAccess", { get: unreachable }));
    assert.deepEqual(Object.keys(h.exports).sort(), ["GET", "PATCH", "dynamic", "runtime"]);
    assert.equal(h.exports.runtime, "nodejs"); assert.equal(h.exports.dynamic, "force-dynamic");
    assert.equal(h.exports.GET, h.wraps[0].token); assert.equal(h.exports.PATCH, h.wraps[1].token);
    for (const x of h.wraps) { assert.equal(x.args.length, 1); assert.equal(typeof x.args[0], "function"); }
    assert.equal(h.callback.length, 2);
    assert.equal(Object.getPrototypeOf(h.callback).constructor.name, "Function");
    assert.equal(Object.getPrototypeOf(h.wraps[1].args[0]).constructor.name, "AsyncFunction");
  });
  await t.test("constructor lookup, construct, state lookup, call order and exact receiver/arguments", () => {
    const events: string[] = [], registry = unread(), actor = unread(), result = unread();
    const instance = Object.defineProperty({}, "state", { get() {
      events.push("state.get"); return function (this: object, ...args: unknown[]) {
        events.push("state.call"); assert.equal(this, instance); assert.deepEqual(args, [actor]); return result;
      };
    } });
    const ctor = constructorFor(instance, (args, target) => {
      events.push("construct"); assert.equal(args.length, 1); assert.equal(args[0], registry); assert.equal(target, ctor);
    });
    const h = load(Object.defineProperty({}, "KvLegacyAccess", { get() { events.push("constructor.get"); return ctor; } }));
    assert.equal(Reflect.apply(h.callback, unread(), [registry, actor, unread(), unread()]), result);
    assert.deepEqual(events, ["constructor.get", "construct", "state.get", "state.call"]);
  });
  for (const [label, registry] of scalarCases) {
    await t.test(`registry ${label} forwarded verbatim once`, () => {
      const actor = unread(), result = unread(); let constructs = 0, calls = 0;
      const instance = { state(this: object, ...args: unknown[]) {
        calls++; assert.equal(this, instance); assert.deepEqual(args, [actor]); return result;
      } };
      const h = load({ KvLegacyAccess: constructorFor(instance, (args) => {
        constructs++; assert.equal(args.length, 1); assert.equal(args[0], registry);
      }) });
      assert.equal(h.callback(registry, actor), result); assert.equal(constructs, 1); assert.equal(calls, 1);
    });
  }
  for (const [label, actor] of scalarCases) {
    await t.test(`actor ${label} forwarded verbatim exactly once`, () => {
      const instance = { state(this: object, ...args: unknown[]) {
        assert.equal(this, instance); assert.equal(args.length, 1); assert.equal(args[0], actor); return actor;
      } };
      const h = load({ KvLegacyAccess: constructorFor(instance) });
      assert.equal(h.callback(unread(), actor, unread()), actor);
    });
  }
  const resolved = Promise.resolve("public result"), pending = new Promise(() => {});
  const thenable = Object.defineProperty({}, "then", { get: unreachable });
  const results: [string, unknown][] = [...scalarCases, ["array", []], ["function", unreachable],
    ["fulfilled promise", resolved], ["pending promise", pending], ["throwing-then thenable", thenable]];
  for (const [label, result] of results) {
    await t.test(`synchronous raw result ${label} preserves identity without adoption`, () => {
      const h = load({ KvLegacyAccess: constructorFor({ state: () => result }) });
      assert.equal(h.callback(unread(), unread()), result);
    });
  }
  for (const stage of ["constructor.get", "construct", "state.get", "state.call"]) {
    for (const [label, refusal] of scalarCases) {
      await t.test(`${stage} refusal ${label} propagates synchronously and stops later work`, () => {
        const events: string[] = [];
        function step(name: string) { events.push(name); if (name === stage) throw refusal; }
        const instance = Object.defineProperty({}, "state", { get() {
          step("state.get"); return () => { step("state.call"); return unread(); };
        } });
        const ctor = constructorFor(instance, () => step("construct"));
        const h = load(Object.defineProperty({}, "KvLegacyAccess", { get() { step("constructor.get"); return ctor; } }));
        exactThrow(() => h.callback(unread(), unread()), refusal);
        const all = ["constructor.get", "construct", "state.get", "state.call"];
        assert.deepEqual(events, all.slice(0, all.indexOf(stage) + 1));
      });
    }
  }
  for (const [label, invalid] of scalarCases.filter(([, x]) => typeof x !== "object" || x === null)) {
    await t.test(`nonconstructor ${label} fails before any instance work`, () => {
      const h = load({ KvLegacyAccess: invalid }); typeError(() => h.callback(unread(), unread()));
    });
    await t.test(`noncallable state ${label} fails after exactly one getter`, () => {
      let gets = 0;
      const h = load({ KvLegacyAccess: constructorFor(Object.defineProperty({}, "state", { get() { gets++; return invalid; } })) });
      typeError(() => h.callback(unread(), unread())); assert.equal(gets, 1);
    });
  }
  await t.test("arrow constructor is refused without calling it", () => {
    const h = load({ KvLegacyAccess: unreachable });
    // unreachable is constructible; use an arrow to test [[Construct]] refusal.
    const arrow = () => unreachable();
    const other = load({ KvLegacyAccess: arrow }); typeError(() => other.callback(unread(), unread()));
    assert.equal(typeof h.callback, "function");
  });
  await t.test("object nonconstructor and object noncallable state refuse without property traversal", () => {
    typeError(() => load({ KvLegacyAccess: unread() }).callback(unread(), unread()));
    typeError(() => load({ KvLegacyAccess: constructorFor({ state: unread() }) }).callback(unread(), unread()));
  });
  await t.test("inherited constructor and state getters use their original receivers", () => {
    const result = unread(); let moduleReceiver: unknown, stateReceiver: unknown;
    const instance = Object.create(Object.defineProperty({}, "state", { get() { stateReceiver = this; return () => result; } }));
    const legacy = Object.create(Object.defineProperty({}, "KvLegacyAccess", { get() { moduleReceiver = this; return constructorFor(instance); } }));
    assert.equal(load(legacy).callback(unread(), unread()), result);
    assert.equal(moduleReceiver, legacy); assert.equal(stateReceiver, instance);
  });
  await t.test("captured state method survives getter replacing state and constructor", () => {
    const actor = unread(), result = unread(); const legacy: Bag = {};
    const instance = Object.defineProperty({}, "state", { configurable: true, get() {
      Object.defineProperty(instance, "state", { value: unreachable }); legacy.KvLegacyAccess = unreachable;
      return function (this: object, arg: unknown) { assert.equal(this, instance); assert.equal(arg, actor); return result; };
    } });
    legacy.KvLegacyAccess = constructorFor(instance);
    assert.equal(load(legacy).callback(unread(), actor), result);
  });
  for (const [label, primitive] of scalarCases.filter(([, x]) => typeof x !== "object" || x === null)) {
    await t.test(`ordinary constructor primitive return ${label} retains constructed this`, () => {
      const registry = unread(), actor = unread(), result = unread(); let receiver: unknown;
      const ctor = function (this: Bag, ...args: unknown[]) {
        assert.deepEqual(args, [registry]); receiver = this;
        this.state = function (this: object, arg: unknown) { assert.equal(this, receiver); assert.equal(arg, actor); return result; };
        return primitive;
      };
      assert.equal(load({ KvLegacyAccess: ctor }).callback(registry, actor), result);
    });
  }
  for (const kind of ["object", "array", "function"] as const) {
    await t.test(`ordinary constructor explicit ${kind} return is the state receiver`, () => {
      const actor = unread(), result = unread();
      const replacement = kind === "array" ? [] : kind === "function" ? function () {} : {};
      Object.defineProperty(replacement, "state", { value: function (this: object, arg: unknown) {
        assert.equal(this, replacement); assert.equal(arg, actor); return result;
      } });
      const ctor = function () { return replacement; };
      assert.equal(load({ KvLegacyAccess: ctor }).callback(unread(), actor), result);
    });
  }
  await t.test("fresh calls reread constructor and construct new instances", () => {
    const pairs = [[unread(), unread()], [unread(), unread()]], results = [unread(), unread()]; let index = 0;
    const legacy = Object.defineProperty({}, "KvLegacyAccess", { get() {
      const i = index++;
      return constructorFor({ state(arg: unknown) { assert.equal(arg, pairs[i][1]); return results[i]; } }, args => { assert.equal(args.length, 1); assert.equal(args[0], pairs[i][0]); });
    } });
    const h = load(legacy);
    assert.equal(h.callback(...pairs[0]), results[0]); assert.equal(h.callback(...pairs[1]), results[1]); assert.equal(index, 2);
  });
  for (const stage of ["construct", "state.get", "state.call"]) {
    await t.test(`reentrant ${stage} call preserves outer receiver and identities`, () => {
      const registries = [unread(), unread()], actors = [unread(), unread()], results = [unread(), unread()];
      let callback: Call, next = 0, nested = false; const events: string[] = [];
      function reenter(i: number, point: string) {
        events.push(`${i}:${point}`);
        if (i === 0 && point === stage && !nested) { nested = true; assert.equal(callback(registries[1], actors[1]), results[1]); }
      }
      const legacy = Object.defineProperty({}, "KvLegacyAccess", { get() {
        const i = next++;
        const instance = Object.defineProperty({}, "state", { get() {
          reenter(i, "state.get"); return function (this: object, arg: unknown) {
            assert.equal(this, instance); assert.equal(arg, actors[i]); reenter(i, "state.call"); return results[i];
          };
        } });
        return constructorFor(instance, args => { assert.equal(args.length, 1); assert.equal(args[0], registries[i]); reenter(i, "construct"); });
      } });
      callback = load(legacy).callback; assert.equal(callback(registries[0], actors[0]), results[0]);
      assert.equal(next, 2); assert.equal(nested, true);
      const outer = events.filter(x => x.startsWith("0:"));
      assert.deepEqual(outer, ["0:construct", "0:state.get", "0:state.call"]);
      assert.deepEqual(events.filter(x => x.startsWith("1:")), ["1:construct", "1:state.get", "1:state.call"]);
    });
  }
  await t.test("interleaved unsettled calls return their exact promises without cross-call state", async () => {
    const actors = [unread(), unread()]; const values = [Object.freeze({ value: 0 }), Object.freeze({ value: 1 })];
    const resolve: ((x: unknown) => void)[] = [];
    const promises = [new Promise(r => resolve.push(r)), new Promise(r => resolve.push(r))]; let i = 0;
    const legacy = Object.defineProperty({}, "KvLegacyAccess", { get() {
      const n = i++; return constructorFor({ state(arg: unknown) { assert.equal(arg, actors[n]); return promises[n]; } });
    } });
    const h = load(legacy); const first = h.callback(unread(), actors[0]), second = h.callback(unread(), actors[1]);
    assert.equal(first, promises[0]); assert.equal(second, promises[1]);
    resolve[1](values[1]); assert.equal(await second, values[1]); resolve[0](values[0]); assert.equal(await first, values[0]);
  });
});
