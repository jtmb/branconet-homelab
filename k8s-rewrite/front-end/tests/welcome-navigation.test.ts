import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual page's CTA handlers with scoped React/router/HTTP models.
// This is navigation intent, not DOM, Next routing or server authorization proof.
type Element = { type: unknown; props: Record<string, unknown> };
type Reply = { ok: boolean; body?: unknown; networkFailure?: boolean; parseFailure?: boolean; fetchWait?: Promise<void>; bodyWait?: Promise<void>; bodyEntered?: () => void };
function fixture(replies: Reply[]) {
  const routes: string[] = [], requests: string[] = [];
  let jsonReads = 0;
  const states: unknown[] = [];
  let stateIndex = 0, mounted = false;
  const effects: (() => void)[] = [];
  const jsx = (type: unknown, props: Element["props"]) => ({ type, props });
  const modules: Record<string, unknown> = {
    react: {
      useEffect: (effect: () => void) => { if (!mounted) effects.push(effect); },
      useState: (initial: unknown) => {
        const index = stateIndex++;
        if (!(index in states)) states[index] = initial;
        return [states[index], (value: unknown) => {
          states[index] = typeof value === "function" ? value(states[index]) : value;
        }];
      },
    },
    "react/jsx-runtime": { jsx, jsxs: jsx },
    "next/navigation": { useRouter: () => ({ push: (route: string) => routes.push(route) }) },
    "next/image": { __esModule: true, default: "Image" },
    "lucide-react": new Proxy({}, { get: (_target, name) => name }),
  };
  const filename = "src/app/welcome/page.tsx";
  const output = ts.transpileModule(readFileSync(resolve(filename), "utf8"), {
    fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const component = { exports: {} as { default: () => unknown } };
  runInNewContext(output, { module: component, exports: component.exports,
    require: (name: string) => { assert(name in modules, name); return modules[name]; },
    fetch: async (url: string) => {
      requests.push(url); const reply = replies.shift(); assert(reply, "Unexpected session request");
      if (reply.fetchWait) await reply.fetchWait;
      if (reply.networkFailure) throw new Error("Synthetic network failure");
      return { ok: reply.ok, json: async () => {
        jsonReads++; reply.bodyEntered?.(); if (reply.bodyWait) await reply.bodyWait;
        if (reply.parseFailure) throw new Error("Synthetic JSON failure"); return reply.body;
      } };
    },
  });
  const walk = (value: unknown): Element[] => Array.isArray(value) ? value.flatMap(walk)
    : value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
  const render = () => { stateIndex = 0; return component.exports.default(); };
  const initial = render();
  mounted = true; effects.forEach(effect => effect());
  const elements = () => walk(render());
  const buttons = () => elements().filter(element => element.type === "button");
  assert.equal(buttons().length, 3, "Header, hero and final CTA remain covered");
  const click = async (index: number) => { await (buttons()[index].props.onClick as () => Promise<void>)(); };
  return { routes, requests, click, render, elements, buttons, initial, jsonReads: () => jsonReads };
}

function deferred() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return { promise, release };
}

function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function assertPending(f: ReturnType<typeof fixture>, pending: boolean) {
  const elements = f.elements();
  const statuses = elements.filter(element => element.props.role === "status");
  assert.equal(statuses.length, 1, "One status stays mounted after initial checking");
  const status = statuses[0];
  assert.equal(status.props.className, "sr-only");
  assert.equal(text(status), pending ? "Checking session…" : "");
  assert.equal(elements.filter(element => element.props.role === "alert").length, 0);
  for (const button of f.buttons()) {
    assert.equal(button.props["aria-busy"], pending);
    assert.notEqual(button.props.disabled, true, "Every explicit click remains available");
    assert.equal(text(button), "Get Started", "Visible button copy stays unchanged");
  }
  const contains = (value: unknown): boolean => Array.isArray(value) ? value.some(contains)
    : value === status || Boolean(value && typeof value === "object" && "props" in value && contains((value as Element).props.children));
  for (const element of elements.filter(element => element.props["aria-busy"] === true)) {
    assert.equal(contains(element.props.children), false, "Status stays outside each busy region");
  }
}

test("every welcome CTA preserves successful authenticated, bootstrap and existing-user navigation", async () => {
  for (const [body, destination] of [
    [{ authenticated: true, hasUsers: true }, "/"],
    [{ authenticated: false, hasUsers: false }, "/auth/register"],
    [{ authenticated: false, hasUsers: true }, "/auth/login"],
  ] as const) for (let button = 0; button < 3; button++) {
    const f = fixture([{ ok: true, body }]); await f.click(button);
    assert.deepEqual(f.routes, [destination]); assert.deepEqual(f.requests, ["/api/auth/session"]);
  }
});

test("every welcome CTA refuses failed HTTP session responses before interpreting flags", async () => {
  for (const body of [
    { authenticated: false, error: "Internal server error" },
    { authenticated: false, hasUsers: false },
    { authenticated: true, hasUsers: true },
  ]) for (let button = 0; button < 3; button++) {
    const f = fixture([{ ok: false, body }]); await f.click(button);
    assert.deepEqual(f.routes, ["/auth/login"]); assert.equal(f.jsonReads(), 0);
  }
});

test("every welcome CTA requires explicit boolean session flags before choosing a destination", async () => {
  for (const body of [null, [], false, 0, "session", {},
    { authenticated: false }, { authenticated: true }, { hasUsers: false },
    { authenticated: "false", hasUsers: false }, { authenticated: 1, hasUsers: true },
    { authenticated: false, hasUsers: null }, { authenticated: false, hasUsers: 0 },
    { authenticated: true, hasUsers: "true" },
  ]) for (let button = 0; button < 3; button++) {
    const f = fixture([{ ok: true, body }]); await f.click(button);
    assert.deepEqual(f.routes, ["/auth/login"]);
  }
});

test("every welcome CTA retains login fallback for network and JSON failures", async () => {
  for (const reply of [{ ok: true, networkFailure: true }, { ok: true, parseFailure: true }]) {
    for (let button = 0; button < 3; button++) {
      const f = fixture([reply]); await f.click(button); assert.deepEqual(f.routes, ["/auth/login"]);
    }
  }
});

test("welcome CTA obtains a fresh session response on every click without reusing bootstrap intent", async () => {
  const f = fixture([
    { ok: true, body: { authenticated: false, hasUsers: false } },
    { ok: false, body: { authenticated: false, error: "Internal server error" } },
    { ok: true, body: { authenticated: false, hasUsers: true } },
    { ok: true, body: { authenticated: true, hasUsers: true } },
  ]);
  for (let n = 0; n < 4; n++) await f.click(0);
  assert.deepEqual(f.routes, ["/auth/register", "/auth/login", "/auth/login", "/"]);
  assert.deepEqual(f.requests, Array(4).fill("/api/auth/session"));
});

test("welcome initial checking remains separate and makes no implicit session request", () => {
  const f = fixture([]);
  assert.equal(text(f.initial), "");
  assert.deepEqual(f.requests, []);
  assert.deepEqual(f.routes, []);
  assertPending(f, false);
});

const outcomes: [string, Reply, string][] = [
  ["authenticated", { ok: true, body: { authenticated: true, hasUsers: true } }, "/"],
  ["bootstrap", { ok: true, body: { authenticated: false, hasUsers: false } }, "/auth/register"],
  ["existing user", { ok: true, body: { authenticated: false, hasUsers: true } }, "/auth/login"],
  ["HTTP refusal", { ok: false, body: { authenticated: false, hasUsers: false } }, "/auth/login"],
  ["malformed flags", { ok: true, body: { authenticated: false, hasUsers: "false" } }, "/auth/login"],
  ["JSON failure", { ok: true, parseFailure: true }, "/auth/login"],
  ["network failure", { ok: true, networkFailure: true }, "/auth/login"],
];

for (let button = 0; button < 3; button++) {
  for (const [label, reply, destination] of outcomes) {
    test(`welcome CTA ${button + 1} exposes pending request and settles ${label}`, async () => {
      const gate = deferred();
      const f = fixture([{ ...reply, fetchWait: gate.promise }]);
      assertPending(f, false);
      const click = f.click(button);
      assertPending(f, true);
      assert.deepEqual(f.requests, ["/api/auth/session"]);
      assert.deepEqual(f.routes, []);
      assert.equal(f.jsonReads(), 0);
      gate.release(); await click;
      assertPending(f, false);
      assert.deepEqual(f.routes, [destination]);
      assert.equal(f.jsonReads(), reply.ok && !reply.networkFailure ? 1 : 0);
    });
  }
  for (const [label, reply, destination] of outcomes.filter(([, reply]) => reply.ok && !reply.networkFailure)) {
    test(`welcome CTA ${button + 1} stays pending during ${label} JSON body`, async () => {
      const gate = deferred(), entered = deferred();
      const f = fixture([{ ...reply, bodyWait: gate.promise, bodyEntered: entered.release }]);
      const click = f.click(button);
      await entered.promise;
      assert.equal(f.jsonReads(), 1);
      assert.deepEqual(f.routes, []);
      assertPending(f, true);
      gate.release(); await click;
      assertPending(f, false);
      assert.deepEqual(f.routes, [destination]);
    });
  }
}

for (const order of [[0, 1, 2], [2, 0, 1], [1, 2, 0]]) {
  test(`overlapping welcome clicks retain independent requests and pending until last settlement ${order.join("-")}`, async () => {
    const gates = [deferred(), deferred(), deferred()];
    const f = fixture([
      { ok: true, body: { authenticated: false, hasUsers: false }, fetchWait: gates[0].promise },
      { ok: true, body: { authenticated: true, hasUsers: true }, fetchWait: gates[1].promise },
      { ok: true, networkFailure: true, fetchWait: gates[2].promise },
    ]);
    const clicks = [f.click(0), f.click(1), f.click(2)];
    const expected = ["/auth/register", "/", "/auth/login"];
    assert.deepEqual(f.requests, Array(3).fill("/api/auth/session"));
    assertPending(f, true);
    const settled: string[] = [];
    for (const [index, request] of order.entries()) {
      gates[request].release(); await clicks[request]; settled.push(expected[request]);
      assert.deepEqual(f.routes, settled, "Existing completion-order navigation remains unchanged");
      assertPending(f, index < 2);
    }
  });
}

test("overlapping clicks of the same welcome button each obtain fresh session authority", async () => {
  const first = deferred(), second = deferred();
  const f = fixture([
    { ok: true, body: { authenticated: false, hasUsers: false }, fetchWait: first.promise },
    { ok: false, body: { authenticated: true, hasUsers: true }, fetchWait: second.promise },
  ]);
  const a = f.click(0), b = f.click(0);
  assert.deepEqual(f.requests, Array(2).fill("/api/auth/session"));
  assertPending(f, true);
  second.release(); await b;
  assert.deepEqual(f.routes, ["/auth/login"]); assertPending(f, true);
  first.release(); await a;
  assert.deepEqual(f.routes, ["/auth/login", "/auth/register"]); assertPending(f, false);
});
