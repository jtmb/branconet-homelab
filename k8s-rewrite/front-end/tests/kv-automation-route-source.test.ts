import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

// PUBLIC SOURCE only: compile the exact function declaration without its imports.
// Authentication, headers, body/schema, registry, engine and responses are stubs.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL("../src/app/api/kv/automation/route.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("route.ts", source, ts.ScriptTarget.Latest, true);
const post = ast.statements.find((s: { name?: { getText(): string } }) => ts.isFunctionDeclaration(s) && s.name?.getText() === "POST");
assert.ok(post);
const js = ts.transpileModule(post.getText().replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Call = (this: unknown, ...args: unknown[]) => unknown;
type Handler = (request: unknown) => Promise<unknown>;
const names = ["kvRegistry", "kvEngine", "kvBody", "automationRequest", "runAutomation", "secretResponse", "kvErrorResponse"];
type Scope = { handler: Handler; replace: (name: string, value: unknown) => void };
function select(bindings: Record<string, unknown>): Scope {
  const setters = names.map(n => `case ${JSON.stringify(n)}: ${n} = value; break;`).join("\n");
  return new Function(...names, '"use strict";\n' + js + "\nreturn {handler:POST,replace(name,value){switch(name){" + setters + "default:throw Error('unknown binding')}}};")(...names.map(n => bindings[n])) as Scope;
}
function opaque(label: string, awaited = false): object {
  return new Proxy(Object.create(null), { get(_t, key) { if (awaited && key === "then") return undefined; throw Error(label + " read " + String(key)); }, ownKeys() { throw Error(label + " keys"); }, getPrototypeOf() { throw Error(label + " prototype"); } });
}
function deferred() {
  let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
const stages = ["registry", "authenticate-get", "headers-get", "header-method-get", "header-call", "authenticate-call", "engine", "body", "automation", "response"];
const early = stages.slice(0, 6);
const examples = [undefined, null, false, true, 0, -1, "", "public", Symbol("public"), {}, [], opaque("identity", true)];
type Options = { header?: unknown; actor?: unknown; input?: unknown; result?: unknown; response?: unknown; at?: (stage: string) => void; auth?: (actor: unknown) => unknown; body?: (input: unknown) => unknown; run?: (result: unknown) => unknown; respond?: (response: unknown) => unknown; error?: Call };
function rig(o: Options = {}) {
  const events: string[] = [], errors: unknown[] = [];
  const value = (key: "header" | "actor" | "input" | "result" | "response", awaited = true) => Object.hasOwn(o, key) ? o[key] : opaque(key, awaited);
  const header = value("header", false), actor = value("actor"), input = value("input"), result = value("result"), response = value("response");
  const engine = opaque("engine"), schema = opaque("schema"), errorResult = {};
  const hit = (s: string) => { events.push(s); o.at?.(s); };
  const headers = Object.defineProperty(Object.create(null), "get", { configurable: true, get() { hit("header-method-get"); return function (this: unknown, ...args: unknown[]) { hit("header-call"); assert.equal(this, headers); assert.deepEqual(args, ["authorization"]); return header; }; } });
  const request = new Proxy(Object.create(null), { get(_t, k) { assert.equal(k, "headers"); hit("headers-get"); return headers; } });
  const registry = Object.defineProperty(Object.create(null), "authenticateIdentity", { configurable: true, get() { hit("authenticate-get"); return function (this: unknown, ...args: unknown[]) { hit("authenticate-call"); assert.equal(this, registry); assert.equal(args.length, 1); assert.equal(args[0], header); return o.auth ? o.auth(actor) : actor; }; } });
  const bindings: Record<string, unknown> = {
    kvRegistry: function (this: unknown, ...args: unknown[]) { hit("registry"); assert.equal(this, undefined); assert.equal(args.length, 0); return registry; },
    kvEngine: function (this: unknown, ...args: unknown[]) { hit("engine"); assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], registry); return engine; },
    kvBody: function (this: unknown, ...args: unknown[]) { hit("body"); assert.equal(this, undefined); assert.equal(args.length, 2); assert.equal(args[0], request); assert.equal(args[1], schema); return o.body ? o.body(input) : input; },
    automationRequest: schema,
    runAutomation: function (this: unknown, ...args: unknown[]) { hit("automation"); assert.equal(this, undefined); assert.equal(args.length, 3); assert.equal(args[0], engine); assert.equal(args[1], actor); assert.equal(args[2], input); return o.run ? o.run(result) : result; },
    secretResponse: function (this: unknown, ...args: unknown[]) { hit("response"); assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], result); return o.respond ? o.respond(response) : response; },
    kvErrorResponse: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 1); errors.push(args[0]); return o.error ? o.error(...args) : errorResult; },
  };
  const scope = select(bindings);
  return { events, errors, header, actor, input, result, response, engine, schema, request, headers, registry, bindings, errorResult, scope, invoke: () => scope.handler(request) };
}
function adopted(kind: string, value: unknown, hold: ReturnType<typeof deferred>): unknown {
  return kind === "plain" ? value : kind === "resolved" ? Promise.resolve(value) : kind === "pending" ? hold.promise : { then(resolve: (v: unknown) => void) { resolve(value); } };
}

test("automation POST finite PUBLIC SOURCE controls", async t => {
  await t.test("exact imports runtime exported async function and try/catch source", () => {
    assert.equal(ast.statements.length, 5);
    assert.deepEqual(ast.statements.filter((s: unknown) => ts.isImportDeclaration(s)).map((s: { getText(): string }) => s.getText()), ['import { kvBody, kvEngine, kvErrorResponse, kvRegistry } from "@/lib/kv-http";', 'import { automationRequest, runAutomation } from "@/lib/kv-automation";', 'import { secretResponse } from "@/lib/secret-http";']);
    assert.equal(ast.statements[3].getText(), 'export const runtime = "nodejs";');
    assert.deepEqual(post.modifiers.map((m: { kind: number }) => m.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
    assert.deepEqual(post.parameters.map((p: { getText(): string }) => p.getText()), ["request: Request"]);
    assert.equal(post.body.statements.length, 1);
    const block = post.body.statements[0]; assert.ok(ts.isTryStatement(block));
    assert.deepEqual(block.tryBlock.statements.map((s: { getText(): string }) => s.getText()), ['const registry = kvRegistry(), actor = await registry.authenticateIdentity(request.headers.get("authorization"));', 'return secretResponse(await runAutomation(kvEngine(registry), actor, await kvBody(request, automationRequest)));']);
    assert.equal(block.catchClause.getText(), "catch (error) { return kvErrorResponse(error); }");
    select(Object.fromEntries(names.map(n => [n, () => { throw Error("selection executed dependency"); }])));
  });
  for (const field of ["header", "actor", "input", "result", "response"] as const) for (const [index, value] of examples.entries()) {
    await t.test("exact receivers arguments and opaque " + field + " " + index, async () => {
      const r = rig({ [field]: value }); const p = r.invoke(); assert.ok(p instanceof Promise);
      assert.deepEqual(r.events, early); assert.equal(await p, r.response); assert.deepEqual(r.events, stages); assert.deepEqual(r.errors, []);
    });
  }
  for (const field of ["auth", "body", "run", "respond"] as const) for (const kind of ["plain", "resolved", "pending", "thenable"]) {
    await t.test(field + " " + kind + " adoption and await fence", async () => {
      const hold = deferred(); const r = rig({ [field]: (v: unknown) => adopted(kind, v, hold) }); const p = r.invoke();
      if (kind === "pending") {
        for (let i = 0; i < 5; i++) await Promise.resolve();
        const stop = field === "auth" ? 6 : field === "body" ? 8 : field === "run" ? 9 : 10;
        assert.deepEqual(r.events, stages.slice(0, stop)); hold.resolve(field === "auth" ? r.actor : field === "body" ? r.input : field === "run" ? r.result : r.response);
      }
      assert.equal(await p, r.response); assert.deepEqual(r.events, stages); assert.deepEqual(r.errors, []);
    });
  }
  for (const field of ["auth", "body", "run"] as const) for (const kind of ["throw", "reject", "then-getter", "then-call"]) {
    await t.test(field + " awaited failure " + kind + " caught once", async () => {
      const failure = {}; const r = rig({ [field]: () => { if (kind === "throw") throw failure; if (kind === "reject") return Promise.reject(failure); if (kind === "then-getter") return Object.defineProperty({}, "then", { get() { throw failure; } }); return { then() { throw failure; } }; } });
      assert.equal(await r.invoke(), r.errorResult); assert.deepEqual(r.errors, [failure]);
      assert.deepEqual(r.events, stages.slice(0, field === "auth" ? 6 : field === "body" ? 8 : 9));
    });
  }
  for (const stage of stages) {
    await t.test("synchronous failure at " + stage + " catches exact identity and stops suffix", async () => {
      const failure = {}; const r = rig({ at: s => { if (s === stage) throw failure; } });
      assert.equal(await r.invoke(), r.errorResult); assert.deepEqual(r.errors, [failure]); assert.deepEqual(r.events, stages.slice(0, stages.indexOf(stage) + 1));
    });
  }
  for (const field of ["respond", "error"] as const) for (const kind of ["throw", "reject", "then-getter", "then-call"]) {
    await t.test(field + " returned failure " + kind + " distinguishes return from await", async () => {
      const failure = {}, trigger = {};
      const refuse = () => { if (kind === "throw") throw failure; if (kind === "reject") return Promise.reject(failure); if (kind === "then-getter") return Object.defineProperty({}, "then", { get() { throw failure; } }); return { then() { throw failure; } }; };
      const r = rig(field === "respond" ? { respond: refuse } : { at: s => { if (s === "registry") throw trigger; }, error: refuse });
      if (field === "respond" && kind === "throw") { assert.equal(await r.invoke(), r.errorResult); assert.deepEqual(r.errors, [failure]); }
      else { await assert.rejects(r.invoke(), x => x === failure); assert.deepEqual(r.errors, field === "error" ? [trigger] : []); }
    });
  }
  for (const name of ["kvRegistry", "kvEngine", "kvBody", "runAutomation", "secretResponse", "kvErrorResponse"]) for (const value of [undefined, null, 0, {}]) {
    await t.test("noncallable " + name + " preserves argument evaluation and refusal", async () => {
      const r = rig(name === "kvErrorResponse" ? { at: s => { if (s === "registry") throw Error("public trigger"); } } : {});
      r.scope.replace(name, value);
      if (name === "kvErrorResponse") { await assert.rejects(r.invoke(), TypeError); assert.deepEqual(r.events, ["registry"]); }
      else { assert.equal(await r.invoke(), r.errorResult); assert.equal(r.errors.length, 1); assert.ok(r.errors[0] instanceof TypeError);
        assert.deepEqual(r.events, name === "kvRegistry" ? [] : name === "kvEngine" ? early : name === "kvBody" ? stages.slice(0, 7) : name === "runAutomation" ? stages.slice(0, 8) : stages.slice(0, 9)); }
    });
  }
  for (const kind of ["inherited", "proxy", "missing", "null", "undefined", "primitive"]) {
    await t.test("authenticateIdentity " + kind + " property lookup and receiver", async () => {
      const r = rig(); const calls: unknown[][] = [];
      const method = function (this: unknown, ...args: unknown[]) { calls.push([this, ...args]); return r.actor; };
      const proto = { authenticateIdentity: method };
      const registry = kind === "inherited" ? Object.create(proto) : kind === "proxy" ? new Proxy({}, { get(_t, k) { assert.equal(k, "authenticateIdentity"); return method; } }) : kind === "null" ? null : kind === "undefined" ? undefined : kind === "primitive" ? 0 : {};
      r.scope.replace("kvRegistry", () => registry); r.scope.replace("kvEngine", (...args: unknown[]) => { assert.deepEqual(args, [registry]); return r.engine; });
      if (["inherited", "proxy"].includes(kind)) { assert.equal(await r.invoke(), r.response); assert.deepEqual(calls, [[registry, r.header]]); }
      else { assert.equal(await r.invoke(), r.errorResult); assert.ok(r.errors[0] instanceof TypeError); assert.deepEqual(r.events, kind === "null" || kind === "undefined" ? [] : ["headers-get", "header-method-get", "header-call"]); }
    });
  }
  for (const kind of ["inherited", "proxy", "missing", "null", "undefined", "primitive"]) {
    await t.test("headers.get " + kind + " exact receiver and refusal suffix", async () => {
      const r = rig(); const calls: unknown[][] = [];
      const method = function (this: unknown, ...args: unknown[]) { calls.push([this, ...args]); return r.header; };
      const headers = kind === "inherited" ? Object.create({ get: method }) : kind === "proxy" ? new Proxy({}, { get(_t, k) { assert.equal(k, "get"); return method; } }) : kind === "null" ? null : kind === "undefined" ? undefined : kind === "primitive" ? false : {};
      const request = { headers }; r.scope.replace("kvBody", (...args: unknown[]) => { assert.deepEqual(args, [request, r.schema]); return r.input; });
      if (["inherited", "proxy"].includes(kind)) { assert.equal(await r.scope.handler(request), r.response); assert.deepEqual(calls, [[headers, "authorization"]]); }
      else { assert.equal(await r.scope.handler(request), r.errorResult); assert.ok(r.errors[0] instanceof TypeError); assert.deepEqual(r.events, ["registry", "authenticate-get"]); }
    });
  }
  for (const request of [undefined, null]) {
    await t.test("nullish request " + String(request) + " catches after method capture", async () => {
      const r = rig(); assert.equal(await r.scope.handler(request), r.errorResult); assert.ok(r.errors[0] instanceof TypeError); assert.deepEqual(r.events, ["registry", "authenticate-get"]);
    });
  }
  for (const stage of ["engine", "body"]) {
    await t.test("runAutomation and secretResponse captured before " + stage, async () => {
      let r!: ReturnType<typeof rig>;
      r = rig({ at: s => { if (s === stage) { r.scope.replace("runAutomation", () => { throw Error("late run"); }); r.scope.replace("secretResponse", () => { throw Error("late response"); }); } } });
      assert.equal(await r.invoke(), r.response); assert.deepEqual(r.events, stages); assert.deepEqual(r.errors, []);
    });
  }
  await t.test("engine precedes fresh body and schema selection", async () => {
    let r!: ReturnType<typeof rig>; const schema = opaque("replacement schema");
    r = rig({ at: s => { if (s === "engine") { r.scope.replace("automationRequest", schema); r.scope.replace("kvBody", function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.deepEqual(args, [r.request, schema]); return r.input; }); } } });
    assert.equal(await r.invoke(), r.response); assert.deepEqual(r.events, stages.filter(s => s !== "body"));
  });
  await t.test("body pending retains original engine actor and captured callees", async () => {
    const hold = deferred(); const r = rig({ body: () => hold.promise }); const p = r.invoke();
    for (let i = 0; i < 5; i++) await Promise.resolve(); assert.deepEqual(r.events, stages.slice(0, 8));
    for (const n of ["kvRegistry", "kvEngine", "runAutomation", "secretResponse"]) r.scope.replace(n, () => { throw Error("late " + n); });
    hold.resolve(r.input); assert.equal(await p, r.response); assert.deepEqual(r.events, stages);
  });
  await t.test("fresh selection and repeated calls never reuse registry or actor", async () => {
    const a = rig(), b = rig(); assert.notEqual(a.scope.handler, b.scope.handler);
    assert.equal(await a.invoke(), a.response); assert.equal(await b.invoke(), b.response);
    assert.equal(await a.invoke(), a.response); assert.deepEqual(a.events, [...stages, ...stages]); assert.deepEqual(b.events, stages);
  });
  for (const trigger of ["interleave", ...stages]) {
    await t.test("same handler " + trigger + " reentrancy keeps call-local bindings", async () => {
      const events = [[], []] as string[][]; let count = 0, second: Promise<unknown> | undefined, handler!: Handler;
      const holds = [deferred(), deferred()];
      const hit = (i: number, stage: string) => { events[i].push(stage); if (i === 0 && trigger === stage) second = handler(ctx[1].request); };
      const ctx = [0, 1].map(i => {
        const actor = {}, input = {}, engine = {}, result = {}, response = {}, header = Symbol("header");
        const headers = Object.defineProperty({}, "get", { get() { hit(i, "header-method-get"); return function (this: unknown, ...args: unknown[]) { hit(i, "header-call"); assert.equal(this, headers); assert.deepEqual(args, ["authorization"]); return header; }; } });
        const request = Object.defineProperty({}, "headers", { get() { hit(i, "headers-get"); return headers; } });
        const registry = Object.defineProperty({}, "authenticateIdentity", { get() { hit(i, "authenticate-get"); return function (this: unknown, ...args: unknown[]) { hit(i, "authenticate-call"); assert.equal(this, registry); assert.deepEqual(args, [header]); return actor; }; } });
        return { actor, input, engine, result, response, request, registry };
      });
      const index = (key: "registry" | "request" | "actor" | "result", value: unknown) => { const i = ctx.findIndex(x => x[key] === value); assert.ok(i >= 0); return i; };
      handler = select({
        kvRegistry: () => { const i = count++; assert.ok(i < 2); hit(i, "registry"); return ctx[i].registry; },
        kvEngine: (...args: unknown[]) => { assert.equal(args.length, 1); const i = index("registry", args[0]); hit(i, "engine"); return ctx[i].engine; },
        automationRequest: {},
        kvBody: (...args: unknown[]) => { assert.equal(args.length, 2); const i = index("request", args[0]); hit(i, "body"); return trigger === "interleave" ? holds[i].promise : ctx[i].input; },
        runAutomation: (...args: unknown[]) => { assert.equal(args.length, 3); const i = index("actor", args[1]); assert.equal(args[0], ctx[i].engine); assert.equal(args[2], ctx[i].input); hit(i, "automation"); return ctx[i].result; },
        secretResponse: (...args: unknown[]) => { assert.equal(args.length, 1); const i = index("result", args[0]); hit(i, "response"); return ctx[i].response; },
        kvErrorResponse: (error: unknown) => { throw error; },
      }).handler;
      const first = handler(ctx[0].request);
      if (trigger === "interleave") {
        second = handler(ctx[1].request); for (let i = 0; i < 5; i++) await Promise.resolve();
        assert.deepEqual(events, [stages.slice(0, 8), stages.slice(0, 8)]);
        holds[1].resolve(ctx[1].input); assert.equal(await second, ctx[1].response); assert.deepEqual(events[0], stages.slice(0, 8)); holds[0].resolve(ctx[0].input);
      }
      assert.equal(await first, ctx[0].response); assert.ok(second); assert.equal(await second, ctx[1].response); assert.deepEqual(events, [stages, stages]);
    });
  }
});
