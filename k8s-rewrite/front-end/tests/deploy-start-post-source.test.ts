import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

// Exact declaration only. Application imports, neighbours and initializers never run.
const source = readFileSync(new URL("../src/app/api/deploy/start/route.ts", import.meta.url), "utf8");
const start = source.indexOf("export async function POST(request: NextRequest)");
const finish = source.indexOf("export async function GET", start);
assert.ok(start >= 0 && finish > start);
const declaration = source.slice(start, finish).trim();
const compilerPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compilerPath, "explicit source compiler required");
const compiler = createRequire(import.meta.url)(compilerPath) as {
  transpileModule(input: string, options: object): { outputText: string };
};
const javascript = compiler.transpileModule(declaration.replace(/^export /, ""), {
  compilerOptions: { target: 9, module: 0 },
}).outputText;
type PublicRequest = { json(): unknown };
type Handler = (request: PublicRequest) => Promise<unknown>;
const names = ["requireOperator", "NextResponse", "runtimeCapabilities", "ansibleSelection", "syncVarsToYAML", "syncNodesFromVars", "syncInventoryToFile", "prisma", "PREPARATION_OUTPUT", "Date", "AbortController", "activeJobs", "runAnsible", "AnsibleSelectionError"];
const factory = new Function(...names, javascript + "\nreturn POST;") as (...args: unknown[]) => Handler;

class PublicSelectionError extends Error {}
type Settings = {
  fault?: string; occurrence?: number; failure?: unknown; auth?: unknown;
  capability?: unknown; body?: unknown; selectResult?: unknown;
  returns?: Record<string, unknown>; responseResult?: (value: ResponseMetadata) => unknown;
};
type ResponseMetadata = { body: unknown; options: unknown; args: unknown[] };
function setup(settings: Settings = {}) {
  const trace: string[] = [];
  const calls: { label: string; receiver: unknown; args: unknown[] }[] = [];
  const counts = new Map<string, number>();
  const failure = Object.hasOwn(settings, "failure") ? settings.failure : new Error("PUBLIC synthetic failure");
  function hit(label: string) {
    trace.push(label);
    const count = (counts.get(label) ?? 0) + 1;
    counts.set(label, count);
    if (settings.fault === label && count === (settings.occurrence ?? 1)) throw failure;
  }
  function call(label: string, receiver: unknown, args: unknown[], fallback: unknown) {
    hit(label); calls.push({ label, receiver, args });
    return settings.returns && Object.hasOwn(settings.returns, label) ? settings.returns[label] : fallback;
  }
  class SyntheticResponse {
    static [Symbol.hasInstance](value: unknown) {
      hit("auth.instanceof");
      return typeof value === "object" && value !== null && Object.getPrototypeOf(value) === SyntheticResponse.prototype;
    }
    static get json() {
      hit("response.member");
      return function (this: unknown, ...args: unknown[]) {
        call("response.call", this, args, undefined);
        const result: ResponseMetadata = { body: args[0], options: args[1], args };
        return settings.responseResult ? settings.responseResult(result) : result;
      };
    }
  }
  const selectionError = new Proxy(PublicSelectionError, {
    get(target, key, receiver) {
      if (key === Symbol.hasInstance) return (value: unknown) => {
        hit("selectionError.instanceof");
        return typeof value === "object" && value !== null && Object.getPrototypeOf(value) === PublicSelectionError.prototype;
      };
      return Reflect.get(target, key, receiver);
    },
  });
  const selected = {
    get playbook() { hit("selected.playbook"); return "public-selected.yml"; },
    get roles() { hit("selected.roles"); return ["PUBLIC-role"]; },
  };
  const job = { get id() { hit("job.id"); return "PUBLIC-job-id"; } };
  const jobReceiver = {
    get create() {
      hit("prisma.create.member");
      return function (this: unknown, ...args: unknown[]) { return call("prisma.create.call", this, args, job); };
    },
  };
  const prisma = { get job() { hit("prisma.job"); return jobReceiver; } };
  let controller: object | undefined;
  class SyntheticController {
    constructor(...args: unknown[]) { call("controller.construct", undefined, args, undefined); controller = this; }
    get signal() { hit("controller.signal"); return "PUBLIC-signal"; }
  }
  const registrations: unknown[][] = [];
  const activeJobs = {
    get set() {
      hit("activeJobs.set.member");
      return function (this: unknown, ...args: unknown[]) {
        call("activeJobs.set.call", this, args, undefined); registrations.push(args);
      };
    },
  };
  const request = {
    get json() {
      hit("request.json.member");
      return function (this: unknown, ...args: unknown[]) {
        return call("request.json.call", this, args, Object.hasOwn(settings, "body") ? settings.body : {});
      };
    },
  };
  const auth = Object.hasOwn(settings, "auth") ? settings.auth : { id: "PUBLIC-operator" };
  const capabilities = { get provisioning() { hit("capability.provisioning"); return Object.hasOwn(settings, "capability") ? settings.capability : true; } };
  const values: unknown[] = [
    function (this: unknown, ...args: unknown[]) { return call("auth.call", this, args, auth); },
    SyntheticResponse,
    function (this: unknown, ...args: unknown[]) { return call("capability.call", this, args, capabilities); },
    function (this: unknown, ...args: unknown[]) { return call("selection.call", this, args, Object.hasOwn(settings, "selectResult") ? settings.selectResult : selected); },
    function (this: unknown, ...args: unknown[]) { return call("vars.call", this, args, undefined); },
    function (this: unknown, ...args: unknown[]) { return call("nodes.call", this, args, undefined); },
    function (this: unknown, ...args: unknown[]) { return call("inventory.call", this, args, undefined); },
    prisma, "PUBLIC preparation metadata",
    class SyntheticDate { constructor(...args: unknown[]) { call("date.construct", undefined, args, undefined); } },
    SyntheticController, activeJobs,
    function (this: unknown, ...args: unknown[]) { return call("runner.call", this, args, undefined); },
    selectionError,
  ];
  const handler = factory(...values);
  const invoke = () => handler(request);
  return { trace, calls, counts, failure, request, selected, job, jobReceiver, activeJobs, registrations, invoke, Response: SyntheticResponse, controller: () => controller };
}
function response(value: unknown): ResponseMetadata {
  assert.ok(typeof value === "object" && value !== null && "body" in value && "args" in value);
  return value as ResponseMetadata;
}
function callAt(h: ReturnType<typeof setup>, label: string) {
  const found = h.calls.find(x => x.label === label); assert.ok(found, label); return found;
}
const successOrder = ["auth.call", "auth.instanceof", "capability.call", "capability.provisioning", "request.json.member", "request.json.call", "selection.call", "selected.playbook", "vars.call", "nodes.call", "inventory.call", "prisma.job", "prisma.create.member", "date.construct", "prisma.create.call", "controller.construct", "activeJobs.set.member", "job.id", "activeJobs.set.call", "job.id", "selected.roles", "controller.signal", "runner.call", "response.member", "job.id", "response.call"];

test("exact POST source selection excludes imports, GET and neighbours", () => {
  assert.match(declaration, /^export async function POST\(request: NextRequest\)/);
  assert.doesNotMatch(declaration, /\bimport\s|export async function GET/);
  assert.equal(names.length, 14);
});
test("success observes exact source order, receivers and metadata arguments", async () => {
  const h = setup(); const result = response(await h.invoke());
  assert.deepEqual(h.trace, successOrder);
  assert.deepEqual(result.body, { success: true, jobId: "PUBLIC-job-id" }); assert.equal(result.args.length, 1);
  assert.equal(callAt(h, "request.json.call").receiver, h.request);
  assert.equal(callAt(h, "prisma.create.call").receiver, h.jobReceiver);
  assert.equal(callAt(h, "activeJobs.set.call").receiver, h.activeJobs);
  for (const label of ["auth.call", "capability.call", "request.json.call", "vars.call", "nodes.call", "inventory.call", "date.construct", "controller.construct"]) assert.deepEqual(callAt(h, label).args, []);
  assert.deepEqual(callAt(h, "selection.call").args, ["site.yml", []]);
  const data = (callAt(h, "prisma.create.call").args[0] as { data: Record<string, unknown> }).data;
  assert.deepEqual(Object.keys(data), ["playbook", "status", "output", "startedAt"]);
  assert.equal(data.playbook, "public-selected.yml"); assert.equal(data.status, "running"); assert.equal(data.output, "PUBLIC preparation metadata");
  assert.deepEqual(h.registrations, [["PUBLIC-job-id", h.controller()]]);
  assert.deepEqual(callAt(h, "runner.call").args, ["PUBLIC-job-id", "public-selected.yml", ["PUBLIC-role"], "PUBLIC-signal"]);
});
test("auth denial returns exact identity before capability or request", async () => {
  const first = setup(); const denial = new first.Response();
  // The handler must use the same synthetic response constructor as its denial.
  const h = setup({ returns: { "auth.call": denial } });
  h.Response[Symbol.hasInstance] = value => value === denial;
  assert.equal(await h.invoke(), denial); assert.deepEqual(h.trace, ["auth.call"]);
});
for (const label of ["auth.call", "auth.instanceof", "capability.call", "capability.provisioning"]) {
  test("outside try fault propagates unchanged: " + label, async () => {
    const h = setup({ fault: label }); await assert.rejects(h.invoke(), x => x === h.failure);
    assert.equal(h.counts.has("request.json.member"), false); assert.equal(h.counts.has("selectionError.instanceof"), false);
  });
}
test("outside try asynchronous authorization rejection propagates unchanged", async () => {
  const failure = new Error("PUBLIC authorization rejection");
  const h = setup({ returns: { "auth.call": { then(_resolve: unknown, reject: (x: unknown) => void) { reject(failure); } } } });
  await assert.rejects(h.invoke(), x => x === failure); assert.deepEqual(h.trace, ["auth.call"]);
});
for (const capability of [false, 0, null, undefined, ""]) {
  test("disabled capability refuses before request: " + String(capability), async () => {
    const h = setup({ capability }); const r = response(await h.invoke());
    assert.deepEqual(h.trace, ["auth.call", "auth.instanceof", "capability.call", "capability.provisioning", "response.member", "response.call"]);
    assert.deepEqual(r.options, { status: 501 }); assert.deepEqual(r.body, { error: "Run bootstrap/provisioning from the independent operator environment" });
  });
}
for (const capability of [true, 1, "PUBLIC-enabled", {}]) {
  test("capability source truthiness proceeds: " + String(capability), async () => {
    const h = setup({ capability }); assert.deepEqual(response(await h.invoke()).body, { success: true, jobId: "PUBLIC-job-id" });
  });
}
for (const body of [undefined, null, {}]) {
  test("nullish request fields default without fabricated selection: " + String(body), async () => {
    const h = setup({ body }); await h.invoke(); assert.deepEqual(callAt(h, "selection.call").args, ["site.yml", []]);
  });
}
test("nonnull falsy selection fields preserve identity and source getter order", async () => {
  const observed: string[] = [];
  const body = { get playbook() { observed.push("playbook"); return 0; }, get roles() { observed.push("roles"); return false; } };
  const h = setup({ body }); await h.invoke(); assert.deepEqual(observed, ["playbook", "roles"]); assert.deepEqual(callAt(h, "selection.call").args, [0, false]);
});
test("default roles array is fresh for each invocation", async () => {
  const h = setup(); await h.invoke(); await h.invoke();
  const selections = h.calls.filter(x => x.label === "selection.call"); assert.notEqual(selections[0].args[1], selections[1].args[1]);
});
for (const field of ["playbook", "roles"]) {
  test("body field fault prevents selection and preparation: " + field, async () => {
    const body = Object.defineProperty({}, field, { get() { throw new Error("PUBLIC field failure"); } });
    const h = setup({ body }); assert.deepEqual(response(await h.invoke()).options, { status: 500 });
    assert.equal(h.counts.has("selection.call"), false); assert.equal(h.counts.has("vars.call"), false);
  });
}
const caughtFaults = ["request.json.member", "request.json.call", "selection.call", "selected.playbook", "vars.call", "nodes.call", "inventory.call", "prisma.job", "prisma.create.member", "date.construct", "prisma.create.call", "controller.construct", "activeJobs.set.member", "job.id", "activeJobs.set.call", "selected.roles", "controller.signal", "runner.call", "response.member", "response.call"];
for (const label of caughtFaults) {
  test("caught synchronous fault is fixed500 and stops later phases: " + label, async () => {
    const h = setup({ fault: label }); const r = response(await h.invoke());
    assert.deepEqual(r.body, { error: "Provisioning preparation failed" }); assert.deepEqual(r.options, { status: 500 });
    const at = successOrder.indexOf(label); const next = h.trace.indexOf("selectionError.instanceof");
    assert.deepEqual(h.trace.slice(0, next), successOrder.slice(0, at + 1));
    assert.deepEqual(h.trace.slice(next), ["selectionError.instanceof", "response.member", "response.call"]);
  });
}
for (const label of ["request.json.call", "vars.call", "nodes.call", "inventory.call", "prisma.create.call"]) {
  test("awaited synthetic rejection becomes fixed500: " + label, async () => {
    const failure = new Error("PUBLIC rejected immediate binding");
    const h = setup({ returns: { [label]: { then(_resolve: unknown, reject: (x: unknown) => void) { reject(failure); } } } });
    const r = response(await h.invoke()); assert.deepEqual(r.body, { error: "Provisioning preparation failed" }); assert.deepEqual(r.options, { status: 500 }); assert.equal(h.counts.has("runner.call"), false);
  });
}
test("selection-class failure returns public400 and skips preparation", async () => {
  const h = setup({ fault: "selection.call", failure: new PublicSelectionError("PUBLIC invalid selection") });
  const r = response(await h.invoke()); assert.deepEqual(r.body, { error: "PUBLIC invalid selection" }); assert.deepEqual(r.options, { status: 400 }); assert.equal(h.counts.has("vars.call"), false);
});
test("request parsing and each preparation await fence the next phase", async () => {
  for (const [label, next] of [["request.json.call", "selection.call"], ["vars.call", "nodes.call"], ["nodes.call", "inventory.call"], ["inventory.call", "prisma.job"], ["prisma.create.call", "controller.construct"]]) {
    let release: ((value: unknown) => void) | undefined;
    const pending = new Promise(resolve => { release = resolve; });
    const h = setup({ returns: { [label]: pending } }); const result = h.invoke();
    for (let i = 0; i < 8; i++) await Promise.resolve();
    assert.equal(h.counts.has(label), true); assert.equal(h.counts.has(next), false); assert.ok(release);
    release(label === "request.json.call" ? {} : label === "prisma.create.call" ? h.job : undefined);
    assert.deepEqual(response(await result).body, { success: true, jobId: "PUBLIC-job-id" });
  }
});
for (const occurrence of [2, 3]) {
  test("later job id fault retains only prior inert registration: " + occurrence, async () => {
    const h = setup({ fault: "job.id", occurrence }); const r = response(await h.invoke());
    assert.deepEqual(r.options, { status: 500 }); assert.equal(h.registrations.length, 1); assert.equal(h.counts.has("runner.call"), occurrence === 3);
  });
}
test("void runner result is discarded without then inspection or awaiting", async () => {
  let inspected = false;
  const h = setup({ returns: { "runner.call": { get then() { inspected = true; throw new Error("PUBLIC must remain inert"); } } } });
  assert.deepEqual(response(await h.invoke()).body, { success: true, jobId: "PUBLIC-job-id" }); assert.equal(inspected, false);
});
test("successful return adopts synthetic response Promise", async () => {
  const sentinel = { public: "adopted response" };
  const h = setup({ responseResult: () => Promise.resolve(sentinel) }); assert.equal(await h.invoke(), sentinel);
});
test("successful returned Promise rejection bypasses synchronous catch", async () => {
  const failure = new Error("PUBLIC asynchronous response refusal");
  const h = setup({ responseResult: () => ({ then(_resolve: unknown, reject: (x: unknown) => void) { reject(failure); } }) });
  await assert.rejects(h.invoke(), x => x === failure); assert.equal(h.counts.has("selectionError.instanceof"), false); assert.equal(h.counts.get("response.call"), 1);
});
test("disabled branch response rejection remains outside catch", async () => {
  const failure = new Error("PUBLIC disabled response refusal");
  const h = setup({ capability: false, responseResult: () => ({ then(_resolve: unknown, reject: (x: unknown) => void) { reject(failure); } }) });
  await assert.rejects(h.invoke(), x => x === failure); assert.equal(h.counts.has("selectionError.instanceof"), false);
});
test("catch classifier fault propagates unchanged", async () => {
  const failure = new Error("PUBLIC classifier failure");
  const h = setup({ returns: { "request.json.call": { then(_r: unknown, reject: (x: unknown) => void) { reject("PUBLIC rejected body"); } } }, fault: "selectionError.instanceof", failure });
  await assert.rejects(h.invoke(), x => x === failure); assert.equal(h.counts.has("response.member"), false);
});
test("selection error message getter failure propagates from catch", async () => {
  const failure = new Error("PUBLIC message failure"); const selected = new PublicSelectionError();
  Object.defineProperty(selected, "message", { get() { throw failure; } });
  const h = setup({ fault: "selection.call", failure: selected });
  await assert.rejects(h.invoke(), x => x === failure); assert.equal(h.counts.get("response.member"), 1); assert.equal(h.counts.has("response.call"), false);
});
test("catch response fault propagates without recursively catching", async () => {
  const failure = new Error("PUBLIC catch response failure");
  const h = setup({ returns: { "request.json.call": { then(_r: unknown, reject: (x: unknown) => void) { reject("PUBLIC parse refusal"); } } }, fault: "response.call", failure });
  await assert.rejects(h.invoke(), x => x === failure); assert.equal(h.counts.get("selectionError.instanceof"), 1); assert.equal(h.counts.get("response.call"), 1);
});
test("catch response Promise rejection is adopted unchanged", async () => {
  const failure = new Error("PUBLIC catch asynchronous failure");
  const h = setup({ fault: "selection.call", failure: new PublicSelectionError("PUBLIC selection"), responseResult: () => ({ then(_r: unknown, reject: (x: unknown) => void) { reject(failure); } }) });
  await assert.rejects(h.invoke(), x => x === failure); assert.equal(h.counts.get("response.call"), 1);
});
