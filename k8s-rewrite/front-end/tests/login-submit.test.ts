import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual page with scoped React/router/HTTP models. This checks
// client presentation and submission intent, not DOM or server authentication.
type Element = { type: unknown; props: Record<string, unknown> };
type Reply = { ok: boolean; body?: unknown; parseFailure?: boolean; networkFailure?: boolean };
function fixture(reply: Reply, hold = false) {
  const states: unknown[] = [], routes: string[] = [];
  const requests: { url: string; init: unknown }[] = [];
  let cursor = 0, jsonReads = 0, prevented = 0;
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
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
  return { elements, fill, submit, release, requests, routes, text: () => text(render()),
    jsonReads: () => jsonReads, prevented: () => prevented,
    replyWith: (next: Reply) => { reply = next; } };
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
    assert.doesNotMatch(f.text(), /Network error|Synthetic proxy failure/);
    assert.deepEqual(f.routes, []); assert.equal(f.requests.length, 1); assert.equal(f.jsonReads(), 1);
    assertRetainedForm(f);
  });
}

test("login preserves normal JSON string feedback and intentional empty strings", async () => {
  for (const error of ["Invalid credentials", "Account unavailable", ""]) {
    const f = ready({ ok: false, body: { error } }); await f.submit();
    if (error) assert(f.text().includes(error));
    assert.doesNotMatch(f.text(), /Login failed|Network error/);
    assert.deepEqual(f.routes, []); assertRetainedForm(f);
  }
});

test("login transport failure retains network feedback and recovers loading", async () => {
  const f = ready({ ok: false, networkFailure: true }); await f.submit();
  assert.match(f.text(), /Network error — please try again/);
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
});

test("login disables a pending submit and clears prior feedback on an explicit retry", async () => {
  const f = ready({ ok: false, body: { error: "Invalid credentials" } }, true);
  const pending = f.submit();
  assert(f.elements().some(element => element.type === "button" && element.props.disabled === true));
  assert.deepEqual(f.routes, []); f.release(); await pending;
  assert.match(f.text(), /Invalid credentials/); assertRetainedForm(f);
  f.replyWith({ ok: true }); await f.submit();
  assert.doesNotMatch(f.text(), /Invalid credentials|Login failed|Network error/);
  assert.deepEqual(f.routes, ["/"]); assert.equal(f.requests.length, 2); assertRetainedForm(f);
});
