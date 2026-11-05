import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import vm from "node:vm";
import test from "node:test";

// PUBLIC SOURCE controls only. Never import job-output, Prisma, db or job-stream.
// SQL text is observed at an inert tag; it is never sent to an SQL implementation.
const requireTool = createRequire(import.meta.url);
const typescriptPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(typescriptPath, "An explicit BORTUS_SOURCE_TYPESCRIPT binding is required");
const ts = requireTool(typescriptPath) as typeof import("typescript");
const sourcePath = path.resolve("src/lib/job-output.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const parsed = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true);
const selected = parsed.statements.filter((node): node is import("typescript").FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === "readJobTail");
assert.equal(selected.length, 1);
const declaration = selected[0].getText(parsed);
assert.ok(selected[0].modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(selected[0].modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.AsyncKeyword));
const compiled = ts.transpileModule(declaration.replace(/^export /, "") + "\nreadJobTail;", {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText;

type TailResult = { output: unknown; total: number; cursor: number; truncated: boolean } | null;
type Tail = (id: unknown, chars: unknown, client?: unknown) => Promise<TailResult>;
type Call = { receiver: unknown; strings: TemplateStringsArray; values: unknown[] };
type Setup = {
  result?: unknown;
  query?: (call: Call) => unknown;
  number?: (value: unknown) => number;
  defaultClient?: () => unknown;
};

function harness(setup: Setup = {}) {
  const events: string[] = [];
  const calls: Call[] = [];
  const client = Object.defineProperty({}, "$queryRaw", { get() {
    events.push("query:get");
    return function (this: unknown, strings: TemplateStringsArray, ...values: unknown[]) {
      events.push("query:call");
      const call = { receiver: this, strings, values };
      calls.push(call);
      return setup.query ? setup.query(call) : setup.result;
    };
  } });
  const context = Object.create(null) as Record<string, unknown>;
  const bindings = Object.create(null) as Record<string, unknown>;
  Object.defineProperty(bindings, "prisma", { get() {
    events.push("default:get");
    return setup.defaultClient ? setup.defaultClient() : client;
  } });
  if (setup.number) bindings.Number = setup.number;
  context.bindings = bindings;
  // An ordinary lexical object getter preserves thrown error identity. A throwing
  // contextified global accessor can be surfaced by vm as a missing-name error.
  const fn = vm.runInNewContext("with (bindings) {\n" + compiled + "\n}", context, { timeout: 1000 }) as Tail;
  return { fn, client, events, calls };
}

const publicId = "public-job-metadata";
const sql = ["\n    SELECT substr(output, -", ") AS output, length(output) AS total FROM jobs WHERE id = ", " LIMIT 1"];

for (const total of [0n, 1n, 5n, 6n, 25n, 9007199254740993n]) {
  for (const chars of [0, 1, 5, 25]) {
    test(`public total ${total} / chars ${chars}: result projection and unchanged substitutions`, async () => {
      const h = harness({ result: [{ output: "public-output-metadata", total }] });
      const result = await h.fn(publicId, chars, h.client);
      assert.ok(result);
      assert.deepEqual({ ...result }, { output: "public-output-metadata", total: Number(total), cursor: Number(total), truncated: Number(total) > chars });
      assert.equal(h.calls.length, 1);
      assert.equal(h.calls[0].receiver, h.client);
      assert.deepEqual([...h.calls[0].strings], sql);
      assert.deepEqual([...h.calls[0].strings.raw], sql);
      assert.deepEqual(h.calls[0].values, [chars, publicId]);
      assert.deepEqual(h.events, ["query:get", "query:call"]);
    });
  }
}

for (const chars of [-1, -0, 0.5, NaN, Infinity, -Infinity, Number.MAX_SAFE_INTEGER]) {
  test(`count ${String(chars)} is characterized as immediate metadata without SQL claims`, async () => {
    const h = harness({ result: [{ output: "public-characterization", total: 2n }] });
    const result = await h.fn(publicId, chars, h.client);
    assert.ok(result);
    assert.ok(Object.is(h.calls[0].values[0], chars));
    assert.equal(result.truncated, 2 > chars);
  });
}

for (const id of ["", "public-'quoted'", "public-😀", "public-\u0000-id", "public-\ud800", "public-; SELECT inert_metadata"]) {
  test(`job ID ${JSON.stringify(id)} remains an unchanged inert substitution`, async () => {
    const h = harness({ result: [] });
    assert.equal(await h.fn(id, 4, h.client), null);
    assert.equal(h.calls[0].values[1], id);
    assert.deepEqual([...h.calls[0].strings], sql);
  });
}

for (const row of [undefined, null, false, 0, -0, NaN, "", 0n]) {
  test(`falsy first-row ${String(row)} returns null without later field access`, async () => {
    const rows = new Proxy([row], { get(target, key, receiver) {
      if (key === "then") return undefined;
      assert.equal(key, "0");
      return Reflect.get(target, key, receiver);
    } });
    const h = harness({ result: rows, number() { assert.fail("Number must stay inert"); } });
    assert.equal(await h.fn(publicId, 5, h.client), null);
    assert.equal(h.calls.length, 1);
  });
}

for (const output of ["", "public", "public-😀", "public-\ud800", undefined, null, false, 0, { publicMetadata: true }]) {
  test(`output metadata ${JSON.stringify(output)} is returned unchanged`, async () => {
    const h = harness({ result: [{ output, total: 7n }] });
    const result = await h.fn(publicId, 5, h.client);
    assert.ok(result);
    assert.equal(result.output, output);
    assert.equal(result.total, 7);
  });
}

for (const total of [undefined, null, true, false, "7", "public-nonnumeric", -0, NaN, Infinity, -Infinity]) {
  test(`Number total ${String(total)} is characterized without precision or SQL qualification`, async () => {
    const h = harness({ result: [{ output: "public-total-metadata", total }] });
    const result = await h.fn(publicId, 5, h.client);
    assert.ok(result);
    assert.ok(Object.is(result.total, Number(total)));
    assert.ok(Object.is(result.cursor, result.total));
    assert.equal(result.truncated, Number(total) > 5);
  });
}

test("source-derived order: receiver/tag, await, first row, total conversion, output, comparison", async () => {
  const events: string[] = [];
  const chars = { [Symbol.toPrimitive](hint: string) { events.push(`chars:${hint}`); return 5; } };
  const id = { toString() { assert.fail("ID coercion must remain inert"); } };
  const row = Object.defineProperties({}, {
    total: { get() { events.push("total:get"); return 7n; } },
    output: { get() { events.push("output:get"); return "public-ordered-metadata"; } },
  });
  const rows = new Proxy([row], { get(target, key, receiver) {
    events.push(`rows:${String(key)}`); return Reflect.get(target, key, receiver);
  } });
  const h = harness({
    query(call) {
      events.push("tag");
      assert.equal(call.values[0], chars); assert.equal(call.values[1], id);
      return { then(resolve: (value: unknown) => void) { events.push("await:then"); resolve(rows); } };
    },
    number(value) { events.push("Number"); return Number(value); },
  });
  const promise = h.fn(id, chars, h.client);
  assert.deepEqual(events, ["tag"]);
  const result = await promise;
  assert.deepEqual(events, ["tag", "await:then", "rows:then", "rows:0", "total:get", "Number", "output:get", "chars:number"]);
  assert.deepEqual(h.events, ["query:get", "query:call"]);
  assert.ok(result); assert.equal(result.truncated, true);
});

for (const mode of ["omitted", "undefined", "explicit"] as const) {
  test(`default-client resolution ${mode}`, async () => {
    const h = harness({ result: [] });
    const result = mode === "omitted" ? await h.fn(publicId, 5) : await h.fn(publicId, 5, mode === "undefined" ? undefined : h.client);
    assert.equal(result, null);
    assert.deepEqual(h.events, mode === "explicit" ? ["query:get", "query:call"] : ["default:get", "query:get", "query:call"]);
    assert.equal(h.calls[0].receiver, h.client);
  });
}

test("explicit client bypasses a throwing default binding", async () => {
  const h = harness({ result: [], defaultClient() { assert.fail("default must remain inert"); } });
  assert.equal(await h.fn(publicId, 5, h.client), null);
});

test("default binding is resolved freshly for each call", async () => {
  let count = 0;
  const first = { $queryRaw() { return [{ output: "public-first", total: 1n }]; } };
  const second = { $queryRaw() { return [{ output: "public-second", total: 2n }]; } };
  const h = harness({ defaultClient() { return count++ === 0 ? first : second; } });
  assert.equal((await h.fn(publicId, 5))?.output, "public-first");
  assert.equal((await h.fn(publicId, 5))?.output, "public-second");
  assert.equal(count, 2);
});

test("fresh result identities and stable frozen per-site template identity", async () => {
  const h = harness({ result: [{ output: "public-identity", total: 4n }] });
  const first = await h.fn(publicId, 2, h.client);
  const second = await h.fn(publicId, 2, h.client);
  assert.notEqual(first, second);
  assert.equal(h.calls[0].strings, h.calls[1].strings);
  assert.equal(h.calls[0].strings.raw, h.calls[1].strings.raw);
  assert.ok(Object.isFrozen(h.calls[0].strings));
  assert.ok(Object.isFrozen(h.calls[0].strings.raw));
  const separate = harness({ result: [] });
  await separate.fn(publicId, 2, separate.client);
  assert.notEqual(h.calls[0].strings, separate.calls[0].strings);
});

test("query lookup and tag receiver remain fresh across invocations", async () => {
  const h = harness({ result: [] });
  await h.fn(publicId, 1, h.client); await h.fn(publicId, 2, h.client);
  assert.deepEqual(h.events, ["query:get", "query:call", "query:get", "query:call"]);
  assert.equal(h.calls.length, 2);
});

test("rows after index zero and unrelated row fields stay inert", async () => {
  const row = new Proxy({ output: "public-first-only", total: 4n }, { get(target, key, receiver) {
    assert.ok(key === "total" || key === "output"); return Reflect.get(target, key, receiver);
  } });
  const rows = new Proxy([row], { get(target, key, receiver) {
    if (key === "then") return undefined;
    assert.equal(key, "0"); return Reflect.get(target, key, receiver);
  } });
  const h = harness({ result: rows });
  assert.equal((await h.fn(publicId, 2, h.client))?.output, "public-first-only");
});

test("output is read once and captured before comparison side effects", async () => {
  let reads = 0;
  const row = { total: 9n, get output() { reads++; return `public-output-${reads}`; } };
  const chars = { valueOf() { assert.equal(reads, 1); return 2; } };
  const h = harness({ result: [row] });
  assert.equal((await h.fn(publicId, chars, h.client))?.output, "public-output-1");
  assert.equal(reads, 1);
});

const faultCases = ["default", "query-get", "query-call", "query-reject", "then-get", "then-reject", "index-get", "total-get", "Number", "output-get", "comparison"] as const;
for (const fault of faultCases) {
  test(`immediate ${fault} fault preserves identity and never retries`, async () => {
    const witness = new Error(`public-${fault}-fault`);
    let tags = 0;
    let outputs = 0;
    const row = Object.defineProperties({}, {
      total: { get() { if (fault === "total-get") throw witness; return 9n; } },
      output: { get() { outputs++; if (fault === "output-get") throw witness; return "public-error-metadata"; } },
    });
    const rows = new Proxy([row], { get(target, key, receiver) {
      if (key === "then") return undefined;
      if (key === "0" && fault === "index-get") throw witness;
      return Reflect.get(target, key, receiver);
    } });
    const h = harness({
      defaultClient() { if (fault === "default") throw witness; return h.client; },
      query() {
        tags++;
        if (fault === "query-call") throw witness;
        if (fault === "query-reject") return Promise.reject(witness);
        if (fault === "then-get") return Object.defineProperty({}, "then", { get() { throw witness; } });
        if (fault === "then-reject") return { then(_resolve: unknown, reject: (error: unknown) => void) { reject(witness); } };
        return rows;
      },
      number(value) { if (fault === "Number") throw witness; return Number(value); },
    });
    const client = fault === "query-get" ? Object.defineProperty({}, "$queryRaw", { get() { throw witness; } }) : h.client;
    const chars = fault === "comparison" ? { valueOf() { throw witness; } } : 5;
    await assert.rejects(fault === "default" ? h.fn(publicId, chars) : h.fn(publicId, chars, client), error => error === witness);
    assert.equal(tags, fault === "default" || fault === "query-get" ? 0 : 1);
    if (!["output-get", "comparison"].includes(fault)) assert.equal(outputs, 0);
  });
}

for (const rows of [null, undefined]) {
  test(`nullish query result ${String(rows)} rejects without a retry`, async () => {
    const h = harness({ result: rows });
    await assert.rejects(h.fn(publicId, 5, h.client), error => (error as Error).name === "TypeError");
    assert.equal(h.calls.length, 1);
  });
}

for (const client of [null, false, 0, "public-nonclient", {}]) {
  test(`invalid explicit client ${JSON.stringify(client)} never resolves the default`, async () => {
    const h = harness({ defaultClient() { assert.fail("explicit invalid client must bypass default"); } });
    await assert.rejects(h.fn(publicId, 5, client), error => (error as Error).name === "TypeError");
    assert.equal(h.calls.length, 0);
    assert.deepEqual(h.events, []);
  });
}

test("Symbol total conversion rejects before output access", async () => {
  let outputs = 0;
  const h = harness({ result: [{ total: Symbol("public-total"), get output() { outputs++; return "public-never-read"; } }] });
  await assert.rejects(h.fn(publicId, 5, h.client), error => (error as Error).name === "TypeError");
  assert.equal(outputs, 0); assert.equal(h.calls.length, 1);
});

test("thenable first resolution wins without a second query or second row read", async () => {
  let reads = 0;
  const rows = new Proxy([{ total: 3n, output: "public-once" }], { get(target, key, receiver) {
    if (key === "then") return undefined;
    reads++; assert.equal(key, "0"); return Reflect.get(target, key, receiver);
  } });
  const h = harness({ query() { return { then(resolve: (value: unknown) => void, reject: (error: unknown) => void) {
    resolve(rows); resolve(null); reject(new Error("public-ignored-late-rejection"));
  } }; } });
  assert.equal((await h.fn(publicId, 2, h.client))?.output, "public-once");
  assert.equal(reads, 1); assert.equal(h.calls.length, 1);
});
