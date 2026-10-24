import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as model from "../src/components/secrets/kv-administration-model";

// Actual hooks/client and retention metadata JSX only. Omit every adjacent
// workflow callback and all JSX after the first retention box before evaluation.
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const selected = parsed.statements.filter(statement => ts.isFunctionDeclaration(statement) &&
  ["useTask", "History"].includes(statement.name?.text ?? ""));
assert.equal(selected.length, 2);
const printer = ts.createPrinter();
const declarations = selected.map(statement => {
  const fn = statement as ts.FunctionDeclaration;
  if (fn.name!.text !== "History") return fn.getText(parsed);
  const statements = fn.body!.statements;
  const minimum = statements.findIndex(statement => ts.isVariableStatement(statement) &&
    statement.declarationList.declarations.some(declaration => declaration.name.getText(parsed) === "minimum"));
  assert(minimum > 0);
  const boundary = statements[minimum + 1];
  assert(ts.isVariableStatement(boundary) && boundary.declarationList.declarations.length === 1 &&
    boundary.declarationList.declarations[0].name.getText(parsed) === "destroy",
  "Exact excluded workflow callback boundary changed");
  const returned = statements.at(-1)!;
  assert(ts.isReturnStatement(returned) && returned.expression && ts.isParenthesizedExpression(returned.expression));
  const fieldset = returned.expression.expression;
  assert(ts.isJsxElement(fieldset));
  const boxes = fieldset.children.filter(ts.isJsxElement);
  const retentionBox = boxes[0];
  assert(retentionBox && retentionBox.openingElement.tagName.getText(parsed) === "div");
  const heading = retentionBox.children.find(ts.isJsxElement)!;
  assert(heading.openingElement.tagName.getText(parsed) === "h3" &&
    heading.children.some(child => ts.isJsxText(child) && child.text === "Committed-version retention"),
  "Exact first retention JSX box boundary changed");
  const view = ts.factory.updateJsxElement(fieldset, fieldset.openingElement, [retentionBox], fieldset.closingElement);
  const receiver = ts.createSourceFile("receiver.ts", `function receive() {
    return { retention, retentionConfirm, message, finished, selected, task,
      setRetention, setRetentionConfirm, setMessage, setSelected, view: null };
  }`, ts.ScriptTarget.Latest, true);
  const state = ((receiver.statements[0] as ts.FunctionDeclaration).body!.statements[0] as ts.ReturnStatement)
    .expression as ts.ObjectLiteralExpression;
  const result = ts.factory.updateObjectLiteralExpression(state, [
    ...state.properties.slice(0, -1), ts.factory.createPropertyAssignment("view", view),
  ]);
  const chosen = printer.printNode(ts.EmitHint.Unspecified, ts.factory.updateFunctionDeclaration(
    fn, fn.modifiers, fn.asteriskToken, fn.name, fn.typeParameters, fn.parameters, fn.type,
    ts.factory.updateBlock(fn.body!, [...statements.slice(0, minimum + 1), ts.factory.createReturnStatement(result)]),
  ), parsed);
  assert(!/\b(?:destroyBody|gcBody|request<CleanupResult>|request<GcPreview>|previewGc|commitGc)\b/.test(chosen),
    "An excluded workflow callback entered the retention fixture");
  assert(!/\/(?:destroy|versions|value|operations|history\/gc)/.test(chosen),
    "An excluded workflow route entered the retention fixture");
  return chosen;
});
const output = ts.transpileModule(declarations.join("\n") + "\nmodule.exports = History;", {
  fileName: filename,
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

type Element = { type: string; props: Record<string, unknown> & { children?: unknown } };
type State = {
  retention: string; retentionConfirm: string; message: string; finished: boolean; selected: number[];
  task: { busy: boolean; error: string }; view: Element;
  setRetention: (value: string) => void; setRetentionConfirm: (value: string) => void;
  setMessage: (value: string) => void; setSelected: (value: number[]) => void;
};
const pathId = "00000000-0000-4000-8000-000000000001";
const admin = { authenticated: true, username: "synthetic-admin", role: "write", engineAdmin: true };
const snapshot: model.PathSnapshot = {
  path: { id: pathId, mountId: "synthetic-mount", path: "synthetic/path", namespace: "synthetic-namespace",
    name: "synthetic-name", revision: 3, retention: 20, fields: [{ field: "synthetic-field", key: "synthetic-key" }] },
  status: { pathId, uid: "synthetic-uid", resourceVersion: "synthetic-rv", head: 1,
    adopted: true, tombstone: false, versions: 1, guardedAdoption: true },
  capabilities: { pathId, revision: 3, nativeMutationEnabled: false, permissions: { update: true } },
  versions: { pathId, uid: "synthetic-uid", resourceVersion: "synthetic-rv", head: 1, items: [] },
};
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const children = (node: unknown): Element[] => {
  if (Array.isArray(node)) return node.flatMap(children);
  if (!node || typeof node !== "object" || !("props" in node)) return [];
  const element = node as Element;
  return [element, ...children(element.props.children)];
};
const commit = (state: State) => {
  const found = children(state.view).find(node => node.type === "Button" && node.props.children === "Commit retention revision");
  assert(found); return found.props as { disabled: boolean; onClick: () => void };
};
const expected = (limit: string) => `retention ${pathId} revision=3 limit=${limit}`;
function harness(captured: model.PathSnapshot = snapshot) {
  const slots: unknown[] = [], pending: (() => void)[] = [];
  const listeners = new Map<string, Set<() => void>>();
  let cursor = 0, dirty = false, state: State, notifications = 0;
  const standard = async (url: string, _init?: RequestInit) => json(
    url === "/api/auth/session" ? admin : { revision: 4, retention: 25 });
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
  const visibility = { ...events, visibilityState: "visible" };
  const component = { exports: undefined as unknown as (props: { snapshot: model.PathSnapshot; changed: () => void }) => State };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { ...model, module: component, exports: {}, useState, useRef, useCallback, useEffect,
    fetch: async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      assert((url === "/api/auth/session" && method === "GET") ||
        (url === `/api/kv/paths/${pathId}` && method === "PATCH"), "Only session and retention metadata PATCH permitted");
      calls.push({ url, method, body: init?.body as string | undefined, cache: init?.cache });
      return handler(url, init);
    },
    Error, queueMicrotask, route: (id: string) => `/api/kv/paths/${id}`,
    Button: "Button", Field: "Field", Exact: "Exact",
    inputClass: "", boxClass: "", window: events, document: visibility,
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
  });
  const render = () => {
    let passes = 0;
    do {
      assert(++passes < 30, "Synthetic render did not converge"); dirty = false; cursor = 0;
      state = component.exports({ snapshot: captured, changed: () => { notifications++; } });
      for (const effect of pending.splice(0)) effect();
    } while (dirty);
    return state;
  };
  const settle = async () => {
    for (let i = 0; i < 50; i++) {
      await new Promise(resolve => setImmediate(resolve)); render();
      if (!state.task.busy) return state;
    }
    assert.fail("Synthetic metadata requests did not settle");
  };
  render();
  return { render, settle, calls, standard, get notifications() { return notifications; },
    respond: (next: typeof handler) => { handler = next; },
    event: (name: string) => { if (name === "visibilitychange") visibility.visibilityState = "hidden";
      for (const listener of listeners.get(name) ?? []) listener(); return render(); },
    ready: async () => {
      await settle(); state.setRetention("25"); state.setRetentionConfirm(expected("25"));
      state.setMessage("synthetic prior retention status"); state.setSelected([17]); return render();
    },
  };
}
function reset(state: State) {
  assert.equal(state.retention, ""); assert.equal(state.retentionConfirm, ""); assert.equal(state.message, "");
  assert.equal(JSON.stringify(state.selected), "[17]", "Retention cleanup preserves adjacent selection");
}
for (const status of [401, 403]) {
  for (const stage of ["preflight", "request", "postflight"]) {
    test(`retention clears three states on malformed ${status} at ${stage}`, async () => {
      const ui = harness(), before = await ui.ready(); let sessions = 0;
      ui.respond(async url => {
        if (url === "/api/auth/session") {
          sessions++;
          return stage === "preflight" || (stage === "postflight" && sessions === 2)
            ? new Response("malformed", { status }) : json(admin);
        }
        return stage === "request" ? new Response("malformed", { status }) : json({ revision: 4 });
      });
      commit(before).onClick(); const after = await ui.settle(); reset(after);
      assert.match(after.task.error, /Fresh authorization denied/); assert.equal(after.finished, true);
      assert.equal(ui.calls.length, stage === "preflight" ? 1 : stage === "request" ? 2 : 3);
      assert.equal(ui.notifications, 0);
    });
  }
  test(`retention clears without waiting for stalled ${status} body`, async () => {
    const ui = harness(), before = await ui.ready(); let cancelled = false;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(new ReadableStream({
      pull: () => new Promise(() => {}), cancel: () => { cancelled = true; return new Promise(() => {}); },
    }), { status }));
    commit(before).onClick(); reset(await ui.settle()); assert(cancelled);
  });
}
for (const stage of ["preflight", "postflight"]) for (const loss of ["role", "engineAdmin", "account"]) {
  test(`retention fresh ${loss} loss at ${stage} clears draft`, async () => {
    const ui = harness(), before = await ui.ready(); let sessions = 0;
    const lost = loss === "role" ? { ...admin, role: "readonly" } : loss === "engineAdmin"
      ? { ...admin, engineAdmin: false } : { ...admin, authenticated: false, username: "" };
    ui.respond(async url => url === "/api/auth/session"
      ? json(++sessions === (stage === "preflight" ? 1 : 2) ? lost : admin) : json({ revision: 4 }));
    commit(before).onClick(); reset(await ui.settle()); assert.equal(ui.notifications, 0);
  });
}
for (const status of [409, 503]) test(`retention ordinary ${status} retains draft and status with existing error invalidation`, async () => {
  const ui = harness(), before = await ui.ready();
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : json({}, status));
  commit(before).onClick(); const after = await ui.settle();
  assert.equal(after.retention, before.retention); assert.equal(after.message, before.message);
  assert.equal(after.retentionConfirm, ""); assert.equal(after.finished, true);
  assert.equal(ui.calls.length, 2); assert.equal(ui.notifications, 0);
  assert.equal(JSON.stringify(after.selected), "[17]");
});
for (const event of ["pagehide", "bortus-session-ended", "visibilitychange"]) {
  test(`retention ${event} clears and fences held metadata`, async () => {
    const ui = harness(), before = await ui.ready(); let release: ((value: Response) => void) | undefined;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Promise(resolve => { release = resolve; }));
    commit(before).onClick(); await new Promise(resolve => setImmediate(resolve)); assert(release);
    reset(ui.event(event)); release(json({ revision: 4 })); reset(await ui.settle()); assert.equal(ui.notifications, 0);
  });
}
test("retention exact captured revision/limit body, pending freeze and metadata success", async () => {
  const ui = harness(); let state = await ui.ready();
  state.setRetentionConfirm("wrong"); state = ui.render(); assert.equal(commit(state).disabled, true);
  state.setRetentionConfirm(expected("25")); state = ui.render(); assert.equal(commit(state).disabled, false);
  let release: ((value: Response) => void) | undefined;
  ui.respond(async (url, init) => init?.method === "PATCH" ? new Promise(resolve => { release = resolve; }) : ui.standard(url, init));
  commit(state).onClick(); state = ui.render(); assert.equal(state.view.props.disabled, true); assert.equal(commit(state).disabled, true);
  await new Promise(resolve => setImmediate(resolve)); assert(release); release(json({ revision: 4, retention: 25 }));
  state = await ui.settle(); assert.equal(state.finished, true); assert.equal(ui.notifications, 1);
  assert.match(state.message, /Retention metadata committed/);
  const sent = ui.calls.find(call => call.method === "PATCH")!;
  assert.deepEqual(JSON.parse(sent.body!), { revision: 3, retention: 25 });
  assert.equal(sent.url, `/api/kv/paths/${pathId}`); assert(ui.calls.every(call => call.cache === "no-store"));
  state = ui.event("pagehide"); reset(state); assert.equal(state.finished, true);
});
test("retention input changes invalidate exact confirmation", async () => {
  const ui = harness(), state = await ui.ready();
  const input = children(state.view).find(node => node.type === "input")!; assert(input);
  (input.props.onChange as (event: unknown) => void)({ target: { value: "26" } });
  const after = ui.render(); assert.equal(after.retention, "26"); assert.equal(after.retentionConfirm, "");
  assert.equal(commit(after).disabled, true); assert.equal(ui.calls.length, 0);
});
test("retention bounds, unchanged limit and captured metadata capabilities gate submission", async () => {
  const ui = harness(); let state = await ui.ready();
  for (const value of ["0", "101", "1.5", "invalid", "20"]) {
    state.setRetention(value); state.setRetentionConfirm(expected(value)); state = ui.render();
    assert.equal(commit(state).disabled, true, value);
  }
  for (const capabilities of [ { ...snapshot.capabilities, revision: 2 },
    { ...snapshot.capabilities, permissions: { update: false } } ]) {
    const denied = harness({ ...snapshot, capabilities }); assert.equal(commit(await denied.ready()).disabled, true);
  }
  assert.equal(ui.calls.length, 0);
});
