import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual page with scoped React/router/HTTP models. This checks
// client presentation and submission intent, not DOM or server authentication.
type Element = { type: unknown; props: Record<string, unknown> };
type Reply = { ok: boolean; body?: unknown; parseFailure?: boolean; networkFailure?: boolean; holdBody?: boolean };
function fixture(reply: Reply, hold = false) {
  const states: unknown[] = [], routes: string[] = [];
  const requests: { url: string; init: unknown }[] = [];
  let cursor = 0, jsonReads = 0, prevented = 0;
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let releaseBody!: () => void, bodyEntered!: () => void;
  const pendingBody = new Promise<void>(resolve => { releaseBody = resolve; });
  let bodyStarted = new Promise<void>(resolve => { bodyEntered = resolve; });
  const jsx = (type: unknown, props: Element["props"]) => ({ type, props });
  const modules: Record<string, unknown> = {
    react: { useState: (initial: unknown) => {
      const index = cursor++;
      if (!(index in states)) states[index] = initial;
      return [states[index], (value: unknown) => { states[index] = value; }];
    } },
    "react/jsx-runtime": { jsx, jsxs: jsx },
    "next/navigation": { useRouter: () => ({ push: (route: string) => routes.push(route) }) },
    "next/link": { __esModule: true, default: "Link" },
    "lucide-react": new Proxy({}, { get: (_target, name) => name }),
  };
  const filename = "src/app/auth/login/page.tsx";
  const output = ts.transpileModule(readFileSync(resolve(filename), "utf8"), {
    fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const component = { exports: {} as { default: () => unknown } };
  runInNewContext(output, { module: component, exports: component.exports,
    require: (name: string) => { assert(name in modules, name); return modules[name]; },
    fetch: async (url: string, init: unknown) => {
      assert.equal(url, "/api/auth/login");
      requests.push({ url, init: JSON.parse(JSON.stringify(init)) });
      if (hold) await pending;
      if (reply.networkFailure) throw new Error("Synthetic transport failure");
      return { ok: reply.ok, json: async () => {
        jsonReads++;
        bodyEntered();
        if (reply.holdBody) await pendingBody;
        if (reply.parseFailure) throw new Error("Synthetic JSON failure");
        return reply.body;
      } };
    },
  });
  const render = () => { cursor = 0; return component.exports.default(); };
  const walk = (value: unknown): Element[] => Array.isArray(value) ? value.flatMap(walk)
    : value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
  const text = (value: unknown): string => {
    if (Array.isArray(value)) return value.map(text).join(" ");
    if (value && typeof value === "object") {
      assert("props" in value, "An object cannot be rendered as error text");
      return text((value as Element).props.children);
    }
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
  };
  const elements = () => walk(render());
  const fill = (id: string, value: string) => {
    const input = elements().find(element => element.type === "input" && element.props.id === id); assert(input);
    (input.props.onChange as (event: unknown) => void)({ target: { value } });
  };
  const submit = async () => {
    const form = elements().find(element => element.type === "form"); assert(form);
    await (form.props.onSubmit as (event: unknown) => Promise<void>)({ preventDefault: () => { prevented++; } });
  };
  return { elements, fill, submit, release, releaseBody, get bodyStarted() { return bodyStarted; }, requests, routes, descendants: walk, text: () => text(render()),
    jsonReads: () => jsonReads, prevented: () => prevented,
    replyWith: (next: Reply) => { reply = next; bodyStarted = new Promise<void>(resolve => { bodyEntered = resolve; }); } };
}
function ready(reply: Reply, hold = false) {
  const f = fixture(reply, hold);
  f.fill("username", "synthetic-user"); f.fill("password", "synthetic-password");
  return f;
}
function assertRetainedForm(f: ReturnType<typeof fixture>) {
  assert(f.elements().some(element => element.type === "form"));
  const inputs = f.elements().filter(element => element.type === "input");
  assert.deepEqual(inputs.map(input => [input.props.id, input.props.value, input.props.required, input.props.autoComplete]), [
    ["username", "synthetic-user", true, "username"], ["password", "synthetic-password", true, "current-password"],
  ]);
  assert(!f.elements().some(element => element.type === "button" && element.props.disabled === true));
  assert.equal(f.prevented(), f.requests.length);
  assertPendingStatus(f, false);
}

function assertPendingStatus(f: ReturnType<typeof fixture>, pending: boolean) {
  const elements = f.elements();
  const statuses = elements.filter(element => element.props.role === "status");
  assert.equal(statuses.length, 1, "A status container exists before, during and after submission");
  assert.equal(statuses[0].props.children, pending ? "Signing in…" : "");
  assert.match(String(statuses[0].props.className), /\bsr-only\b/);
  assert.equal(statuses[0].props.tabIndex, undefined, "Pending feedback must not introduce a focus target");
  const form = elements.find(element => element.type === "form"); assert(form);
  assert.equal(form.props["aria-busy"], pending, "Form busy state follows the existing loading state");
  assert(!f.descendants(form).some(element => element.props.role === "status"), "Status stays outside the busy subtree");
  const button = elements.find(element => element.type === "button" && element.props.type === "submit"); assert(button);
  assert.equal(button.props.disabled, pending);
  const spinners = elements.filter(element => element.type === "Loader2");
  assert.equal(spinners.length, pending ? 1 : 0);
  if (pending) assert.equal(spinners[0].props["aria-hidden"], "true", "The spinner is decorative beside the pending status");
}

function assertErrorAnnouncement(f: ReturnType<typeof fixture>, message: string) {
  const alerts = f.elements().filter(element => element.props.role === "alert");
  assert.equal(alerts.length, message ? 1 : 0, "Only current nonempty feedback is an alert");
  if (message) {
    assert.equal(alerts[0].props.children, message);
    assert.equal(alerts[0].props.tabIndex, undefined, "Feedback must not introduce a focus target");
  }
}

for (const [label, reply] of [
  ["unreadable JSON", { parseFailure: true }],
  ["null body", { body: null }],
  ["array body", { body: [] }],
  ["string body", { body: "Synthetic proxy failure" }],
  ["boolean body", { body: false }],
  ["numeric body", { body: 42 }],
  ["missing error", { body: {} }],
  ["null error", { body: { error: null } }],
  ["object error", { body: { error: { message: "Synthetic proxy failure" } } }],
  ["array error", { body: { error: ["Synthetic proxy failure"] } }],
  ["boolean error", { body: { error: true } }],
  ["numeric error", { body: { error: 42 } }],
] as const) {
  test(`login HTTP refusal with ${label} shows the fixed fallback`, async () => {
    const f = ready({ ok: false, ...reply }); await f.submit();
    assert.match(f.text(), /Login failed/);
    assertErrorAnnouncement(f, "Login failed");
    assert.doesNotMatch(f.text(), /Network error|Synthetic proxy failure/);
    assert.deepEqual(f.routes, []); assert.equal(f.requests.length, 1); assert.equal(f.jsonReads(), 1);
    assertRetainedForm(f);
  });
}

test("login preserves normal JSON string feedback and intentional empty strings", async () => {
  for (const error of ["Invalid credentials", "Account unavailable", ""]) {
    const f = ready({ ok: false, body: { error } }); await f.submit();
    if (error) assert(f.text().includes(error));
    assertErrorAnnouncement(f, error);
    assert.doesNotMatch(f.text(), /Login failed|Network error/);
    assert.deepEqual(f.routes, []); assertRetainedForm(f);
  }
});

test("login transport failure retains network feedback and recovers loading", async () => {
  const f = ready({ ok: false, networkFailure: true }); await f.submit();
  assert.match(f.text(), /Network error — please try again/);
  assertErrorAnnouncement(f, "Network error — please try again");
  assert.doesNotMatch(f.text(), /Login failed/); assert.equal(f.jsonReads(), 0);
  assert.deepEqual(f.routes, []); assertRetainedForm(f);
});

test("login success posts entered credentials and navigates without decoding the body", async () => {
  const f = ready({ ok: true, parseFailure: true }); await f.submit();
  assert.deepEqual(f.requests, [{ url: "/api/auth/login", init: {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "synthetic-user", password: "synthetic-password" }),
  } }]);
  assert.deepEqual(f.routes, ["/"]); assert.equal(f.jsonReads(), 0);
  assert.doesNotMatch(f.text(), /Login failed|Network error/); assertRetainedForm(f);
  assertErrorAnnouncement(f, "");
});

test("login disables a pending submit and clears prior feedback on an explicit retry", async () => {
  const f = ready({ ok: false, body: { error: "Invalid credentials" } }, true);
  assertErrorAnnouncement(f, "");
  const pending = f.submit();
  assertPendingStatus(f, true);
  assert(f.elements().some(element => element.type === "button" && element.props.disabled === true));
  assert.deepEqual(f.routes, []); f.release(); await pending;
  assert.match(f.text(), /Invalid credentials/); assertRetainedForm(f);
  assertErrorAnnouncement(f, "Invalid credentials");
  f.replyWith({ ok: true }); await f.submit();
  assert.doesNotMatch(f.text(), /Invalid credentials|Login failed|Network error/);
  assert.deepEqual(f.routes, ["/"]); assert.equal(f.requests.length, 2); assertRetainedForm(f);
  assertErrorAnnouncement(f, "");
});

test("login starts with an empty status and does not submit or navigate without intent", () => {
  const f = fixture({ ok: true });
  assertPendingStatus(f, false); assertErrorAnnouncement(f, "");
  assert.equal(f.requests.length, 0); assert.equal(f.jsonReads(), 0); assert.equal(f.prevented(), 0);
  assert.deepEqual(f.routes, []);
});

for (const [label, reply, expected] of [
  ["string error", { body: { error: "Invalid credentials" } }, "Invalid credentials"],
  ["unreadable JSON", { parseFailure: true }, "Login failed"],
  ["nonstring error", { body: { error: { message: "Synthetic proxy failure" } } }, "Login failed"],
  ["empty string", { body: { error: "" } }, ""],
] as const) {
  test(`login remains pending while an unsuccessful ${label} body is held`, async () => {
    const f = ready({ ok: false, holdBody: true, ...reply });
    const pending = f.submit(); await f.bodyStarted;
    assertPendingStatus(f, true); assertErrorAnnouncement(f, "");
    assert.equal(f.requests.length, 1); assert.equal(f.jsonReads(), 1); assert.deepEqual(f.routes, []);
    f.releaseBody(); await pending;
    assertErrorAnnouncement(f, expected); assertRetainedForm(f);
    assert.equal(f.requests.length, 1); assert.deepEqual(f.routes, []);
    assert.doesNotMatch(f.text(), /Signing in|Network error|Synthetic proxy failure/);
  });
}

test("login clears prior alert on explicit retry while the next unsuccessful body is held", async () => {
  const f = ready({ ok: false, body: { error: "Invalid credentials" } });
  await f.submit(); assertErrorAnnouncement(f, "Invalid credentials"); assertRetainedForm(f);
  f.replyWith({ ok: false, holdBody: true, parseFailure: true });
  const pending = f.submit(); await f.bodyStarted;
  assert.equal(f.jsonReads(), 2); assertPendingStatus(f, true); assertErrorAnnouncement(f, "");
  assert.doesNotMatch(f.text(), /Invalid credentials|Login failed|Network error/);
  f.releaseBody(); await pending;
  assertErrorAnnouncement(f, "Login failed"); assertRetainedForm(f);
  assert.equal(f.requests.length, 2); assert.deepEqual(f.routes, []);
});

for (const [label, reply] of [
  ["success", { ok: true, parseFailure: true }],
  ["transport failure", { ok: false, networkFailure: true }],
] as const) {
  test(`login pending request settles on ${label} without reading a body`, async () => {
    const f = ready(reply, true); const pending = f.submit();
    assertPendingStatus(f, true); assert.equal(f.jsonReads(), 0); assert.deepEqual(f.routes, []);
    f.release(); await pending; assertRetainedForm(f);
    assert.equal(f.requests.length, 1); assert.equal(f.jsonReads(), 0);
    assert.deepEqual(f.routes, reply.ok ? ["/"] : []);
    assertErrorAnnouncement(f, reply.ok ? "" : "Network error — please try again");
  });
}
