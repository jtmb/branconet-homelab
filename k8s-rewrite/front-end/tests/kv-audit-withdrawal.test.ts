import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as model from "../src/components/secrets/kv-administration-model";

// Actual production hooks, handlers and JSX, with a scoped state/element
// receiver. No React DOM, browser, database, native/API handler or credentials.
// The fetch double refuses everything except session/audit metadata GETs.
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ["useTask", "usePage", "AuditView"];
const selected = parsed.statements.filter(statement =>
  ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
assert.equal(selected.length, names.length);
const printer = ts.createPrinter();
const declarations = selected.map(statement => {
  const fn = statement as ts.FunctionDeclaration;
  if (fn.name!.text !== "AuditView") return fn.getText(parsed);
  const returned = fn.body!.statements.at(-1)!;
  assert(ts.isReturnStatement(returned) && returned.expression);
  const receiver = ts.createSourceFile("receiver.ts", `function receive() {
    return { pathFilter, operationFilter, filters, validation, list,
      setPathFilter, setOperationFilter, view: null };
  }`, ts.ScriptTarget.Latest, true);
  const stateReturn = (receiver.statements[0] as ts.FunctionDeclaration).body!.statements[0] as ts.ReturnStatement;
  const state = stateReturn.expression as ts.ObjectLiteralExpression;
  const result = ts.factory.updateObjectLiteralExpression(state, [
    ...state.properties.slice(0, -1), ts.factory.createPropertyAssignment("view", returned.expression),
  ]);
  return printer.printNode(ts.EmitHint.Unspecified, ts.factory.updateFunctionDeclaration(
    fn, fn.modifiers, fn.asteriskToken, fn.name, fn.typeParameters, fn.parameters, fn.type,
    ts.factory.updateBlock(fn.body!, [...fn.body!.statements.slice(0, -1), ts.factory.createReturnStatement(result)]),
  ), parsed);
});
const output = ts.transpileModule(declarations.join("\n") + "\nmodule.exports = AuditView;", {
  fileName: filename,
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

type Element = { type: string; props: Record<string, unknown> & { children?: unknown } };
type State = {
  pathFilter: string; operationFilter: string; filters: string | null; validation: string;
  setPathFilter: (value: string) => void; setOperationFilter: (value: string) => void;
  list: { task: { busy: boolean; error: string }; page: model.Page<model.Audit> | null;
    controls: Element; refresh: () => void };
  view: Element;
};
const pathA = "00000000-0000-4000-8000-000000000001";
const pathB = "00000000-0000-4000-8000-000000000002";
const operation = "00000000-0000-4000-8000-000000000003";
const session = { authenticated: true, username: "synthetic-reader", role: "readonly", engineAdmin: false };
const row: model.Audit = {
  id: "synthetic-audit", actorId: "synthetic-actor", operationId: operation, pathId: pathA,
  mountId: null, path: "synthetic/path", namespace: "synthetic-namespace", name: "synthetic-name",
  principal: null, alias: null, key: null, action: "read", previousVersion: null,
  newVersion: null, outcome: "authorized", createdAt: "2026-01-01T00:00:00.000Z",
};
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const children = (node: unknown): Element[] => {
  if (Array.isArray(node)) return node.flatMap(children);
  if (!node || typeof node !== "object" || !("props" in node)) return [];
  const element = node as Element;
  return [element, ...children(element.props.children)];
};
const button = (tree: unknown, label: string) => {
  const found = children(tree).find(node => node.type === "Button" && node.props.children === label);
  assert(found, `Missing production button: ${label}`);
  return found.props as { disabled?: boolean; onClick: () => void };
};

function harness() {
  const slots: unknown[] = [], pending: (() => void)[] = [];
  const listeners = new Map<string, Set<() => void>>();
  let cursor = 0, dirty = false, state: State;
  let handler: (url: string) => Promise<Response> = async url =>
    json(url === "/api/auth/session" ? session : { items: [row], nextCursor: "synthetic/cursor+one" });
  const calls: { url: string; method: string; body: unknown; cache: RequestCache | undefined }[] = [];
  const useState = (initial: unknown) => {
    const index = cursor++;
    if (!slots[index]) slots[index] = { value: initial, set: (value: unknown) => {
      const slot = slots[index] as { value: unknown };
      slot.value = typeof value === "function" ? value(slot.value) : value; dirty = true;
    } };
    const slot = slots[index] as { value: unknown; set: (value: unknown) => void };
    return [slot.value, slot.set];
  };
  const useRef = (value: unknown) => {
    const index = cursor++;
    return slots[index] ?? (slots[index] = { current: value });
  };
  const changed = (old: unknown[] | undefined, next: unknown[]) =>
    !old || old.length !== next.length || next.some((value, index) => !Object.is(value, old[index]));
  const useCallback = (callback: unknown, deps: unknown[]) => {
    const index = cursor++, old = slots[index] as { deps: unknown[]; callback: unknown } | undefined;
    if (changed(old?.deps, deps)) slots[index] = { deps, callback };
    return (slots[index] as { callback: unknown }).callback;
  };
  const useEffect = (effect: () => (() => void) | void, deps: unknown[]) => {
    const index = cursor++, old = slots[index] as { deps: unknown[]; cleanup?: () => void } | undefined;
    if (changed(old?.deps, deps)) {
      const slot = { deps, cleanup: undefined as (() => void) | undefined }; slots[index] = slot;
      pending.push(() => { old?.cleanup?.(); slot.cleanup = effect() ?? undefined; });
    }
  };
  const events = {
    addEventListener: (name: string, callback: () => void) => {
      if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name)!.add(callback);
    },
    removeEventListener: (name: string, callback: () => void) => listeners.get(name)?.delete(callback),
  };
  const component = { exports: undefined as unknown as (props: { pathId: string }) => State };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { ...model, module: component, exports: {}, useState, useRef, useCallback, useEffect,
    fetch: async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      assert.equal(method, "GET"); assert.equal(init?.body, undefined);
      assert(url === "/api/auth/session" || url === "/api/kv/audit" || url.startsWith("/api/kv/audit?"));
      calls.push({ url, method, body: init?.body, cache: init?.cache }); return handler(url);
    },
    Error, URLSearchParams, Button: "Button", Table: "Table", TaskState: "TaskState", Field: "Field", inputClass: "",
    window: events, document: { ...events, visibilityState: "visible" },
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
  });
  const render = () => {
    let passes = 0;
    do {
      assert(++passes < 30, "Synthetic render did not converge"); dirty = false; cursor = 0;
      state = component.exports({ pathId: pathA });
      for (const effect of pending.splice(0)) effect();
    } while (dirty);
    return state;
  };
  const settle = async () => {
    for (let i = 0; i < 50; i++) {
      await new Promise(resolve => setImmediate(resolve)); render();
      if (!state.list.task.busy) return state;
    }
    assert.fail("Synthetic metadata request did not settle");
  };
  const click = (label: string) => {
    const current = render();
    const control = button(label === "Apply audit filters" ? current.view : current.list.controls, label);
    assert.equal(!!control.disabled, false, `Disabled production button: ${label}`); control.onClick(); render();
  };
  const drafts = (path: string, op: string) => {
    state.setPathFilter(path); state.setOperationFilter(op); return render();
  };
  render();
  return { render, settle, click, drafts, calls,
    respond: (next: typeof handler) => { handler = next; },
    event: (name: string) => { for (const listener of listeners.get(name) ?? []) listener(); render(); },
  };
}

function cleared(state: State) {
  assert.equal(state.pathFilter, ""); assert.equal(state.operationFilter, "");
  assert.equal(state.filters, null); assert.equal(state.validation, ""); assert.equal(state.list.page, null);
  for (const label of ["Previous page", "Next page", "Refresh metadata"])
    assert.equal(button(state.list.controls, label).disabled, true);
  assert.equal(button(state.view, "Apply audit filters").disabled, false);
}

test("audit exact applied filters reset prior cursor history and encode only supported metadata query fields", async () => {
  const ui = harness(); await ui.settle(); ui.click("Next page"); await ui.settle();
  ui.click("Next page"); await ui.settle(); ui.drafts(pathB, operation);
  const start = ui.calls.length; ui.click("Apply audit filters"); const after = await ui.settle();
  assert.equal(button(after.list.controls, "Previous page").disabled, true);
  assert.equal(ui.calls.length - start, 3);
  const request = ui.calls[start + 1];
  assert.equal(request.url, `/api/kv/audit?pathId=${pathB}&operationId=${operation}`);
  assert.equal(request.cache, "no-store");
  ui.click("Next page"); await ui.settle();
  assert.equal(ui.calls.at(-2)!.url, `${request.url}&cursor=synthetic%2Fcursor%2Bone`);
  ui.click("Previous page"); await ui.settle(); assert.equal(ui.calls.at(-2)!.url, request.url);
});

test("audit invalid UUIDs retain current page and send no request; authorized is a decision label", async () => {
  const ui = harness(); const before = await ui.settle(); ui.drafts("invalid", operation);
  const start = ui.calls.length; ui.click("Apply audit filters"); const after = await ui.settle();
  assert.equal(ui.calls.length, start); assert.equal(after.list.page, before.list.page);
  assert.equal(after.validation, "Filters require exact UUIDs.");
  assert(children(after.view).some(node => String(node.props.children).includes("does not prove")));
});

test("empty filtered audit pages remain forward reachable and previous history stays bounded to 100", async () => {
  const ui = harness(); await ui.settle(); let page = 0;
  ui.respond(async url => json(url === "/api/auth/session" ? session : { items: [], nextCursor: `synthetic-${++page}` }));
  ui.click("Refresh metadata"); await ui.settle();
  for (let i = 0; i < 103; i++) { ui.click("Next page"); await ui.settle(); }
  let after = ui.render(); assert.equal(after.list.page!.items.length, 0);
  assert.equal(button(after.list.controls, "Next page").disabled, false);
  assert(children(after.view).some(node => String(node.props.children).includes("Filtered pages can be empty")));
  for (let i = 0; i < 100; i++) { ui.click("Previous page"); after = await ui.settle(); }
  assert.equal(button(after.list.controls, "Previous page").disabled, true);
});

for (const status of [401, 403]) {
  for (const stage of ["preflight", "operation", "postflight"]) {
    test(`audit ${status} at ${stage} clears complete filter/page state without an automatic request`, async () => {
      const ui = harness(); await ui.settle(); ui.click("Next page"); await ui.settle();
      ui.drafts("invalid", operation); ui.click("Apply audit filters"); ui.drafts(pathB, operation);
      let sessions = 0;
      ui.respond(async url => {
        if (url === "/api/auth/session") {
          sessions++; return stage === "preflight" || (stage === "postflight" && sessions === 2)
            ? new Response("malformed", { status }) : json(session);
        }
        return stage === "operation" ? new Response("malformed", { status }) : json({ items: [row], nextCursor: "next" });
      });
      const start = ui.calls.length; ui.click("Next page"); const after = await ui.settle(); cleared(after);
      assert.match(after.list.task.error, /Fresh authorization denied/);
      assert.equal(ui.calls.length - start, stage === "preflight" ? 1 : stage === "operation" ? 2 : 3);
      const end = ui.calls.length; await ui.settle(); assert.equal(ui.calls.length, end);
      ui.respond(async url => json(url === "/api/auth/session" ? session : { items: [row], nextCursor: null }));
      ui.click("Apply audit filters"); const resumed = await ui.settle();
      assert.equal(ui.calls.length - end, 3); assert.equal(ui.calls[end + 1].url, "/api/kv/audit");
      assert.equal(resumed.list.page!.items.length, 1);
      assert.equal(button(resumed.list.controls, "Previous page").disabled, true);
    });
  }
  test(`audit ${status} cleanup never awaits a stalled denial body cancellation`, async () => {
    const ui = harness(); await ui.settle(); ui.drafts(pathB, operation); let cancellations = 0;
    ui.respond(async url => url === "/api/auth/session" ? json(session) : new Response(new ReadableStream({
      cancel() { cancellations++; return new Promise(() => {}); },
    }), { status }));
    const start = ui.calls.length; ui.click("Refresh metadata"); cleared(await ui.settle());
    assert.equal(cancellations, 1); assert.equal(ui.calls.length - start, 2);
  });
}

test("audit semantic authentication loss and postflight identity/role/administration change clear without implicit retry", async () => {
  for (const fresh of [{ authenticated: false }, { ...session, username: "another-reader" },
    { ...session, role: "write" }, { ...session, engineAdmin: true }]) {
    const ui = harness(); await ui.settle(); ui.drafts(pathB, operation); let sessions = 0;
    ui.respond(async url => url === "/api/auth/session" ? json(++sessions === 1 && fresh.authenticated ? session : fresh)
      : json({ items: [row], nextCursor: null }));
    const start = ui.calls.length; ui.click("Refresh metadata"); cleared(await ui.settle());
    assert.equal(ui.calls.length - start, fresh.authenticated ? 3 : 1);
  }
});

test("audit metadata remains available to a fresh scoped writer without engine administration", async () => {
  const ui = harness(); await ui.settle();
  const scoped = { ...session, role: "write", engineAdmin: false };
  ui.respond(async url => json(url === "/api/auth/session" ? scoped : { items: [row], nextCursor: null }));
  const start = ui.calls.length; ui.click("Refresh metadata"); const after = await ui.settle();
  assert.equal(after.list.page!.items.length, 1); assert.equal(after.list.task.error, "");
  assert.equal(after.pathFilter, pathA); assert.equal(ui.calls.length - start, 3);
});

test("ordinary audit 409/503 failures preserve entered and applied filters, with no automatic retry", async () => {
  for (const status of [409, 503]) {
    const ui = harness(); await ui.settle(); const original = ui.render().filters; ui.drafts(pathB, operation);
    ui.respond(async url => url === "/api/auth/session" ? json(session) : json({}, status));
    const start = ui.calls.length; ui.click("Refresh metadata"); const after = await ui.settle();
    assert.equal(after.pathFilter, pathB); assert.equal(after.operationFilter, operation); assert.equal(after.filters, original);
    assert.equal(after.list.page, null); assert(after.list.task.error); assert.equal(ui.calls.length - start, 2);
    assert.equal(button(after.list.controls, "Refresh metadata").disabled, false);
  }
});

test("oversized audit metadata pages are refused without displaying rows", async () => {
  const ui = harness(); await ui.settle();
  ui.respond(async url => json(url === "/api/auth/session" ? session : { items: Array.from({ length: 101 }, () => row), nextCursor: null }));
  ui.click("Refresh metadata"); const after = await ui.settle();
  assert.equal(after.list.page, null); assert.match(after.list.task.error, /Metadata page exceeds the row limit/);
});

test("page hiding cancels late metadata display, clears audit filters and does not restart loading", async () => {
  const ui = harness(); await ui.settle(); ui.drafts(pathB, operation);
  let release!: (response: Response) => void;
  ui.respond(async url => url === "/api/auth/session" ? json(session) : new Promise(resolve => { release = resolve; }));
  const start = ui.calls.length; ui.click("Refresh metadata");
  for (let i = 0; i < 20 && !release; i++) await new Promise(resolve => setImmediate(resolve));
  assert(release); ui.event("pagehide"); release(json({ items: [row], nextCursor: "late" }));
  cleared(await ui.settle()); assert.equal(ui.calls.length - start, 2);
});
