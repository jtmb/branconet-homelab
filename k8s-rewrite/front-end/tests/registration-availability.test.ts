import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Runs the actual page with scoped React/router/HTTP models. This is client
// presentation and submission intent, not DOM or server authorization proof.
type Element = { type: unknown; props: Record<string, unknown> };
type Reply = { ok: boolean; status?: number; body?: unknown; networkFailure?: boolean; parseFailure?: boolean };
function fixture(reply: Reply, hold = false) {
  const states: unknown[] = [], effects: (() => void)[] = [], routes: string[] = [];
  const requests: { url: string; init?: { method?: string; body?: string } }[] = [];
  let cursor = 0, mounted = false, jsonReads = 0, submitJsonReads = 0, holdSubmit = false, holdSubmitBody = false;
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let bodyEntered!: () => void;
  let bodyStarted = new Promise<void>(resolve => { bodyEntered = resolve; });
  let submitReply: Reply = { ok: true, status: 201 };
  const jsx = (type: unknown, props: Element["props"]) => ({ type, props });
  const modules: Record<string, unknown> = {
    react: {
      useState: (initial: unknown) => {
        const index = cursor++;
        if (!(index in states)) states[index] = initial;
        return [states[index], (value: unknown) => { states[index] = value; }];
      },
      useEffect: (effect: () => void) => { if (!mounted) effects.push(effect); },
    },
    "react/jsx-runtime": { jsx, jsxs: jsx },
    "next/navigation": { useRouter: () => ({ push: (route: string) => routes.push(route) }) },
    "next/link": { __esModule: true, default: "Link" },
    "lucide-react": new Proxy({}, { get: (_target, name) => name }),
  };
  const filename = "src/app/auth/register/page.tsx";
  const output = ts.transpileModule(readFileSync(resolve(filename), "utf8"), {
    fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const component = { exports: {} as { default: () => unknown } };
  runInNewContext(output, { module: component, exports: component.exports,
    require: (name: string) => { assert(name in modules, name); return modules[name]; },
    fetch: async (url: string, init?: { method?: string; body?: string }) => {
      requests.push({ url, init: init ? JSON.parse(JSON.stringify(init)) : undefined });
      assert(["/api/auth/session", "/api/auth/register"].includes(url), url);
      if (url === "/api/auth/session" && hold) await pending;
      if (url === "/api/auth/register" && holdSubmit) await pending;
      const current = url === "/api/auth/session" ? reply : submitReply;
      if (current.networkFailure) throw new Error("Synthetic network failure");
      return { ok: current.ok, status: current.status, json: async () => {
        if (url === "/api/auth/session") jsonReads++;
        if (url === "/api/auth/register") {
          submitJsonReads++;
          bodyEntered();
          if (holdSubmitBody) await pending;
        }
        if (current.parseFailure) throw new Error("Synthetic JSON failure");
        return current.body;
      } };
    },
  });
  const walk = (value: unknown): Element[] => Array.isArray(value) ? value.flatMap(walk)
    : value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
  const text = (value: unknown): string => Array.isArray(value) ? value.map(text).join(" ")
    : value && typeof value === "object" && "props" in value ? text((value as Element).props.children)
    : typeof value === "string" ? value : "";
  const render = () => { cursor = 0; return component.exports.default(); };
  const first = render(); mounted = true; effects.forEach(effect => effect());
  const elements = () => walk(render());
  const settle = async () => { await new Promise<void>(resolve => setImmediate(resolve)); };
  const fill = (id: string, value: string) => {
    const input = elements().find(element => element.type === "input" && element.props.id === id);
    assert(input, `Missing ${id} input`);
    (input.props.onChange as (event: unknown) => void)({ target: { value } });
  };
  const submit = async () => {
    const form = elements().find(element => element.type === "form"); assert(form, "Missing form");
    await (form.props.onSubmit as (event: unknown) => Promise<void>)({ preventDefault: () => {} });
  };
  return { first, render, elements, text: () => text(render()), firstElements: walk(first), settle, release,
    requests, routes, fill, submit, descendants: walk, get bodyStarted() { return bodyStarted; },
    jsonReads: () => jsonReads, submitJsonReads: () => submitJsonReads, textOf: text,
    replyToSubmit: (next: Reply) => { submitReply = next; bodyStarted = new Promise<void>(resolve => { bodyEntered = resolve; }); }, holdSubmit: () => { holdSubmit = true; },
    holdSubmitBody: () => { holdSubmitBody = true; } };
}
function assertPendingStatus(f: ReturnType<typeof fixture>, pending: boolean) {
  const elements = f.elements();
  const statuses = elements.filter(element => element.props.role === "status");
  assert.equal(statuses.length, 1, "An open form has a status container before, during and after submission");
  assert.equal(statuses[0].props.children, pending ? "Creating account…" : "");
  assert.match(String(statuses[0].props.className), /\bsr-only\b/);
  assert.equal(statuses[0].props.tabIndex, undefined, "Pending feedback must not introduce a focus target");
  const form = elements.find(element => element.type === "form"); assert(form);
  assert.equal(form.props["aria-busy"], pending, "Form busy state follows the existing loading state");
  assert(!f.descendants(form).some(element => element.props.role === "status"), "Status stays outside the busy subtree");
  const button = elements.find(element => element.type === "button" && element.props.type === "submit"); assert(button);
  assert.equal(button.props.disabled, pending);
  assert.equal(f.textOf(button).trim(), "Create account", "The visible action name stays unchanged");
  const spinners = elements.filter(element => element.type === "Loader2");
  assert.equal(spinners.length, pending ? 1 : 0);
  if (pending) assert.equal(spinners[0].props["aria-hidden"], "true", "The submit spinner is decorative beside the status");
}
function assertRetainedForm(f: ReturnType<typeof fixture>) {
  assertPendingStatus(f, false);
  const inputs = f.elements().filter(element => element.type === "input");
  assert.deepEqual(inputs.map(input => [input.props.id, input.props.value, input.props.required, input.props.autoComplete,
    input.props.minLength, input.props.maxLength, input.props.pattern]), [
    ["username", "synthetic-user", true, "username", 3, 30, "^[a-zA-Z0-9_-]+$"],
    ["password", "abcdefgh", true, "new-password", 8, undefined, undefined],
    ["confirm", "abcdefgh", true, "new-password", 8, undefined, undefined],
  ]);
  assert.deepEqual(f.elements().filter(element => element.type === "Link").map(element => element.props.href),
    ["/welcome", "/auth/login"]);
}
function assertLockAnnouncement(f: ReturnType<typeof fixture>) {
  const alerts = f.elements().filter(element => element.props.role === "alert");
  assert.equal(alerts.length, 1, "The lock notice replaces submission feedback with one alert");
  assert.equal(f.textOf(alerts[0]), "Registration Locked Account creation has been disabled by the administrator.");
  assert.equal(alerts[0].props.tabIndex, undefined, "The lock notice must not introduce a focus target");
  assert(!f.elements().some(element => element.type === "form"));
  assert.equal(f.elements().filter(element => element.props.role === "status").length, 0, "Lock replaces pending submission status");
  const link = f.elements().find(element => element.type === "Link"); assert(link);
  assert.equal(link.props.href, "/auth/login");
  assert.equal(link.props.children, "Go to sign in");
  assert(!f.textOf(alerts[0]).includes("Go to sign in"), "Navigation stays outside the announcement");
  assert.deepEqual(f.routes, []);
}
function assertErrorAnnouncement(f: ReturnType<typeof fixture>, message: string) {
  const alerts = f.elements().filter(element => element.props.role === "alert");
  assert.equal(alerts.length, message ? 1 : 0, "Only current nonempty feedback is an alert");
  if (message) {
    assert.equal(alerts[0].props.children, message);
    assert.equal(alerts[0].props.tabIndex, undefined, "Feedback must not introduce a focus target");
  }
}
function assertUnknown(f: ReturnType<typeof fixture>) {
  assert(!f.elements().some(element => element.type === "form"), "Unknown availability must not offer account creation");
  assert.match(f.text(), /Unable to check registration availability/i);
  assert.doesNotMatch(f.text(), /disabled by the administrator/i);
  assert(f.elements().some(element => element.type === "Link" && element.props.href === "/auth/login"));
  assert.deepEqual(f.requests.map(request => request.url), ["/api/auth/session"]);
  assert.deepEqual(f.routes, []);
}

test("pending registration availability does not present an open form or administrator lock", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: true } }, true);
  assert(!f.firstElements.some(element => element.type === "form"));
  assert.doesNotMatch(f.text(), /disabled by the administrator/i);
  f.release(); await f.settle();
  assert(f.elements().some(element => element.type === "form"));
});

test("explicit successful registration availability preserves open and administrator-locked states", async () => {
  for (const registrationOpen of [true, false]) {
    const f = fixture({ ok: true, body: { registrationOpen } }); await f.settle();
    assert.equal(f.elements().some(element => element.type === "form"), registrationOpen);
    if (!registrationOpen) assertLockAnnouncement(f);
    assert.doesNotMatch(f.text(), /Unable to check registration availability/i);
  }
});

test("open registration describes account setup without promising a role from session hints", async () => {
  for (const hint of [{ hasUsers: true }, { hasUsers: false }, {}]) {
    const f = fixture({ ok: true, body: { registrationOpen: true, ...hint } }); await f.settle();
    assertErrorAnnouncement(f, "");
    assertPendingStatus(f, false);
    assert(f.elements().some(element => element.type === "form"));
    assert.match(f.text(), /Set up your Botrus account/);
    assert.doesNotMatch(f.text(), /administrator account|write access|readonly/i);
    f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
    await f.submit();
    assert.equal(f.requests[1]?.url, "/api/auth/register");
    assert.deepEqual(JSON.parse(f.requests[1]?.init?.body ?? "null"), { username: "synthetic-user", password: "abcdefgh" });
    assert.deepEqual(f.routes, ["/"]);
    assertErrorAnnouncement(f, "");
  }
});

test("failed HTTP availability is unknown even when its body claims open or closed", async () => {
  for (const body of [{ error: "Internal server error" }, { registrationOpen: true }, { registrationOpen: false }]) {
    const f = fixture({ ok: false, status: 500, body }); await f.settle();
    assertUnknown(f); assert.equal(f.jsonReads(), 0, "Do not interpret unsuccessful HTTP bodies");
  }
});

test("malformed availability cannot masquerade as a known registration decision", async () => {
  for (const body of [null, [], false, 0, "session", {}, { registrationOpen: null },
    { registrationOpen: "false" }, { registrationOpen: 1 }, { registrationOpen: 0 }]) {
    const f = fixture({ ok: true, body }); await f.settle(); assertUnknown(f);
  }
});

test("network and JSON availability failures have honest unknown presentation", async () => {
  for (const reply of [{ ok: true, networkFailure: true }, { ok: true, parseFailure: true }]) {
    const f = fixture(reply); await f.settle(); assertUnknown(f);
  }
});

test("confirmed-open registration retains validation and successful POST/navigation", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
  f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "different");
  await f.submit(); assert.match(f.text(), /Passwords do not match/); assert.equal(f.requests.length, 1);
  assertErrorAnnouncement(f, "Passwords do not match");
  assertPendingStatus(f, false);
  f.fill("password", "short"); f.fill("confirm", "short");
  await f.submit(); assert.match(f.text(), /Password must be at least 8 characters/); assert.equal(f.requests.length, 1);
  assertErrorAnnouncement(f, "Password must be at least 8 characters");
  assertPendingStatus(f, false);
  f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh"); await f.submit();
  assert.deepEqual(f.requests[1], { url: "/api/auth/register", init: {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: "synthetic-user", password: "abcdefgh" }),
  } });
  assert.deepEqual(f.routes, ["/"]);
  assertErrorAnnouncement(f, "");
  assertRetainedForm(f);
});

test("confirmed-open form retains fresh server refusal, lock and transport-error outcomes", async () => {
  for (const [reply, message, locked] of [
    [{ ok: false, status: 403, body: { error: "Registration is locked" } }, /Registration Locked/, true],
    [{ ok: false, status: 409, body: { error: "Username already exists" } }, /Username already exists/, false],
    [{ ok: false, status: 400, body: {} }, /Registration failed/, false],
    [{ ok: false, networkFailure: true }, /Network error/, false],
  ] as const) {
    const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
    f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
    f.replyToSubmit(reply); await f.submit();
    assert.match(f.text(), message); assert.equal(f.elements().some(element => element.type === "form"), !locked);
    if (locked) assertLockAnnouncement(f);
    else assertErrorAnnouncement(f, "networkFailure" in reply ? "Network error — please try again"
      : "body" in reply && "error" in reply.body ? reply.body.error : "Registration failed");
    assert.deepEqual(f.routes, []); assert.equal(f.requests.length, 2);
    assert(!f.elements().some(element => element.type === "button" && element.props.disabled === true));
  }
});

for (const status of [403, 500]) {
  for (const [label, reply] of [
    ["unreadable JSON", { parseFailure: true }],
    ["null body", { body: null }],
    ["array body", { body: [] }],
    ["string body", { body: "Synthetic proxy failure" }],
    ["object error", { body: { error: { message: "Synthetic proxy failure" } } }],
    ["array error", { body: { error: ["Synthetic proxy failure"] } }],
    ["boolean error", { body: { error: true } }],
    ["numeric error", { body: { error: 42 } }],
  ] as const) {
    test(`registration HTTP ${status} with ${label} retains refusal presentation`, async () => {
      const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
      f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
      f.replyToSubmit({ ok: false, status, ...reply }); await f.submit();
      assert.equal(f.elements().some(element => element.type === "form"), status !== 403);
      assert.match(f.text(), status === 403 ? /Registration Locked/ : /Registration failed/);
      if (status === 403) assertLockAnnouncement(f);
      else assertErrorAnnouncement(f, "Registration failed");
      if (status !== 403) assertRetainedForm(f);
      assert.doesNotMatch(f.text(), /Network error|Synthetic proxy failure/);
      assert.deepEqual(f.routes, []); assert.equal(f.requests.length, 2);
      assert(!f.elements().some(element => element.type === "button" && element.props.disabled === true));
    });
  }
}

test("registration lock announcement appears only after a confirmed closed availability check", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: false } }, true);
  assert.equal(f.firstElements.filter(element => element.props.role === "status").length, 1);
  assert.equal(f.firstElements.filter(element => element.props.role === "alert").length, 0);
  f.release(); await f.settle();
  assertLockAnnouncement(f);
  assert.equal(f.elements().filter(element => element.props.role === "status").length, 0);
  assert.deepEqual(f.requests.map(request => request.url), ["/api/auth/session"]);
});

test("registration HTTP403 announces the lock before its body settles and keeps it after malformed JSON", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
  f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "different");
  await f.submit(); assertErrorAnnouncement(f, "Passwords do not match");
  f.fill("confirm", "abcdefgh");
  f.replyToSubmit({ ok: false, status: 403, parseFailure: true }); f.holdSubmitBody();
  const pending = f.submit(); await f.settle();
  assert.equal(f.submitJsonReads(), 1, "The response body is pending after the HTTP refusal");
  assertLockAnnouncement(f);
  assert.equal(f.requests.length, 2, "Only the explicit valid submission sends a POST");
  f.release(); await pending;
  assertLockAnnouncement(f);
  assert.equal(f.requests.length, 2, "Body settlement must not retry account creation");
});

for (const error of ["Synthetic registration refusal", ""]) {
  test(`registration HTTP403 retains the lock announcement with ${error ? "string" : "empty string"} error feedback`, async () => {
    const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
    f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
    f.replyToSubmit({ ok: false, status: 403, body: { error } }); await f.submit();
    assertLockAnnouncement(f);
    assert.doesNotMatch(f.text(), /Synthetic registration refusal|Registration failed|Network error/);
    assert.equal(f.requests.length, 2);
  });
}

test("registration clears the validation alert during a pending explicit retry", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
  f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "different");
  await f.submit(); assertErrorAnnouncement(f, "Passwords do not match");
  f.fill("confirm", "abcdefgh"); f.holdSubmit();
  const pending = f.submit();
  assertErrorAnnouncement(f, "");
  assertPendingStatus(f, true);
  assert(f.elements().some(element => element.type === "button" && element.props.disabled === true));
  assert.deepEqual(f.routes, []);
  f.release(); await pending;
  assertErrorAnnouncement(f, ""); assert.deepEqual(f.routes, ["/"]);
  assertRetainedForm(f);
  assert(!f.elements().some(element => element.type === "button" && element.props.disabled === true));
});

test("open registration starts with an empty submission status and no account-creation intent", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
  assertPendingStatus(f, false); assertErrorAnnouncement(f, "");
  assert.deepEqual(f.requests.map(request => request.url), ["/api/auth/session"]);
  assert.equal(f.submitJsonReads(), 0); assert.deepEqual(f.routes, []);
});

for (const [label, reply, expected] of [
  ["string error", { body: { error: "Synthetic registration refusal" } }, "Synthetic registration refusal"],
  ["unreadable JSON", { parseFailure: true }, "Registration failed"],
  ["nonstring error", { body: { error: { message: "Synthetic proxy failure" } } }, "Registration failed"],
  ["empty string", { body: { error: "" } }, ""],
] as const) {
  test(`registration remains pending while an HTTP500 ${label} body is held`, async () => {
    const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
    f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
    f.replyToSubmit({ ok: false, status: 500, ...reply }); f.holdSubmitBody();
    const pending = f.submit(); await f.bodyStarted;
    assertPendingStatus(f, true); assertErrorAnnouncement(f, "");
    assert.equal(f.requests.length, 2); assert.equal(f.submitJsonReads(), 1); assert.deepEqual(f.routes, []);
    f.release(); await pending;
    assertErrorAnnouncement(f, expected); assertRetainedForm(f);
    assert.equal(f.requests.length, 2); assert.deepEqual(f.routes, []);
    assert.doesNotMatch(f.text(), /Creating account|Network error|Synthetic proxy failure/);
  });
}

test("registration clears prior server feedback while an explicit retry body is held", async () => {
  const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
  f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
  f.replyToSubmit({ ok: false, status: 409, body: { error: "Username already exists" } });
  await f.submit(); assertErrorAnnouncement(f, "Username already exists"); assertRetainedForm(f);
  f.replyToSubmit({ ok: false, status: 500, parseFailure: true }); f.holdSubmitBody();
  const pending = f.submit(); await f.bodyStarted;
  assertPendingStatus(f, true); assertErrorAnnouncement(f, "");
  assert.equal(f.submitJsonReads(), 2); assert.doesNotMatch(f.text(), /Username already exists|Registration failed|Network error/);
  f.release(); await pending;
  assertErrorAnnouncement(f, "Registration failed"); assertRetainedForm(f);
  assert.equal(f.requests.length, 3); assert.deepEqual(f.routes, []);
});

for (const [label, reply] of [
  ["success", { ok: true, parseFailure: true }],
  ["transport failure", { ok: false, networkFailure: true }],
] as const) {
  test(`registration pending request settles on ${label} without reading a body`, async () => {
    const f = fixture({ ok: true, body: { registrationOpen: true } }); await f.settle();
    f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
    f.replyToSubmit(reply); f.holdSubmit(); const pending = f.submit();
    assertPendingStatus(f, true); assertErrorAnnouncement(f, "");
    assert.equal(f.submitJsonReads(), 0); assert.deepEqual(f.routes, []);
    f.release(); await pending; assertRetainedForm(f);
    assert.equal(f.requests.length, 2); assert.equal(f.submitJsonReads(), 0);
    assert.deepEqual(f.routes, reply.ok ? ["/"] : []);
    assertErrorAnnouncement(f, reply.ok ? "" : "Network error — please try again");
  });
}
