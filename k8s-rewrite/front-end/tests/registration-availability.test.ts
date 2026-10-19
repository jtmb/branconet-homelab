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
  let cursor = 0, mounted = false, jsonReads = 0;
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
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
      const current = url === "/api/auth/session" ? reply : submitReply;
      if (current.networkFailure) throw new Error("Synthetic network failure");
      return { ok: current.ok, status: current.status, json: async () => {
        if (url === "/api/auth/session") jsonReads++;
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
    requests, routes, fill, submit, jsonReads: () => jsonReads,
    replyToSubmit: (next: Reply) => { submitReply = next; } };
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
    if (!registrationOpen) assert.match(f.text(), /Registration Locked.*disabled by the administrator/s);
    assert.doesNotMatch(f.text(), /Unable to check registration availability/i);
  }
});

test("open registration describes account setup without promising a role from session hints", async () => {
  for (const hint of [{ hasUsers: true }, { hasUsers: false }, {}]) {
    const f = fixture({ ok: true, body: { registrationOpen: true, ...hint } }); await f.settle();
    assert(f.elements().some(element => element.type === "form"));
    assert.match(f.text(), /Set up your Botrus account/);
    assert.doesNotMatch(f.text(), /administrator account|write access|readonly/i);
    f.fill("username", "synthetic-user"); f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh");
    await f.submit();
    assert.equal(f.requests[1]?.url, "/api/auth/register");
    assert.deepEqual(JSON.parse(f.requests[1]?.init?.body ?? "null"), { username: "synthetic-user", password: "abcdefgh" });
    assert.deepEqual(f.routes, ["/"]);
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
  f.fill("password", "short"); f.fill("confirm", "short");
  await f.submit(); assert.match(f.text(), /Password must be at least 8 characters/); assert.equal(f.requests.length, 1);
  f.fill("password", "abcdefgh"); f.fill("confirm", "abcdefgh"); await f.submit();
  assert.deepEqual(f.requests[1], { url: "/api/auth/register", init: {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: "synthetic-user", password: "abcdefgh" }),
  } });
  assert.deepEqual(f.routes, ["/"]);
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
      assert.doesNotMatch(f.text(), /Network error|Synthetic proxy failure/);
      assert.deepEqual(f.routes, []); assert.equal(f.requests.length, 2);
      assert(!f.elements().some(element => element.type === "button" && element.props.disabled === true));
    });
  }
}
