import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";

// PUBLIC source controls only. No module initializer, runner, input file or service executes.
const compilerPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compilerPath, "An explicit compiler infrastructure binding is required");
const ts = createRequire(import.meta.url)(compilerPath) as typeof import("typescript");
const sourcePath = fileURLToPath(new URL("../src/lib/ansible-selection.ts", import.meta.url));
const source = ts.createSourceFile(sourcePath, readFileSync(sourcePath, "utf8"), ts.ScriptTarget.Latest, true);
const declarations = source.statements.filter((node): node is import("typescript").FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === "ansibleSelection"
  && !!node.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(declarations.length, 1);
const selected = declarations[0].getText(source).replace(/^export\s+/, "");
const compiled = ts.transpileModule(selected, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  reportDiagnostics: true,
});
assert.equal(compiled.diagnostics?.length, 0);
const roles = Object.freeze(["bootstrap", "kubernetes", "network", "dns", "storage", "longhorn", "nfs", "samba", "ingress", "gitops", "secrets"]);
class SelectionFailure extends Error {
  constructor() { super("Use site.yml and the supported provisioning roles"); }
}
type Selection = (playbook?: unknown, requestedRoles?: unknown) => { playbook: string; roles: unknown };
function load(bindings: Record<string, unknown> = {}): Selection {
  return vm.runInNewContext(`${compiled.outputText}\nansibleSelection;`, {
    ANSIBLE_ROLES: roles, Array, Set, AnsibleSelectionError: SelectionFailure, ...bindings,
  }, { timeout: 1000 }) as Selection;
}
const select = load();
function accepted(input: unknown[], actual = select("site.yml", input)) {
  assert.equal(actual.playbook, "site.yml");
  assert.equal(actual.roles, input);
  assert.deepEqual(Object.keys(actual), ["playbook", "roles"]);
}
function refused(playbook: unknown, requested: unknown, fn = select) {
  assert.throws(() => fn(playbook, requested), error => error instanceof SelectionFailure
    && error.message === "Use site.yml and the supported provisioning roles");
}

test("omitted arguments select site.yml and an empty array", () => {
  const value = select();
  assert.equal(value.playbook, "site.yml");
  assert.equal(Array.isArray(value.roles), true);
  assert.equal((value.roles as unknown[]).length, 0);
});
test("explicit undefined arguments apply both defaults", () => {
  const value = select(undefined, undefined);
  assert.equal(value.playbook, "site.yml");
  assert.equal((value.roles as unknown[]).length, 0);
});
test("playbook default is independent from the supplied role list", () => {
  const input = ["dns"];
  accepted(input, select(undefined, input));
});
test("default role arrays and result objects are fresh", () => {
  const a = select(), b = select();
  assert.notEqual(a, b);
  assert.notEqual(a.roles, b.roles);
  (a.roles as unknown[]).push("dns");
  assert.equal((b.roles as unknown[]).length, 0);
});
test("empty supplied role array is retained", () => accepted([]));
test("all supported roles retain input order and identity", () => {
  const input = [...roles].reverse();
  accepted(input);
  assert.deepEqual(input, [...roles].reverse());
});
test("frozen supported role arrays are not mutated", () => {
  const input = Object.freeze(["secrets", "dns"]);
  const result = select("site.yml", input);
  assert.equal(result.roles, input);
  assert.deepEqual(input, ["secrets", "dns"]);
});
test("fresh result objects retain the same supplied array without copying", () => {
  const input = ["bootstrap"];
  const a = select("site.yml", input), b = select("site.yml", input);
  assert.notEqual(a, b);
  assert.equal(a.roles, input);
  assert.equal(b.roles, input);
});
for (const role of roles) {
  test(`supported singleton ${role}`, () => accepted([role]));
  test(`duplicate supported role ${role} is refused`, () => refused("site.yml", [role, role]));
}
const invalidPlaybooks: [string, unknown][] = [
  ["null", null], ["false", false], ["true", true], ["zero", 0], ["one", 1],
  ["empty", ""], ["relative", "./site.yml"], ["parent", "../site.yml"],
  ["other extension", "site.yaml"], ["case", "SITE.yml"], ["suffix", "site.yml "],
  ["flag", "--help"], ["array", ["site.yml"]], ["object", {}],
  ["boxed string", Object("site.yml")], ["symbol", Symbol("public")],
  ["bigint", 1n], ["uncoercible", { toString() { throw new Error("must remain inert"); } }],
];
for (const [name, playbook] of invalidPlaybooks) {
  test(`invalid playbook ${name} refuses without inspecting roles`, () => {
    const untouched = new Proxy([], { get() { assert.fail("roles were inspected"); } });
    refused(playbook, untouched);
  });
}
const nonArrays: [string, unknown][] = [
  ["null", null], ["false", false], ["true", true], ["zero", 0], ["one", 1],
  ["string", "dns"], ["empty string", ""], ["object", {}], ["array-like", { 0: "dns", length: 1 }],
  ["set", new Set(["dns"])], ["typed array", new Uint8Array([1])],
  ["function", () => []], ["symbol", Symbol("public")], ["bigint", 1n],
];
for (const [name, value] of nonArrays) test(`non-array roles ${name} refuse`, () => refused("site.yml", value));
for (const name of ["", "DNS", "dns ", " dns", "../dns", "--tags", "unknown", "dns,storage"]) {
  test(`unsupported role spelling ${JSON.stringify(name)} refuses`, () => refused("site.yml", [name]));
}
const nonStrings: [string, unknown][] = [
  ["undefined", undefined], ["null", null], ["boolean", false], ["number", 1], ["bigint", 1n],
  ["symbol", Symbol("public")], ["object", {}], ["array", ["dns"]], ["boxed", Object("dns")],
  ["function", () => "dns"], ["uncoercible", { toString() { throw new Error("must remain inert"); } }],
];
for (const [name, value] of nonStrings) test(`non-string role ${name} refuses`, () => refused("site.yml", [value]));
test("more than eleven requested roles refuse before some or iteration", () => {
  const input = new Proxy(new Array(12), {
    get(target, key, receiver) {
      if (key === "some" || key === Symbol.iterator) assert.fail("late operation reached");
      return Reflect.get(target, key, receiver);
    },
  });
  refused("site.yml", input);
});
test("unknown role refuses before constructing Set", () => {
  class ForbiddenSet { constructor() { assert.fail("Set reached"); } }
  refused("site.yml", ["unknown"], load({ Set: ForbiddenSet }));
});
test("non-string role short-circuits registry includes", () => {
  const registry = { length: 11, get includes() { assert.fail("includes reached"); return undefined; } };
  refused("site.yml", [null], load({ ANSIBLE_ROLES: registry }));
});
test("invalid playbook short-circuits even Array.isArray property access", () => {
  const array = { get isArray() { assert.fail("Array reached"); return undefined; } };
  refused("other.yml", [], load({ Array: array }));
});
test("false Array.isArray short-circuits role and registry length reads", () => {
  const registry = { get length() { assert.fail("registry length reached"); return 0; } };
  const input = new Proxy([], { get() { assert.fail("input reached"); } });
  refused("site.yml", input, load({ Array: { isArray: () => false }, ANSIBLE_ROLES: registry }));
});
function trace() {
  const events: string[] = [];
  const input = new Proxy(["dns"], {
    get(target, key, receiver) {
      if (key === "length") events.push("roles.length");
      if (key === "some") {
        events.push("roles.some:get");
        return (predicate: (value: unknown) => boolean) => {
          events.push("roles.some:call");
          return predicate("dns");
        };
      }
      return Reflect.get(target, key, receiver);
    },
  });
  const array = { get isArray() { events.push("Array.isArray:get"); return (value: unknown) => { events.push("Array.isArray:call"); return Array.isArray(value); }; } };
  const registry = {
    get length() { events.push("registry.length"); return 11; },
    get includes() { events.push("registry.includes:get"); return (value: unknown) => { events.push("registry.includes:call"); return value === "dns"; }; },
  };
  class ImmediateSet {
    constructor(value: unknown) { events.push("Set:construct"); assert.equal(value, input); }
    get size() { events.push("Set.size"); return 1; }
  }
  const fn = load({ Array: array, ANSIBLE_ROLES: registry, Set: ImmediateSet });
  return { input, fn, events };
}
test("immediate binding order matches source before a successful return", () => {
  const { input, fn, events } = trace();
  accepted(input, fn("site.yml", input));
  assert.deepEqual(events, ["Array.isArray:get", "Array.isArray:call", "roles.length", "registry.length", "roles.some:get", "roles.some:call", "registry.includes:get", "registry.includes:call", "Set:construct", "Set.size", "roles.length"]);
});
test("immediate binding reads are repeated on each invocation", () => {
  const { input, fn, events } = trace();
  fn("site.yml", input);
  const first = [...events]; events.length = 0;
  fn("site.yml", input);
  assert.deepEqual(events, first);
});
const sentinel = new Error("public immediate failure");
const explode = () => { throw sentinel; };
const failureBindings: [string, () => Record<string, unknown>][] = [
  ["Array.isArray getter", () => ({ Array: { get isArray() { throw sentinel; } } })],
  ["Array.isArray call", () => ({ Array: { isArray: explode } })],
  ["registry length", () => ({ ANSIBLE_ROLES: { get length() { throw sentinel; } } })],
  ["registry includes getter", () => ({ ANSIBLE_ROLES: { length: 11, get includes() { throw sentinel; } } })],
  ["registry includes call", () => ({ ANSIBLE_ROLES: { length: 11, includes: explode } })],
  ["Set construction", () => ({ Set: new Proxy(Set, { construct() { throw sentinel; } }) })],
  ["Set size", () => ({ Set: class { get size() { throw sentinel; } } })],
];
for (const [name, bindings] of failureBindings) test(`immediate ${name} failure propagates unchanged`, () => {
  assert.throws(() => load(bindings())("site.yml", ["dns"]), error => error === sentinel);
});
for (const point of ["length", "some"] as const) test(`immediate roles ${point} getter failure propagates`, () => {
  const input = new Proxy(["dns"], { get(target, key, receiver) {
    if (key === point) throw sentinel;
    return Reflect.get(target, key, receiver);
  } });
  assert.throws(() => select("site.yml", input), error => error === sentinel);
});
test("immediate roles.some call failure propagates", () => {
  const input = Object.assign(["dns"], { some: explode });
  assert.throws(() => select("site.yml", input), error => error === sentinel);
});
test("second roles.length read remains distinct from the first", () => {
  let reads = 0;
  const input = new Proxy(["dns"], { get(target, key, receiver) {
    if (key === "length" && ++reads === 2) throw sentinel;
    if (key === "some") return () => false;
    return Reflect.get(target, key, receiver);
  } });
  const fn = load({ Set: class { size = 1; } });
  assert.throws(() => fn("site.yml", input), error => error === sentinel);
  assert.equal(reads, 2);
});
test("error constructor failure propagates without replacement", () => {
  const error = new Proxy(SelectionFailure, { construct() { throw sentinel; } });
  assert.throws(() => load({ AnsibleSelectionError: error })("other.yml", []), value => value === sentinel);
});
test("unsupported custom noncallable some characterizes JavaScript TypeError", () => {
  const input = Object.assign(["dns"], { some: null });
  assert.throws(() => select("site.yml", input), error => (error as Error).name === "TypeError");
});
test("unsupported sparse single hole is characterized without a production correction", () => {
  const input = new Array(1);
  accepted(input);
  assert.equal(0 in input, false);
});
test("unsupported repeated holes fail the Set cardinality comparison", () => refused("site.yml", new Array(2)));
test("input changes are freshly validated on the next call", () => {
  const input = ["dns"];
  accepted(input);
  input[0] = "unknown";
  refused("site.yml", input);
});
test("supported public role metadata is read freshly on the next call", () => {
  const registry = ["dns"];
  const fn = load({ ANSIBLE_ROLES: registry });
  const input = ["dns"];
  accepted(input, fn("site.yml", input));
  registry[0] = "storage";
  refused("site.yml", ["dns"], fn);
});
