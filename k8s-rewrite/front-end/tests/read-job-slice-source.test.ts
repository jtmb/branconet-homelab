import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";

// PUBLIC SOURCE controls: only this exact declaration executes. No app imports.
const compilerPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compilerPath, "explicit infrastructure compiler binding required");
const ts = createRequire(import.meta.url)(compilerPath) as typeof import("typescript");
const filename = fileURLToPath(new URL("../src/lib/job-output.ts", import.meta.url));
const source = readFileSync(filename, "utf8");
const ast = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const declarations = ast.statements.filter((s): s is import("typescript").FunctionDeclaration =>
  ts.isFunctionDeclaration(s) && s.name?.text === "readJobSlice");
assert.equal(declarations.length, 1);
assert.ok(declarations[0].modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword));
const selected = declarations[0].getText(ast).replace(/^export\s+/, "");
const code = ts.transpileModule(selected, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
interface Slice { output: string; nextOffset: number; total: number; status: string }
type ReadSlice = (id: string, cursor: number, client?: unknown) => Promise<Slice | null>;
type Tag = (this: unknown, strings: TemplateStringsArray, ...values: unknown[]) => unknown;
const queryText = "\n    SELECT substr(output, , ) AS output,\n           length(output) AS total, status FROM jobs WHERE id =  LIMIT 1";
function load(bindings: Record<string, unknown> = {}): ReadSlice {
  const context = vm.createContext({ JOB_CHUNK_CHARS: 4096, ...bindings });
  return vm.runInContext(code + "\nreadJobSlice", context) as ReadSlice;
}
function client(tag: Tag) { return { $queryRaw: tag }; }
function row(output = "PUBLIC", total: bigint = 6n, status = "running") { return { output, total, status }; }
function check(actual: Slice | null, output: string, next: number, total: number, status: string) {
  assert.ok(actual);
  assert.deepEqual(Object.keys(actual), ["output", "nextOffset", "total", "status"]);
  assert.equal(actual.output, output); assert.equal(actual.nextOffset, next);
  assert.equal(actual.total, total); assert.equal(actual.status, status);
}

const witnesses: ReadonlyArray<readonly [string, number]> = [
  ["", 0], ["PUBLIC", 6], ["\n\r\t", 3], ["\0", 1], ["é", 1], ["e\u0301", 2],
  ["中", 1], ["😀", 1], ["A😀B", 3], ["👩‍💻", 3], ["🇨🇦", 2],
  ["\ud800", 1], ["\udc00", 1], ["\ud800\ud800", 2], ["\ud800A\udc00", 3],
  ["x".repeat(4096), 4096], ["😀".repeat(4096), 4096],
];
for (const [index, [output, points]] of witnesses.entries()) {
  for (const cursor of [0, 1, 4095, 4096, 65536, -1, 0.5]) {
    test(`PUBLIC row ${index}, cursor ${cursor}: exact metadata and inert tag`, async () => {
      const id = index % 2 ? "PUBLIC-job_1" : "PUBLIC' OR 1=1 --";
      let calls = 0;
      const c = client(function (strings, ...values) {
        calls++; assert.equal(this, c); assert.equal(strings.join(""), queryText);
        assert.equal(strings.raw.join(""), queryText);
        assert.ok(Object.isFrozen(strings)); assert.ok(Object.isFrozen(strings.raw));
        assert.deepEqual(values, [cursor + 1, 4096, id]);
        return [row(output, 12345n, "PUBLIC-status")];
      });
      check(await load()(id, cursor, c), output, cursor + points, 12345, "PUBLIC-status");
      assert.equal(calls, 1);
    });
  }
}

for (const value of [undefined, null, false, 0, ""]) {
  test(`PUBLIC falsy row ${String(value)}: null without projection`, async () => {
    let calls = 0;
    assert.equal(await load()("PUBLIC", 0, client(() => { calls++; return [value]; })), null);
    assert.equal(calls, 1);
  });
}
test("PUBLIC empty rows and immediate fulfilled Promise: null", async () => {
  assert.equal(await load()("PUBLIC", 0, client(() => Promise.resolve([]))), null);
});
for (const total of [0n, 1n, 4096n, 9007199254740991n, 9007199254740992n, 9007199254740993n]) {
  test(`PUBLIC bigint ${total}: existing Number conversion characterized`, async () => {
    check(await load()("PUBLIC", 2, client(() => [row("😀", total)])), "😀", 3, Number(total), "running");
  });
}
for (const cursor of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
  test(`PUBLIC cursor ${cursor}: arithmetic characterization, no validation claim`, async () => {
    const actual = await load()("PUBLIC", cursor, client((_, ...values) => {
      assert.equal(values[0], cursor + 1); return [row("A", 1n)];
    }));
    check(actual, "A", cursor + 1, 1, "running");
  });
}
test("PUBLIC default client used for omitted and explicit undefined only", async () => {
  let calls = 0;
  const fake = client(() => { calls++; return [row()]; });
  const read = load({ prisma: fake });
  check(await read("PUBLIC", 0), "PUBLIC", 6, 6, "running");
  check(await read("PUBLIC", 1, undefined), "PUBLIC", 7, 6, "running");
  assert.equal(calls, 2);
  await assert.rejects(read("PUBLIC", 0, null), { name: "TypeError" });
  assert.equal(calls, 2);
});
test("PUBLIC explicit client never touches missing default binding", async () => {
  check(await load()("PUBLIC", 0, client(() => [row()])), "PUBLIC", 6, 6, "running");
  await assert.rejects(load()("PUBLIC", 0), { name: "ReferenceError" });
});
test("PUBLIC property and built-in evaluation order, two distinct output reads", async () => {
  const trace: string[] = [];
  let outputReads = 0;
  const fakeRow = {
    get output() { trace.push("output" + ++outputReads); return outputReads === 1 ? "PUBLIC-first" : "😀"; },
    get total() { trace.push("total"); return 31n; },
    get status() { trace.push("status"); return "PUBLIC-final"; },
  };
  const a = { get from() { trace.push("from-lookup"); return function (this: unknown, value: unknown) {
    trace.push("from-call"); assert.equal(this, a); assert.equal(value, "😀");
    return { get length() { trace.push("length"); return 1; } };
  }; } };
  const c = { get $queryRaw() { trace.push("tag-lookup"); return function (this: unknown) {
    trace.push("tag-call"); assert.equal(this, c);
    return { get then() { trace.push("then-lookup"); return undefined; }, get 0() { trace.push("row0"); return fakeRow; } };
  }; } };
  const number = (value: unknown) => { trace.push("number-call"); assert.equal(value, 31n); return 31; };
  check(await load({ Array: a, Number: number })("PUBLIC", 5, c), "PUBLIC-first", 6, 31, "PUBLIC-final");
  assert.deepEqual(trace, ["tag-lookup", "tag-call", "then-lookup", "row0", "output1", "from-lookup", "output2", "from-call", "length", "total", "number-call", "status"]);
});
test("PUBLIC no application initializer or ambient process bindings", async () => {
  const read = load();
  assert.ok(!code.includes("require("));
  check(await read("PUBLIC", 0, client(() => [row()])), "PUBLIC", 6, 6, "running");
});
test("PUBLIC global Number lookup precedes total getter", async () => {
  const trace: string[] = [];
  const context = vm.createContext({ JOB_CHUNK_CHARS: 4096 });
  Object.defineProperty(context, "Number", { get() { trace.push("Number-lookup"); return (v: unknown) => { trace.push("Number-call"); assert.equal(v, 1n); return 1; }; } });
  const read = vm.runInContext(code + "\nreadJobSlice", context) as ReadSlice;
  const data = { output: "A", get total() { trace.push("total"); return 1n; }, status: "PUBLIC" };
  check(await read("PUBLIC", 0, client(() => [data])), "A", 1, 1, "PUBLIC");
  assert.deepEqual(trace, ["Number-lookup", "total", "Number-call"]);
});
test("PUBLIC constant binding resolves between cursor arithmetic and id substitution", async () => {
  const trace: string[] = [];
  const context = vm.createContext({});
  Object.defineProperty(context, "JOB_CHUNK_CHARS", { get() { trace.push("chunk"); return 4096; } });
  const read = vm.runInContext(code + "\nreadJobSlice", context) as ReadSlice;
  const cursor = { [Symbol.toPrimitive]() { trace.push("cursor"); return 0; } };
  const c = { get $queryRaw() { trace.push("tag"); return (_: TemplateStringsArray, ...v: unknown[]) => {
    trace.push("call"); assert.equal(v[2], "PUBLIC"); return [];
  }; } };
  assert.equal(await read("PUBLIC", cursor as unknown as number, c), null);
  assert.deepEqual(trace, ["tag", "cursor", "chunk", "call"]);
});
test("PUBLIC result and tag template identity across repeated calls", async () => {
  const strings: TemplateStringsArray[] = [];
  const read = load();
  const c = client(s => { strings.push(s); return [row()]; });
  const first = await read("PUBLIC", 0, c), second = await read("PUBLIC", 0, c);
  assert.notEqual(first, second); assert.equal(strings[0], strings[1]);
});
test("PUBLIC substitutions evaluate left to right after tag lookup", async () => {
  const trace: string[] = [];
  const value = { [Symbol.toPrimitive](hint: string) { trace.push("cursor:" + hint); return 2; } };
  const c = { get $queryRaw() { trace.push("tag"); return (_: TemplateStringsArray, ...v: unknown[]) => {
    trace.push("call"); assert.deepEqual(v, [3, 4096, "PUBLIC"]); return [];
  }; } };
  assert.equal(await load()("PUBLIC", value as unknown as number, c), null);
  assert.deepEqual(trace, ["tag", "cursor:default", "call"]);
});

// Injected binding/error characterizations are separate from ordinary SQL row semantics.
for (const stage of ["tag-lookup", "tag-call", "tag-rejection", "then-lookup", "row0", "output1", "from-lookup", "output2", "from-call", "length", "total", "number-call", "status"]) {
  test(`PUBLIC immediate fault ${stage}: same rejection, one query maximum`, async () => {
    const fault = Object.freeze({ publicFault: stage });
    const trace: string[] = [];
    const touch = (s: string) => { trace.push(s); if (s === stage) throw fault; };
    let outputs = 0;
    const fakeRow = { get output() { touch("output" + ++outputs); return "A"; }, get total() { touch("total"); return 1n; }, get status() { touch("status"); return "PUBLIC"; } };
    const a = { get from() { touch("from-lookup"); return () => { touch("from-call"); return { get length() { touch("length"); return 1; } }; }; } };
    const n = () => { touch("number-call"); return 1; };
    const c = { get $queryRaw() { touch("tag-lookup"); return () => {
      touch("tag-call"); if (stage === "tag-rejection") { trace.push("tag-rejection"); return Promise.reject(fault); }
      return { get then() { touch("then-lookup"); return undefined; }, get 0() { touch("row0"); return fakeRow; } };
    }; } };
    await assert.rejects(load({ Array: a, Number: n })("PUBLIC", 0, c), error => error === fault);
    assert.equal(trace.at(-1), stage); assert.equal(trace.filter(x => x === "tag-call").length, stage === "tag-lookup" ? 0 : 1);
  });
}
test("PUBLIC cursor coercion fault rejects before tagged call", async () => {
  const fault = Object.freeze({ publicFault: "cursor" }); let calls = 0;
  const cursor = { [Symbol.toPrimitive]() { throw fault; } };
  await assert.rejects(load()("PUBLIC", cursor as unknown as number, client(() => { calls++; return []; })), e => e === fault);
  assert.equal(calls, 0);
});
test("PUBLIC absent constant rejects before tagged call", async () => {
  const context = vm.createContext({}); let calls = 0;
  const read = vm.runInContext(code + "\nreadJobSlice", context) as ReadSlice;
  await assert.rejects(read("PUBLIC", 0, client(() => { calls++; return []; })), { name: "ReferenceError" });
  assert.equal(calls, 0);
});
test("PUBLIC invalid rows result rejects without retry", async () => {
  for (const result of [null, undefined]) {
    let calls = 0;
    await assert.rejects(load()("PUBLIC", 0, client(() => { calls++; return result; })), { name: "TypeError" });
    assert.equal(calls, 1);
  }
});
