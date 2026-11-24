import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import vm from "node:vm";
import type * as TypeScript from "typescript";

const compilerPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compilerPath, "Explicit compiler path required");
const ts = createRequire(import.meta.url)(compilerPath) as typeof TypeScript;
const source = readFileSync(new URL("../src/app/api/deploy/stream/route.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("route.ts", source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((node): node is TypeScript.FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === "GET" &&
  !!node.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(selected.length, 1);
const declaration = selected[0].getText(ast);
assert.equal(createHash("sha256").update(declaration).digest("hex"),
  "d9d395d91320616d1a65144b04e41a4428a1520cc6a66126d3ecaa4fbc7eb18b");
const emitted = ts.transpileModule(declaration.replace(/^export /, ""), {
  compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None },
}).outputText;

type Options = {
  signal: unknown; cursor: number;
  authorize: () => unknown; load: (cursor: number) => unknown;
};
type Reply = { kind: "json" | "response"; body: unknown; status?: number; headers?: unknown };
type Setup = {
  jobId: unknown; headerCursor: unknown; queryCursor: unknown; cookie: unknown;
  initial: unknown; current: unknown; job: unknown;
  valid: boolean; safe: boolean; fault: string;
  initialGate?: Promise<unknown>; currentGate?: Promise<unknown>; jobGate?: Promise<unknown>;
  streamValue: unknown; loadValue: unknown;
};
function harness(changes: Partial<Setup> = {}) {
  const settings: Setup = {
    jobId: "PUBLIC_JOB_ID", headerCursor: null, queryCursor: null, cookie: "PUBLIC_COOKIE",
    initial: { id: "PUBLIC_OPERATOR" }, current: true, job: { id: "PUBLIC_JOB_ID" },
    valid: true, safe: true, fault: "", streamValue: { publicStreamToken: true },
    loadValue: { publicRow: true }, ...changes,
  };
  const events: string[] = [];
  const queries: unknown[] = [];
  const rows: unknown[][] = [];
  const sentinel = new Error("PUBLIC_SYNTHETIC_FAULT");
  let options: Options | undefined;
  let conversions = 0;
  function mark(name: string) {
    events.push(name);
    if (settings.fault === name) throw sentinel;
  }
  class PublicNextResponse {
    static json(body: unknown, init: { status: number }): Reply {
      mark("json:" + init.status);
      return { kind: "json", body, status: init.status };
    }
  }
  class PublicResponse {
    kind = "response" as const;
    body: unknown;
    headers: unknown;
    constructor(body: unknown, init: { headers: unknown }) {
      mark("response:new"); this.body = body; this.headers = init.headers;
    }
  }
  const request = {
    get nextUrl() {
      mark("url");
      return { get searchParams() {
        mark("params");
        return { get(key: string) {
          mark("query:" + key);
          if (key === "jobId") return settings.jobId;
          assert.equal(key, "cursor"); return settings.queryCursor;
        } };
      } };
    },
    get headers() {
      mark("headers");
      return { get(key: string) {
        mark("header:" + key);
        if (key === "last-event-id") return settings.headerCursor;
        assert.equal(key, "cookie"); return settings.cookie;
      } };
    },
    get signal() { mark("signal"); return signal; },
  };
  const signal = Object.freeze({ publicSignalMetadata: true });
  const number = Object.assign((value: unknown) => {
    mark("number:" + (++conversions)); return Number(value);
  }, { isSafeInteger(value: unknown) {
    mark("safeInteger"); return settings.safe && Number.isSafeInteger(value);
  } });
  const current = (cookie: unknown) => {
    mark("auth:current"); assert.equal(cookie, settings.cookie);
    return settings.currentGate ?? settings.current;
  };
  const bindings = {
    requireOperator: () => { mark("auth:initial"); return settings.initialGate ?? settings.initial; },
    NextResponse: PublicNextResponse,
    jobIdValid: (value: unknown) => { mark("jobId:valid"); assert.equal(value, settings.jobId); return settings.valid; },
    isOperatorFromHeaders: current,
    prisma: { job: { findUnique: (query: unknown) => {
      mark("job:findUnique"); queries.push(query); return settings.jobGate ?? settings.job;
    } } },
    get Response() { mark("Response:get"); return PublicResponse; },
    get createJobStream() {
      mark("streamBinding:get");
      return (value: Options) => { mark("stream:create"); options = value; return settings.streamValue; };
    },
    readJobSlice: (id: unknown, cursor: number) => {
      mark("slice:load"); rows.push([id, cursor]); return settings.loadValue;
    },
    Number: number,
  };
  const context = vm.createContext(bindings);
  const GET = new vm.Script(emitted + "\nGET", { filename: "selected-deploy-stream-GET.js" })
    .runInContext(context) as (request: unknown) => Promise<Reply>;
  return { settings, events, queries, rows, sentinel, request, signal, GET, PublicNextResponse,
    options: () => { assert.ok(options); return options; } };
}
const expected = [
  "auth:initial", "url", "params", "query:jobId", "headers", "header:last-event-id",
  "url", "params", "query:cursor", "jobId:valid", "number:1", "safeInteger",
  "headers", "header:cookie", "auth:current", "job:findUnique", "Response:get",
  "streamBinding:get", "signal", "number:2", "stream:create", "response:new",
];
function json(reply: Reply, status: number, error: string) {
  assert.equal(reply.kind, "json"); assert.equal(reply.status, status);
  assert.equal(JSON.stringify(reply.body), JSON.stringify({ error }));
}
const invalid = "Valid jobId and nonnegative cursor are required";
const unavailable = "Job stream unavailable";

test("exact selected GET has source-derived successful evaluation order", async () => {
  const h = harness(); const reply = await h.GET(h.request);
  assert.equal(reply.kind, "response"); assert.deepEqual(h.events, expected);
  assert.equal(reply.body, h.settings.streamValue);
  assert.equal(JSON.stringify(reply.headers), JSON.stringify({
    "Content-Type": "text/event-stream", "Cache-Control": "private, no-store", "X-Accel-Buffering": "no",
  }));
  assert.equal(JSON.stringify(h.queries), JSON.stringify([{ where: { id: "PUBLIC_JOB_ID" }, select: { id: true } }]));
  assert.equal(h.options().signal, h.signal); assert.equal(h.options().cursor, 0);
  assert.equal(h.events.includes("slice:load"), false);
});
test("initial response is returned by identity without request inspection", async () => {
  const h = harness(); const response = new h.PublicNextResponse(); h.settings.initial = response;
  assert.equal(await h.GET(h.request), response); assert.deepEqual(h.events, ["auth:initial"]);
});
test("initial authorization is awaited before request inspection", async () => {
  let release!: (value: unknown) => void;
  const h = harness({ initialGate: new Promise(resolve => { release = resolve; }) });
  const result = h.GET(h.request); await Promise.resolve();
  assert.deepEqual(h.events, ["auth:initial"]); release({ public: true });
  assert.equal((await result).kind, "response");
});
test("initial rejection preserves its exact error outside try", async () => {
  const failure = new Error("PUBLIC_INITIAL_REJECTION");
  const h = harness({ initialGate: Promise.reject(failure) });
  await assert.rejects(h.GET(h.request), error => error === failure);
  assert.deepEqual(h.events, ["auth:initial"]);
});
for (const fault of ["auth:initial", "url", "params", "query:jobId", "headers",
  "header:last-event-id", "query:cursor", "jobId:valid", "number:1", "safeInteger"]) {
  test("pre-try fault propagates unchanged at " + fault, async () => {
    const h = harness({ fault });
    await assert.rejects(h.GET(h.request), error => error === h.sentinel);
    assert.equal(h.events.includes("header:cookie"), false);
    assert.equal(h.events.includes("job:findUnique"), false);
  });
}
for (const headerCursor of ["0", "12", "0004", "999999999999999"]) {
  test("nonnull header cursor wins without reading query: " + headerCursor, async () => {
    const h = harness({ headerCursor, queryCursor: "999" });
    assert.equal((await h.GET(h.request)).kind, "response");
    assert.equal(h.options().cursor, Number(headerCursor));
    assert.equal(h.events.includes("query:cursor"), false);
  });
}
for (const headerCursor of [null, undefined]) {
  test("nullish header falls through to query: " + String(headerCursor), async () => {
    const h = harness({ headerCursor, queryCursor: "27" });
    assert.equal((await h.GET(h.request)).kind, "response");
    assert.equal(h.options().cursor, 27); assert.ok(h.events.includes("query:cursor"));
  });
}
for (const queryCursor of [null, undefined]) {
  test("nullish header and query default to zero: " + String(queryCursor), async () => {
    const h = harness({ headerCursor: undefined, queryCursor });
    assert.equal((await h.GET(h.request)).kind, "response"); assert.equal(h.options().cursor, 0);
  });
}
for (const cursor of ["", "-1", "+1", " 1", "1 ", "1.0", "1e3", "１２", "1\n", "1234567890123456"]) {
  test("malformed cursor refuses before number/auth/row access: " + JSON.stringify(cursor), async () => {
    const h = harness({ headerCursor: cursor });
    json(await h.GET(h.request), 400, invalid);
    assert.equal(h.events.includes("query:cursor"), false);
    assert.equal(h.events.includes("number:1"), false);
    assert.equal(h.events.includes("header:cookie"), false);
  });
}
test("invalid job still reads selected cursor before validator refusal", async () => {
  const h = harness({ valid: false, queryCursor: "12" });
  json(await h.GET(h.request), 400, invalid);
  assert.deepEqual(h.events, expected.slice(0, 10).concat("json:400"));
});
test("invalid job shortcircuits cursor coercion", async () => {
  const h = harness({ valid: false, headerCursor: { toString() { throw new Error("unreached"); } } });
  json(await h.GET(h.request), 400, invalid); assert.equal(h.events.includes("number:1"), false);
});
test("regex coercion error remains outside try", async () => {
  const fault = new Error("PUBLIC_REGEX_COERCION");
  const h = harness({ headerCursor: { toString() { throw fault; } } });
  await assert.rejects(h.GET(h.request), error => error === fault);
  assert.equal(h.events.includes("number:1"), false);
});
test("synthetic integer predicate refusal takes fixed400 branch", async () => {
  const h = harness({ safe: false }); json(await h.GET(h.request), 400, invalid);
  assert.equal(h.events.includes("header:cookie"), false);
});
test("400 response factory error propagates outside try", async () => {
  const h = harness({ valid: false, fault: "json:400" });
  await assert.rejects(h.GET(h.request), error => error === h.sentinel);
});
for (const value of [false, null, undefined, 0, ""]) {
  test("fresh authorization falsy result refuses without row access: " + String(value), async () => {
    const h = harness({ current: value }); json(await h.GET(h.request), 403, "Engine administration required");
    assert.equal(h.events.includes("job:findUnique"), false);
  });
}
test("fresh authorization await fences all row access", async () => {
  let release!: (value: unknown) => void;
  const h = harness({ currentGate: new Promise(resolve => { release = resolve; }) });
  const result = h.GET(h.request); await Promise.resolve(); await Promise.resolve();
  assert.equal(h.events.at(-1), "auth:current"); assert.equal(h.queries.length, 0);
  release(false); json(await result, 403, "Engine administration required");
});
for (const fault of ["header:cookie", "auth:current", "job:findUnique", "Response:get",
  "streamBinding:get", "signal", "number:2", "stream:create", "response:new"]) {
  test("try-stage fault becomes fixed503 at " + fault, async () => {
    const h = harness({ fault }); json(await h.GET(h.request), 503, unavailable);
    assert.equal(h.events.at(-1), "json:503");
  });
}
test("fresh authorization rejection becomes fixed503", async () => {
  const failure = new Error("PUBLIC_CURRENT_REJECTION");
  const h = harness({ currentGate: Promise.resolve().then(() => { throw failure; }) });
  json(await h.GET(h.request), 503, unavailable); assert.equal(h.queries.length, 0);
});
test("row rejection becomes fixed503", async () => {
  const failure = new Error("PUBLIC_ROW_REJECTION");
  const h = harness({ jobGate: Promise.resolve().then(() => { throw failure; }) });
  json(await h.GET(h.request), 503, unavailable); assert.equal(h.events.includes("stream:create"), false);
});
test("row await fences stream construction", async () => {
  let release!: (value: unknown) => void;
  const h = harness({ jobGate: new Promise(resolve => { release = resolve; }) });
  const result = h.GET(h.request); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  assert.equal(h.events.at(-1), "job:findUnique");
  release({ id: "PUBLIC_JOB_ID" }); assert.equal((await result).kind, "response");
});
for (const job of [null, undefined, false, 0, ""]) {
  test("falsy row becomes fixed404: " + String(job), async () => {
    const h = harness({ job }); json(await h.GET(h.request), 404, "Job not found");
    assert.equal(h.events.includes("Response:get"), false);
  });
}
test("truthy row is checked only for existence", async () => {
  const job = { get id(): never { throw new Error("row id must remain unread"); } };
  const h = harness({ job }); assert.equal((await h.GET(h.request)).kind, "response");
});
for (const status of [403, 404]) {
  test("inner JSON factory failure is caught and replaced: " + status, async () => {
    const h = harness({ ...(status === 403 ? { current: false } : { job: null }), fault: "json:" + status });
    json(await h.GET(h.request), 503, unavailable);
    assert.equal(h.events.at(-1), "json:503");
  });
}
test("catch JSON factory failure propagates unchanged", async () => {
  const h = harness({ current: false, fault: "json:503" });
  // Trigger catch via a response factory throwing while keeping the catch factory fault distinct.
  Object.defineProperty(h.settings, "current", { get() { throw h.sentinel; } });
  await assert.rejects(h.GET(h.request), error => error === h.sentinel);
  assert.equal(h.events.at(-1), "json:503");
});
test("authorize callback is lazy, fresh and captures cookie metadata", async () => {
  const h = harness(); await h.GET(h.request);
  assert.equal(h.events.filter(x => x === "auth:current").length, 1);
  assert.equal(h.options().authorize(), true); h.settings.current = false;
  assert.equal(h.options().authorize(), false); h.settings.current = true;
  assert.equal(h.options().authorize(), true);
  assert.equal(h.events.filter(x => x === "auth:current").length, 4);
});
test("authorize callback failure after return propagates rather than creating response", async () => {
  const h = harness(); await h.GET(h.request); h.settings.fault = "auth:current";
  assert.throws(() => h.options().authorize(), error => error === h.sentinel);
  assert.equal(h.events.includes("json:503"), false);
});
test("load callback is lazy, forwards captured ID and fresh cursor", async () => {
  const h = harness(); await h.GET(h.request);
  assert.deepEqual(h.rows, []); assert.equal(h.options().load(7), h.settings.loadValue);
  assert.equal(h.options().load(23), h.settings.loadValue);
  assert.deepEqual(h.rows, [["PUBLIC_JOB_ID", 7], ["PUBLIC_JOB_ID", 23]]);
});
test("load callback error after return propagates unchanged", async () => {
  const h = harness(); await h.GET(h.request); h.settings.fault = "slice:load";
  assert.throws(() => h.options().load(7), error => error === h.sentinel);
  assert.equal(h.events.includes("json:503"), false);
});
test("each GET rechecks both immediate authorization bindings and job existence", async () => {
  const h = harness(); await h.GET(h.request); await h.GET(h.request);
  assert.equal(h.events.filter(x => x === "auth:initial").length, 2);
  assert.equal(h.events.filter(x => x === "auth:current").length, 2);
  assert.equal(h.queries.length, 2);
});
test("stream token is forwarded without reading it", async () => {
  const token = { get privateOutput(): never { throw new Error("no output inspection"); } };
  const h = harness({ streamValue: token });
  assert.equal((await h.GET(h.request)).body, token);
});
