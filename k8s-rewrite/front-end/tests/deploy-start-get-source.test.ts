import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import test from "node:test";
import vm from "node:vm";

// NEW finite PUBLIC SOURCE controls. Only the exact GET declaration executes.
// Actual imports, module initializers, authorization, capabilities and jobs are inert.
const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compiler, "an explicit frozen compiler path is required");
const ts = createRequire(import.meta.url)(compiler);
const source = readFileSync(resolve("src/app/api/deploy/start/route.ts"), "utf8");
const parsed = ts.createSourceFile("selected.ts", source, ts.ScriptTarget.Latest, true);
const declarations = parsed.statements.filter((node: { name?: { text: string } }) =>
  ts.isFunctionDeclaration(node) && node.name?.text === "GET");
assert.equal(declarations.length, 1);
const selected = declarations[0];
assert.equal(selected.parameters.length, 0);
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(selected.modifiers.some((m: { kind: number }) => m.kind === ts.SyntaxKind.AsyncKeyword));
const declaration: string = selected.getText(parsed);
const emitted: string = ts.transpileModule(declaration.replace(/^export /, ""), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText;

type Settings = { ids?: string[]; fault?: string; result?: unknown; keysResult?: Iterable<string> };
function harness(settings: Settings = {}) {
  const trace: string[] = [];
  const fault = Error("PUBLIC-SOURCE-FAULT");
  const ids = settings.ids ?? ["PUBLIC-JOB-2", "PUBLIC-JOB-1"];
  const result = settings.result ?? Object.freeze({ public: "RESPONSE" });
  let body: { activeJobIds: string[] } | undefined;
  let argumentsCount = 0;
  let index = 0;
  let jsonReceiver: unknown;
  let keysReceiver: unknown;
  let fromReceiver: unknown;
  function mark(name: string) { trace.push(name); if (settings.fault === name) throw fault; }
  const iterator = {
    get [Symbol.iterator]() {
      mark("iterator:get");
      return function () { mark("iterator:call"); return iterator; };
    },
    get next() {
      mark("next:get");
      return function () {
        mark("next:" + index);
        return index < ids.length ? { done: false, value: ids[index++] } : { done: true };
      };
    },
  };
  const activeJobs = {
    get keys() {
      mark("keys:get");
      return function (this: unknown) { keysReceiver = this; mark("keys:call"); return settings.keysResult ?? iterator; };
    },
    get values(): never { throw Error("ACTUAL JOB VALUES MUST REMAIN INERT"); },
    get entries(): never { throw Error("ACTUAL JOB ENTRIES MUST REMAIN INERT"); },
  };
  const arrayBinding = {
    get from() {
      mark("from:get");
      return function (this: unknown, items: Iterable<string>) {
        fromReceiver = this; mark("from:call"); return Array.from(items);
      };
    },
  };
  const responseBinding = {
    get json() {
      mark("json:get");
      return function (this: unknown, value: { activeJobIds: string[] }) {
        jsonReceiver = this; argumentsCount = arguments.length;
        mark("json:call"); body = value; return result;
      };
    },
  };
  const bindings = {
    NextResponse: responseBinding, activeJobs, Array: arrayBinding,
    get requireOperator(): never { throw Error("ACTUAL AUTHORIZATION MUST REMAIN INERT"); },
    get runtimeCapabilities(): never { throw Error("ACTUAL CAPABILITIES MUST REMAIN INERT"); },
    get prisma(): never { throw Error("ACTUAL DATABASE MUST REMAIN INERT"); },
    get runAnsiblePlaybook(): never { throw Error("ACTUAL PROVISIONING MUST REMAIN INERT"); },
    get setTimeout(): never { throw Error("ACTUAL TIMERS MUST REMAIN INERT"); },
  };
  const GET = new vm.Script(emitted + "\nGET", { filename: "selected-deploy-start-GET.js" })
    .runInNewContext(bindings, { timeout: 1000, contextCodeGeneration: { strings: false, wasm: false } }) as () => Promise<unknown>;
  return { GET, trace, ids, fault, result, activeJobs, arrayBinding, responseBinding,
    body: () => body, argumentsCount: () => argumentsCount,
    receivers: () => [jsonReceiver, keysReceiver, fromReceiver] };
}
const prefix = ["json:get", "from:get", "keys:get", "keys:call", "from:call", "iterator:get", "iterator:call", "next:get"];
const expected = (count: number) => [...prefix, ...Array.from({ length: count + 1 }, (_, i) => "next:" + i), "json:call"];

test("exact GET selection is exported async zero-argument declaration only", () => {
  assert.match(declaration, /^export async function GET\(\) \{/);
  assert.equal(declaration.includes("async function runAnsible"), false);
  assert.equal(declaration.includes("requireOperator"), false);
  assert.equal(declaration.includes("runtimeCapabilities"), false);
});
test("creating the exact declaration executes no body or imported initializer", () => {
  const h = harness(); assert.deepEqual(h.trace, []);
});
test("successful source-derived member/call/iteration order is exact", async () => {
  const h = harness(); assert.equal(await h.GET(), h.result); assert.deepEqual(h.trace, expected(2));
});
test("json, keys and from receive their original member receivers", async () => {
  const h = harness(); await h.GET(); assert.deepEqual(h.receivers(), [h.responseBinding, h.activeJobs, h.arrayBinding]);
});
test("json gets exactly one argument and only activeJobIds metadata", async () => {
  const h = harness(); await h.GET(); assert.equal(h.argumentsCount(), 1);
  assert.deepEqual(Object.keys(h.body()!), ["activeJobIds"]); assert.deepEqual(h.body()!.activeJobIds, h.ids);
});
for (const [name, ids] of [
  ["empty", []], ["one", ["PUBLIC-1"]], ["insertion order", ["PUBLIC-9", "PUBLIC-2", "PUBLIC-7"]],
  ["Unicode", ["PUBLIC-\u03b1", "PUBLIC-\ud83d\ude80"]],
  ["special metadata names", ["__proto__", "constructor", "toString"]],
] as [string, string[]][]) {
  test("finite PUBLIC IDs preserve " + name, async () => {
    const h = harness({ ids }); await h.GET(); assert.deepEqual(h.body()!.activeJobIds, ids); assert.deepEqual(h.trace, expected(ids.length));
  });
}
test("each invocation obtains a fresh metadata snapshot", async () => {
  const h = harness({ ids: [] }); await h.GET(); const first = h.body()!.activeJobIds;
  h.ids.push("PUBLIC-NEXT"); h.trace.length = 0; await h.GET();
  assert.deepEqual(first, []); assert.deepEqual(h.body()!.activeJobIds, ["PUBLIC-NEXT"]);
  assert.notEqual(first, h.body()!.activeJobIds); assert.deepEqual(h.trace, expected(1));
});
test("all synchronous body work precedes the returned Promise settlement", async () => {
  const h = harness(); const pending = h.GET(); assert.deepEqual(h.trace, expected(2));
  assert.equal(typeof pending.then, "function"); assert.equal(await pending, h.result);
});
test("a synthetic response thenable is adopted by the async return", async () => {
  const token = Object.freeze({ public: "THENABLE-RESULT" });
  const h = harness({ result: { then: (done: (x: unknown) => void) => done(token) } });
  assert.equal(await h.GET(), token); assert.deepEqual(h.trace, expected(2));
});
test("an inert finite Map exposes keys without inspecting job values", async () => {
  const values = new Map<string, unknown>([["PUBLIC-B", Object.freeze({})], ["PUBLIC-A", Object.freeze({})]]);
  const h = harness({ keysResult: values.keys() }); await h.GET();
  assert.deepEqual(h.body()!.activeJobIds, ["PUBLIC-B", "PUBLIC-A"]);
  assert.deepEqual(h.trace, ["json:get", "from:get", "keys:get", "keys:call", "from:call", "json:call"]);
});
for (const point of [...prefix, "next:0", "next:1", "next:2", "json:call"]) {
  test("exact PUBLIC fault at " + point + " rejects without later calls", async () => {
    const h = harness({ fault: point }); const all = expected(2);
    await assert.rejects(h.GET(), e => e === h.fault);
    assert.deepEqual(h.trace, all.slice(0, all.indexOf(point) + 1)); assert.equal(h.body(), undefined);
  });
}
test("synthetic response rejection is preserved without a second json call", async () => {
  const fault = Error("PUBLIC-RESPONSE-REJECTION");
  const h = harness({ result: { then: (_done: unknown, reject: (x: unknown) => void) => reject(fault) } });
  await assert.rejects(h.GET(), e => e === fault); assert.deepEqual(h.trace, expected(2));
});
test("authorization/capability/database/provisioning/timer bindings stay unread", async () => {
  const h = harness(); await h.GET(); assert.deepEqual(h.trace, expected(2));
  // This is an exact-declaration boundary check, not real authorization qualification.
});
