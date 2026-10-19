import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual page's CTA handlers with scoped React/router/HTTP models.
// This is navigation intent, not DOM, Next routing or server authorization proof.
type Element = { type: unknown; props: Record<string, unknown> };
type Reply = { ok: boolean; body?: unknown; networkFailure?: boolean; parseFailure?: boolean };
function fixture(replies: Reply[]) {
  const routes: string[] = [], requests: string[] = [];
  let jsonReads = 0;
  const jsx = (type: unknown, props: Element["props"]) => ({ type, props });
  const modules: Record<string, unknown> = {
    react: { useEffect: () => {}, useState: () => [false, () => {}] },
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
      if (reply.networkFailure) throw new Error("Synthetic network failure");
      return { ok: reply.ok, json: async () => {
        jsonReads++; if (reply.parseFailure) throw new Error("Synthetic JSON failure"); return reply.body;
      } };
    },
  });
  const walk = (value: unknown): Element[] => Array.isArray(value) ? value.flatMap(walk)
    : value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
  const buttons = walk(component.exports.default()).filter(element => element.type === "button");
  assert.equal(buttons.length, 3, "Header, hero and final CTA remain covered");
  const click = async (index: number) => { await (buttons[index].props.onClick as () => Promise<void>)(); };
  return { routes, requests, click, jsonReads: () => jsonReads };
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
