import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct supported PUBLIC selected-declaration controls; historical70 remain frozen.
// Real module/imports/initializers/auth/validator/DB/jobs/output/streams/timers stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/app/api/deploy/stream/route.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), '3158c5613d75e2f95ab4b15651a7effe7c8eb8cdd2f6aaa9a28fbc5faecfc099');
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'e9516a0897eb848bc9700e7492a01f23b3297d999aee4829b757b3bdc7690d90');
const ast = ts.createSourceFile('selected.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'GET');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.equal(node.parameters.length, 1);
assert.equal(node.parameters[0].getText(ast), 'request: NextRequest');
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function GET(request: NextRequest) {\n  const auth = await requireOperator();\n  if (auth instanceof NextResponse) return auth;\n  const jobId = request.nextUrl.searchParams.get(\"jobId\");\n  const rawCursor = request.headers.get(\"last-event-id\") ?? request.nextUrl.searchParams.get(\"cursor\") ?? \"0\";\n  if (!jobIdValid(jobId) || !/^\\d{1,15}$/.test(rawCursor) || !Number.isSafeInteger(Number(rawCursor)))\n    return NextResponse.json({ error: \"Valid jobId and nonnegative cursor are required\" }, { status: 400 });\n  try {\n    const cookie = request.headers.get(\"cookie\");\n    if (!await isOperatorFromHeaders(cookie)) return NextResponse.json({ error: \"Engine administration required\" }, { status: 403 });\n    const job = await prisma.job.findUnique({ where: { id: jobId }, select: { id: true } });\n    if (!job) return NextResponse.json({ error: \"Job not found\" }, { status: 404 });\n    return new Response(createJobStream({ signal: request.signal, cursor: Number(rawCursor),\n      authorize: () => isOperatorFromHeaders(cookie), load: cursor => readJobSlice(jobId, cursor) }), {\n      headers: { \"Content-Type\": \"text/event-stream\", \"Cache-Control\": \"private, no-store\", \"X-Accel-Buffering\": \"no\" },\n    });\n  } catch { return NextResponse.json({ error: \"Job stream unavailable\" }, { status: 503 }); }\n}");
assert.equal(digest(declaration), 'ada55d63e99d803ce4b06d497a87e83a26b0fd7979335c4435c841275083e5e2');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), 'd9d395d91320616d1a65144b04e41a4428a1520cc6a66126d3ecaa4fbc7eb18b');
const compiled = ts.transpileModule(declaration.replace(/^export /, ''), { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const emitted = compiled.outputText;
assert.ok(!emitted.includes('import(') && !emitted.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
function harness(changes = {}) {
    const settings = {
        jobId: "PUBLIC_JOB_ID", headerCursor: null, queryCursor: null, cookie: "PUBLIC_COOKIE",
        initial: { id: "PUBLIC_OPERATOR" }, current: true, job: { id: "PUBLIC_JOB_ID" },
        valid: true, safe: true, fault: "", streamValue: { publicStreamToken: true },
        loadValue: { publicRow: true }, ...changes,
    };
    const events = [];
    const queries = [];
    const rows = [];
    const sentinel = new Error("PUBLIC_SYNTHETIC_FAULT");
    let options;
    let conversions = 0;
    function mark(name) {
        events.push(name);
        if (settings.fault === name)
            throw sentinel;
    }
    class PublicNextResponse {
        static json(body, init) {
            mark("json:" + init.status);
            return { kind: "json", body, status: init.status };
        }
    }
    class PublicResponse {
        kind = "response";
        body;
        headers;
        constructor(body, init) {
            mark("response:new");
            this.body = body;
            this.headers = init.headers;
        }
    }
    const request = {
        get nextUrl() {
            mark("url");
            return { get searchParams() {
                    mark("params");
                    return { get(key) {
                            mark("query:" + key);
                            if (key === "jobId")
                                return settings.jobId;
                            assert.equal(key, "cursor");
                            return settings.queryCursor;
                        } };
                } };
        },
        get headers() {
            mark("headers");
            return { get(key) {
                    mark("header:" + key);
                    if (key === "last-event-id")
                        return settings.headerCursor;
                    assert.equal(key, "cookie");
                    return settings.cookie;
                } };
        },
        get signal() { mark("signal"); return signal; },
    };
    const signal = Object.freeze({ publicSignalMetadata: true });
    const number = Object.assign((value) => {
        mark("number:" + (++conversions));
        return Number(value);
    }, { isSafeInteger(value) {
            mark("safeInteger");
            return settings.safe && Number.isSafeInteger(value);
        } });
    const current = (cookie) => {
        mark("auth:current");
        assert.equal(cookie, settings.cookie);
        return settings.currentGate ?? settings.current;
    };
    const bindings = {
        requireOperator: () => { mark("auth:initial"); return settings.initialGate ?? settings.initial; },
        NextResponse: PublicNextResponse,
        jobIdValid: (value) => { mark("jobId:valid"); assert.equal(value, settings.jobId); return settings.valid; },
        isOperatorFromHeaders: current,
        prisma: { job: { findUnique: (query) => {
                    mark("job:findUnique");
                    queries.push(query);
                    return settings.jobGate ?? settings.job;
                } } },
        get Response() { mark("Response:get"); return PublicResponse; },
        get createJobStream() {
            mark("streamBinding:get");
            return (value) => { mark("stream:create"); options = value; return settings.streamValue; };
        },
        readJobSlice: (id, cursor) => {
            mark("slice:load");
            rows.push([id, cursor]);
            return settings.loadValue;
        },
        Number: number,
    };
    const context = vm.createContext(bindings);
    const GET = new vm.Script(emitted + "\nGET", { filename: "selected-deploy-stream-GET.js" })
        .runInContext(context);
    return { settings, events, queries, rows, sentinel, request, signal, GET, PublicNextResponse,
        options: () => { assert.ok(options); return options; } };
}
const expected = [
    "auth:initial", "url", "params", "query:jobId", "headers", "header:last-event-id",
    "url", "params", "query:cursor", "jobId:valid", "number:1", "safeInteger",
    "headers", "header:cookie", "auth:current", "job:findUnique", "Response:get",
    "streamBinding:get", "signal", "number:2", "stream:create", "response:new",
];
function json(reply, status, error) {
    assert.equal(reply.kind, "json");
    assert.equal(reply.status, status);
    assert.equal(JSON.stringify(reply.body), JSON.stringify({ error }));
}
const invalid = "Valid jobId and nonnegative cursor are required";
const unavailable = "Job stream unavailable";
control("exact selected GET has source-derived successful evaluation order", async () => {
    const h = harness();
    const reply = await h.GET(h.request);
    assert.equal(reply.kind, "response");
    assert.deepEqual(h.events, expected);
    assert.equal(reply.body, h.settings.streamValue);
    assert.equal(JSON.stringify(reply.headers), JSON.stringify({
        "Content-Type": "text/event-stream", "Cache-Control": "private, no-store", "X-Accel-Buffering": "no",
    }));
    assert.equal(JSON.stringify(h.queries), JSON.stringify([{ where: { id: "PUBLIC_JOB_ID" }, select: { id: true } }]));
    assert.equal(h.options().signal, h.signal);
    assert.equal(h.options().cursor, 0);
    assert.equal(h.events.includes("slice:load"), false);
});
control("initial response is returned by identity without request inspection", async () => {
    const h = harness();
    const response = new h.PublicNextResponse();
    h.settings.initial = response;
    assert.equal(await h.GET(h.request), response);
    assert.deepEqual(h.events, ["auth:initial"]);
});
control("initial authorization is awaited before request inspection", async () => {
    let release;
    const h = harness({ initialGate: new Promise(resolve => { release = resolve; }) });
    const result = h.GET(h.request);
    await Promise.resolve();
    assert.deepEqual(h.events, ["auth:initial"]);
    release({ public: true });
    assert.equal((await result).kind, "response");
});
control("initial rejection preserves its exact error outside try", async () => {
    const failure = new Error("PUBLIC_INITIAL_REJECTION");
    const h = harness({ initialGate: Promise.reject(failure) });
    await assert.rejects(h.GET(h.request), error => error === failure);
    assert.deepEqual(h.events, ["auth:initial"]);
});
for (const fault of ["auth:initial", "url", "params", "query:jobId", "headers",
    "header:last-event-id", "query:cursor", "jobId:valid", "number:1", "safeInteger"]) {
    control("pre-try fault propagates unchanged at " + fault, async () => {
        const h = harness({ fault });
        await assert.rejects(h.GET(h.request), error => error === h.sentinel);
        assert.equal(h.events.includes("header:cookie"), false);
        assert.equal(h.events.includes("job:findUnique"), false);
    });
}
for (const headerCursor of ["0", "12", "0004", "999999999999999"]) {
    control("nonnull header cursor wins without reading query: " + headerCursor, async () => {
        const h = harness({ headerCursor, queryCursor: "999" });
        assert.equal((await h.GET(h.request)).kind, "response");
        assert.equal(h.options().cursor, Number(headerCursor));
        assert.equal(h.events.includes("query:cursor"), false);
    });
}
for (const headerCursor of [null, undefined]) {
    control("nullish header falls through to query: " + String(headerCursor), async () => {
        const h = harness({ headerCursor, queryCursor: "27" });
        assert.equal((await h.GET(h.request)).kind, "response");
        assert.equal(h.options().cursor, 27);
        assert.ok(h.events.includes("query:cursor"));
    });
}
for (const queryCursor of [null, undefined]) {
    control("nullish header and query default to zero: " + String(queryCursor), async () => {
        const h = harness({ headerCursor: undefined, queryCursor });
        assert.equal((await h.GET(h.request)).kind, "response");
        assert.equal(h.options().cursor, 0);
    });
}
for (const cursor of ["", "-1", "+1", " 1", "1 ", "1.0", "1e3", "１２", "1\n", "1234567890123456"]) {
    control("malformed cursor refuses before number/auth/row access: " + JSON.stringify(cursor), async () => {
        const h = harness({ headerCursor: cursor });
        json(await h.GET(h.request), 400, invalid);
        assert.equal(h.events.includes("query:cursor"), false);
        assert.equal(h.events.includes("number:1"), false);
        assert.equal(h.events.includes("header:cookie"), false);
    });
}
control("invalid job still reads selected cursor before validator refusal", async () => {
    const h = harness({ valid: false, queryCursor: "12" });
    json(await h.GET(h.request), 400, invalid);
    assert.deepEqual(h.events, expected.slice(0, 10).concat("json:400"));
});
control("invalid job shortcircuits cursor coercion", async () => {
    const h = harness({ valid: false, headerCursor: { toString() { throw new Error("unreached"); } } });
    json(await h.GET(h.request), 400, invalid);
    assert.equal(h.events.includes("number:1"), false);
});
control("regex coercion error remains outside try", async () => {
    const fault = new Error("PUBLIC_REGEX_COERCION");
    const h = harness({ headerCursor: { toString() { throw fault; } } });
    await assert.rejects(h.GET(h.request), error => error === fault);
    assert.equal(h.events.includes("number:1"), false);
});
control("synthetic integer predicate refusal takes fixed400 branch", async () => {
    const h = harness({ safe: false });
    json(await h.GET(h.request), 400, invalid);
    assert.equal(h.events.includes("header:cookie"), false);
});
control("400 response factory error propagates outside try", async () => {
    const h = harness({ valid: false, fault: "json:400" });
    await assert.rejects(h.GET(h.request), error => error === h.sentinel);
});
for (const value of [false, null, undefined, 0, ""]) {
    control("fresh authorization falsy result refuses without row access: " + String(value), async () => {
        const h = harness({ current: value });
        json(await h.GET(h.request), 403, "Engine administration required");
        assert.equal(h.events.includes("job:findUnique"), false);
    });
}
control("fresh authorization await fences all row access", async () => {
    let release;
    const h = harness({ currentGate: new Promise(resolve => { release = resolve; }) });
    const result = h.GET(h.request);
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(h.events.at(-1), "auth:current");
    assert.equal(h.queries.length, 0);
    release(false);
    json(await result, 403, "Engine administration required");
});
for (const fault of ["header:cookie", "auth:current", "job:findUnique", "Response:get",
    "streamBinding:get", "signal", "number:2", "stream:create", "response:new"]) {
    control("try-stage fault becomes fixed503 at " + fault, async () => {
        const h = harness({ fault });
        json(await h.GET(h.request), 503, unavailable);
        assert.equal(h.events.at(-1), "json:503");
    });
}
control("fresh authorization rejection becomes fixed503", async () => {
    const failure = new Error("PUBLIC_CURRENT_REJECTION");
    const h = harness({ currentGate: Promise.resolve().then(() => { throw failure; }) });
    json(await h.GET(h.request), 503, unavailable);
    assert.equal(h.queries.length, 0);
});
control("row rejection becomes fixed503", async () => {
    const failure = new Error("PUBLIC_ROW_REJECTION");
    const h = harness({ jobGate: Promise.resolve().then(() => { throw failure; }) });
    json(await h.GET(h.request), 503, unavailable);
    assert.equal(h.events.includes("stream:create"), false);
});
control("row await fences stream construction", async () => {
    let release;
    const h = harness({ jobGate: new Promise(resolve => { release = resolve; }) });
    const result = h.GET(h.request);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(h.events.at(-1), "job:findUnique");
    release({ id: "PUBLIC_JOB_ID" });
    assert.equal((await result).kind, "response");
});
for (const job of [null, undefined, false, 0, ""]) {
    control("falsy row becomes fixed404: " + String(job), async () => {
        const h = harness({ job });
        json(await h.GET(h.request), 404, "Job not found");
        assert.equal(h.events.includes("Response:get"), false);
    });
}
control("truthy row is checked only for existence", async () => {
    const job = { get id() { throw new Error("row id must remain unread"); } };
    const h = harness({ job });
    assert.equal((await h.GET(h.request)).kind, "response");
});
for (const status of [403, 404]) {
    control("inner JSON factory failure is caught and replaced: " + status, async () => {
        const h = harness({ ...(status === 403 ? { current: false } : { job: null }), fault: "json:" + status });
        json(await h.GET(h.request), 503, unavailable);
        assert.equal(h.events.at(-1), "json:503");
    });
}
control("catch JSON factory failure propagates unchanged", async () => {
    const h = harness({ current: false, fault: "json:503" });
    // Trigger catch via a response factory throwing while keeping the catch factory fault distinct.
    Object.defineProperty(h.settings, "current", { get() { throw h.sentinel; } });
    await assert.rejects(h.GET(h.request), error => error === h.sentinel);
    assert.equal(h.events.at(-1), "json:503");
});
control("authorize callback is lazy, fresh and captures cookie metadata", async () => {
    const h = harness();
    await h.GET(h.request);
    assert.equal(h.events.filter(x => x === "auth:current").length, 1);
    assert.equal(h.options().authorize(), true);
    h.settings.current = false;
    assert.equal(h.options().authorize(), false);
    h.settings.current = true;
    assert.equal(h.options().authorize(), true);
    assert.equal(h.events.filter(x => x === "auth:current").length, 4);
});
control("authorize callback failure after return propagates rather than creating response", async () => {
    const h = harness();
    await h.GET(h.request);
    h.settings.fault = "auth:current";
    assert.throws(() => h.options().authorize(), error => error === h.sentinel);
    assert.equal(h.events.includes("json:503"), false);
});
control("load callback is lazy, forwards captured ID and fresh cursor", async () => {
    const h = harness();
    await h.GET(h.request);
    assert.deepEqual(h.rows, []);
    assert.equal(h.options().load(7), h.settings.loadValue);
    assert.equal(h.options().load(23), h.settings.loadValue);
    assert.deepEqual(h.rows, [["PUBLIC_JOB_ID", 7], ["PUBLIC_JOB_ID", 23]]);
});
control("load callback error after return propagates unchanged", async () => {
    const h = harness();
    await h.GET(h.request);
    h.settings.fault = "slice:load";
    assert.throws(() => h.options().load(7), error => error === h.sentinel);
    assert.equal(h.events.includes("json:503"), false);
});
control("each GET rechecks both immediate authorization bindings and job existence", async () => {
    const h = harness();
    await h.GET(h.request);
    await h.GET(h.request);
    assert.equal(h.events.filter(x => x === "auth:initial").length, 2);
    assert.equal(h.events.filter(x => x === "auth:current").length, 2);
    assert.equal(h.queries.length, 2);
});
control("stream token is forwarded without reading it", async () => {
    const token = { get privateOutput() { throw new Error("no output inspection"); } };
    const h = harness({ streamValue: token });
    assert.equal((await h.GET(h.request)).body, token);
});
assert.equal(count, 70);
