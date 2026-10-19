import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as model from "../src/components/secrets/kv-administration-model";

// Actual hooks/client and declaration/list JSX only. The action function and
// row workflow JSX are deliberately omitted, never exercised by this fixture.
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ["useTask", "usePage", "Rotations"];
const selected = parsed.statements.filter(statement =>
  ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
assert.equal(selected.length, names.length);
const printer = ts.createPrinter();
const declarations = selected.map(statement => {
  const fn = statement as ts.FunctionDeclaration;
  if (fn.name!.text !== "Rotations") return fn.getText(parsed);
  const statements = fn.body!.statements;
  const action = statements.findIndex(statement => ts.isVariableStatement(statement) &&
    statement.declarationList.declarations.some(declaration => declaration.name.getText(parsed) === "action"));
  assert(action > 0 && action === statements.length - 2, "Exact shared action boundary changed");
  const returned = statements.at(-1)!;
  assert(ts.isReturnStatement(returned) && returned.expression && ts.isParenthesizedExpression(returned.expression));
  const fieldset = returned.expression.expression;
  assert(ts.isJsxElement(fieldset));
  const boundary = fieldset.children.findIndex(child => ts.isJsxExpression(child) && child.expression &&
    ts.isBinaryExpression(child.expression) && child.expression.left.getText(parsed) === "row");
  assert(boundary > 0, "Exact row workflow boundary changed");
  const declarationView = ts.factory.updateJsxElement(fieldset, fieldset.openingElement,
    fieldset.children.slice(0, boundary), fieldset.closingElement);
  const receiver = ts.createSourceFile("receiver.ts", `function receive() {
    return { field, kind, consumer, prepareConfirm, prepareExpected, message, row, finished,
      list, task, setField, setKind, setConsumer, setPrepareConfirm, setMessage, view: null };
  }`, ts.ScriptTarget.Latest, true);
  const state = ((receiver.statements[0] as ts.FunctionDeclaration).body!.statements[0] as ts.ReturnStatement)
    .expression as ts.ObjectLiteralExpression;
  const result = ts.factory.updateObjectLiteralExpression(state, [
    ...state.properties.slice(0, -1), ts.factory.createPropertyAssignment("view", declarationView),
  ]);
  return printer.printNode(ts.EmitHint.Unspecified, ts.factory.updateFunctionDeclaration(
    fn, fn.modifiers, fn.asteriskToken, fn.name, fn.typeParameters, fn.parameters, fn.type,
    ts.factory.updateBlock(fn.body!, [...statements.slice(0, action), ts.factory.createReturnStatement(result)]),
  ), parsed);
});
const output = ts.transpileModule(declarations.join("\n") + "\nmodule.exports = Rotations;", {
  fileName: filename,
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

type Element = { type: string; props: Record<string, unknown> & { children?: unknown } };
type Task = { busy: boolean; error: string };
type State = {
  field: string; kind: string; consumer: string; prepareConfirm: string; prepareExpected: string;
  message: string; row: model.Rotation | null; finished: boolean; task: Task; view: Element;
  list: { task: Task; page: model.Page<model.Rotation> | null; controls: Element; refresh: () => void };
  setField: (value: string) => void; setKind: (value: string) => void; setConsumer: (value: string) => void;
  setPrepareConfirm: (value: string) => void; setMessage: (value: string) => void;
};
const pathId = "00000000-0000-4000-8000-000000000001";
const admin = { authenticated: true, username: "synthetic-admin", role: "write", engineAdmin: true };
const snapshot: model.PathSnapshot = {
  path: { id: pathId, mountId: "synthetic-mount", path: "synthetic/path", namespace: "synthetic-namespace",
    name: "synthetic-name", revision: 3, retention: 20, fields: [{ field: "synthetic-field", key: "synthetic-key" }] },
  status: { pathId, uid: "synthetic-uid", resourceVersion: "synthetic-rv", head: 1,
    adopted: true, tombstone: false, versions: 1, guardedAdoption: true },
  capabilities: { pathId, revision: 3, nativeMutationEnabled: true, permissions: { rotate: true } },
  versions: { pathId, uid: "synthetic-uid", resourceVersion: "synthetic-rv", head: 1, items: [] },
};
const rotation: model.Rotation = { id: "synthetic-intent", pathId, field: "synthetic-field", revision: 1,
  state: "prepare", operationId: null, consumerKind: "StatefulSet", consumerNamespace: "synthetic-namespace",
  consumerName: "synthetic-consumer", consumerUid: null, consumerResourceVersion: null };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
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
  let cursor = 0, dirty = false, state: State, notifications = 0;
  const standard = async (url: string, init?: RequestInit) => json(
    url === "/api/auth/session" ? admin : init?.method === "POST" ? rotation :
      { items: [rotation], nextCursor: "synthetic/cursor+one" });
  let handler: typeof standard = standard;
  const calls: { url: string; method: string; body?: string; cache?: RequestCache }[] = [];
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
  const component = { exports: undefined as unknown as (props: { snapshot: model.PathSnapshot; changed: () => void }) => State };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { ...model, module: component, exports: {}, useState, useRef, useCallback, useEffect,
    fetch: async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      assert((url === "/api/auth/session" && method === "GET") ||
        (url.startsWith(`/api/kv/rotations?pathId=${pathId}`) && method === "GET") ||
        (url === "/api/kv/rotations" && method === "POST"), "Only declaration/session/list metadata permitted");
      calls.push({ url, method, body: init?.body as string | undefined, cache: init?.cache });
      return handler(url, init);
    },
    Error, queueMicrotask, route: (id: string) => `/api/kv/paths/${id}`,
    Button: "Button", Table: "Table", TaskState: "TaskState", Field: "Field", Exact: "Exact",
    inputClass: "", boxClass: "", window: events, document: { ...events, visibilityState: "visible" },
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
  });
  const render = () => {
    let passes = 0;
    do {
      assert(++passes < 30, "Synthetic render did not converge"); dirty = false; cursor = 0;
      state = component.exports({ snapshot, changed: () => { notifications++; } });
      for (const effect of pending.splice(0)) effect();
    } while (dirty);
    return state;
  };
  const settle = async () => {
    for (let i = 0; i < 50; i++) {
      await new Promise(resolve => setImmediate(resolve)); render();
      if (!state.task.busy && !state.list.task.busy) return state;
    }
    assert.fail("Synthetic metadata requests did not settle");
  };
  render();
  return { render, settle, calls, standard, get notifications() { return notifications; },
    respond: (next: typeof handler) => { handler = next; },
    event: (name: string) => { for (const listener of listeners.get(name) ?? []) listener(); return render(); },
    ready: async () => {
      await settle(); state.setField("synthetic-field"); state.setKind("StatefulSet");
      state.setConsumer("synthetic-consumer"); render(); state.setPrepareConfirm(state.prepareExpected);
      state.setMessage("synthetic prior declaration success"); return render();
    },
  };
}
function reset(state: State) {
  assert.equal(state.field, ""); assert.equal(state.kind, "Deployment"); assert.equal(state.consumer, "");
  assert.equal(state.prepareConfirm, ""); assert.equal(state.message, "");
}
const prepare = (state: State) => button(state.view, "Prepare intent only").onClick();
for (const status of [401, 403]) for (const channel of ["declaration", "list"]) {
  for (const stage of ["preflight", "request", "postflight"]) {
    test(`declaration ${channel} clears five states on malformed ${status} at ${stage}`, async () => {
      const ui = harness(), before = await ui.ready(), start = ui.calls.length; let sessions = 0;
      ui.respond(async (url, init) => {
        if (url === "/api/auth/session") {
          sessions++;
          if (stage === "preflight" || (stage === "postflight" && sessions === 2))
            return new Response("malformed", { status });
          return json(admin);
        }
        return stage === "request" ? new Response("malformed", { status }) : ui.standard(url, init);
      });
      if (channel === "declaration") prepare(before); else before.list.refresh();
      const after = await ui.settle(); reset(after);
      assert.match((channel === "declaration" ? after.task : after.list.task).error, /Fresh authorization denied/);
      assert.equal(ui.calls.length - start, stage === "preflight" ? 1 : stage === "request" ? 2 : 3);
      assert.equal(ui.notifications, 0);
      assert.equal(after.row, null);
      assert.equal(after.finished, channel === "declaration");
      if (channel === "list") assert.equal(after.list.page, null);
    });
  }
  test(`declaration ${channel} clears without waiting for stalled ${status} body`, async () => {
    const ui = harness(), before = await ui.ready(); let cancelled = false;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(new ReadableStream({
      pull: () => new Promise(() => {}), cancel: () => { cancelled = true; return new Promise(() => {}); },
    }), { status }));
    if (channel === "declaration") prepare(before); else before.list.refresh();
    reset(await ui.settle()); assert(cancelled);
  });
}
for (const channel of ["declaration", "list"]) {
  test(`declaration ${channel} fresh role withdrawal clears draft`, async () => {
    const ui = harness(), before = await ui.ready(), start = ui.calls.length;
    ui.respond(async () => json({ ...admin, role: "readonly" }));
    if (channel === "declaration") prepare(before); else before.list.refresh();
    reset(await ui.settle()); assert.equal(ui.calls.length - start, 1);
  });
  for (const status of [409, 503]) test(`declaration ${channel} ordinary ${status} preserves draft and prior status`, async () => {
    const ui = harness(), before = await ui.ready(), start = ui.calls.length;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : json({}, status));
    if (channel === "declaration") prepare(before); else before.list.refresh();
    const after = await ui.settle();
    for (const key of ["field", "kind", "consumer", "prepareConfirm", "message"] as const)
      assert.equal(after[key], before[key]);
    assert.equal(after.finished, channel === "declaration");
    assert.equal(ui.calls.length - start, 2); assert.equal(ui.notifications, 0);
  });
}
for (const event of ["pagehide", "bortus-session-ended"]) test(`declaration ${event} clears and fences held metadata`, async () => {
  const ui = harness(), before = await ui.ready(); let release: ((value: Response) => void) | undefined;
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Promise(resolve => { release = resolve; }));
  prepare(before); await new Promise(resolve => setImmediate(resolve)); assert(release);
  const withdrawn = ui.event(event); release(json(rotation));
  reset(withdrawn); const after = await ui.settle(); reset(after); assert.equal(after.row, null);
  assert.equal(ui.notifications, 0);
});
test("declaration exact confirmation, pending freeze, unchanged body and successful metadata selection", async () => {
  const ui = harness(); let state = await ui.ready();
  state.setPrepareConfirm("wrong"); state = ui.render(); assert.equal(button(state.view, "Prepare intent only").disabled, true);
  state.setPrepareConfirm(state.prepareExpected); state = ui.render(); assert.equal(button(state.view, "Prepare intent only").disabled, false);
  let release: ((value: Response) => void) | undefined;
  ui.respond(async (url, init) => init?.method === "POST" ? new Promise(resolve => { release = resolve; }) : ui.standard(url, init));
  prepare(state); state = ui.render(); assert.equal(state.view.props.disabled, true);
  assert.equal(button(state.view, "Prepare intent only").disabled, true);
  await new Promise(resolve => setImmediate(resolve)); assert(release); release(json(rotation)); state = await ui.settle();
  assert.deepEqual(copy(state.row), rotation); assert.equal(state.prepareConfirm, ""); assert.equal(ui.notifications, 1);
  assert.match(state.message, /Rotation intent prepared/);
  const sent = ui.calls.find(call => call.method === "POST")!;
  assert.deepEqual(JSON.parse(sent.body!), { pathId, pathRevision: 3, field: "synthetic-field",
    consumer: { kind: "StatefulSet", namespace: "synthetic-namespace", name: "synthetic-consumer" } });
  assert(ui.calls.every(call => call.cache === "no-store"));
  state.setField("synthetic-field"); state.setConsumer("another-consumer"); ui.render();
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(null, { status: 403 }));
  state.list.refresh(); const denied = await ui.settle(); reset(denied);
  assert.deepEqual(copy(denied.row), rotation, "Declaration reset preserves selected workflow row");
});
for (const label of ["Mapped field", "Same-namespace consumer kind", "Exact consumer name in synthetic-namespace"])
  test(`declaration input ${label} invalidates exact confirmation`, async () => {
    const ui = harness(), state = await ui.ready();
    const field = children(state.view).find(node => node.type === "Field" && node.props.label === label)!;
    assert(field); const control = children(field)[1];
    (control.props.onChange as (event: unknown) => void)({ target: { value: "synthetic-change" } });
    assert.equal(ui.render().prepareConfirm, "");
  });
