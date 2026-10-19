import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as model from "../src/components/secrets/kv-administration-model";

// Evaluate actual production hooks, handlers and JSX with a scoped receiver.
// This is a state/element model, without React DOM, a browser or a server.
// Fetch doubles accept only session/list metadata and synthetic revocation;
// issuance and token generation are never called. The local display sentinel
// below is deliberately not a credential and never appears in a response.
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ["useTask", "usePage", "Identities"];
const selected = parsed.statements.filter(statement =>
  ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
assert.equal(selected.length, names.length);
const printer = ts.createPrinter();
const declarations = selected.map(statement => {
  const fn = statement as ts.FunctionDeclaration;
  if (fn.name!.text !== "Identities") return fn.getText(parsed);
  const returned = fn.body!.statements.at(-1)!;
  assert(ts.isReturnStatement(returned) && returned.expression);
  const receiver = ts.createSourceFile("receiver.ts", `function receive() {
    return { credential, issuedId, owner, name, expiry, scopes, selected, confirm,
      issueAck, result, list, task, revoke, setCredential, setIssuedId, setOwner,
      setName, setExpiry, setScopes, setConfirm, setIssueAck, view: null };
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
const output = ts.transpileModule(declarations.join("\n") + "\nmodule.exports = Identities;", {
  fileName: filename,
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

type Element = { type: string; props: Record<string, unknown> & { children?: unknown } };
type Task = { busy: boolean; error: string };
type State = {
  credential: string | null; issuedId: string; owner: string; name: string; expiry: string;
  scopes: model.IdentityScope[]; selected: model.Identity | null; confirm: string;
  issueAck: boolean; result: string; task: Task; view: Element;
  list: { task: Task; page: model.Page<model.Identity> | null; refresh: () => void };
  revoke: () => void;
  setCredential: (value: string | null) => void; setIssuedId: (value: string) => void;
  setOwner: (value: string) => void; setName: (value: string) => void; setExpiry: (value: string) => void;
  setScopes: (value: model.IdentityScope[]) => void; setConfirm: (value: string) => void;
  setIssueAck: (value: boolean) => void;
};
const admin = { authenticated: true, username: "synthetic-admin", role: "write", engineAdmin: true };
const identity: model.Identity = {
  id: "synthetic-identity", ownerId: "synthetic-owner", name: "synthetic-name",
  expiresAt: "2099-01-01T00:00:00.000Z", revokedAt: null, createdAt: "2026-01-01T00:00:00.000Z",
};
const draftScope: model.IdentityScope = { mountId: "synthetic-mount", prefix: "synthetic/path", actions: ["read"] };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const children = (node: unknown): Element[] => {
  if (Array.isArray(node)) return node.flatMap(children);
  if (!node || typeof node !== "object" || !("props" in node)) return [];
  const element = node as Element;
  return [element, ...children(element.props.children)];
};
const button = (state: State, label: string) => {
  const found = children(state.view).find(node => node.type === "Button" && node.props.children === label);
  assert(found, `Missing production button: ${label}`);
  return found.props as { disabled?: boolean; onClick: () => void };
};

function harness() {
  const slots: unknown[] = [], pending: (() => void)[] = [];
  const listeners = new Map<string, Set<() => void>>();
  let cursor = 0, dirty = false, notifications = 0;
  let state: State;
  let handler: (url: string, init?: RequestInit) => Promise<Response> = async url =>
    json(url === "/api/auth/session" ? admin : { items: [identity], nextCursor: null });
  const calls: { url: string; method: string; body: unknown }[] = [];
  const useState = (initial: unknown) => {
    const index = cursor++;
    if (!slots[index]) slots[index] = { value: initial, set: (value: unknown) => {
      (slots[index] as { value: unknown }).value = value; dirty = true;
    } };
    const slot = slots[index] as { value: unknown; set: (value: unknown) => void };
    return [slot.value, slot.set];
  };
  const useRef = (value: unknown) => {
    const index = cursor++;
    return slots[index] ?? (slots[index] = { current: value });
  };
  const depsChanged = (old: unknown[] | undefined, next: unknown[]) =>
    !old || old.length !== next.length || next.some((value, index) => !Object.is(value, old[index]));
  const useCallback = (callback: unknown, deps: unknown[]) => {
    const index = cursor++, old = slots[index] as { deps: unknown[]; callback: unknown } | undefined;
    if (depsChanged(old?.deps, deps)) slots[index] = { deps, callback };
    return (slots[index] as { callback: unknown }).callback;
  };
  const useEffect = (effect: () => void, deps: unknown[]) => {
    const index = cursor++, old = slots[index] as { deps: unknown[] } | undefined;
    if (depsChanged(old?.deps, deps)) { slots[index] = { deps }; pending.push(effect); }
  };
  const events = {
    addEventListener: (name: string, callback: () => void) => {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name)!.add(callback);
    },
    removeEventListener: (name: string, callback: () => void) => listeners.get(name)?.delete(callback),
  };
  const component = { exports: undefined as unknown as (props: { changed: () => void }) => State };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { ...model, module: component, exports: {}, useState, useRef, useCallback, useEffect,
    fetch: async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      assert((url === "/api/auth/session" && method === "GET") ||
        (url === "/api/kv/identities" && method === "GET") ||
        (url === `/api/kv/identities/${identity.id}` && method === "DELETE"), "Only metadata doubles allowed");
      calls.push({ url, method, body: init?.body }); return handler(url, init);
    },
    Error, Button: "Button", Table: "Table", TaskState: "TaskState", Field: "Field", Exact: "Exact",
    Check: "Check", Actions: "Actions", boxClass: "", inputClass: "",
    window: events, document: { ...events, visibilityState: "visible" },
    require: (name: string) => {
      assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx };
    },
  });
  const render = () => {
    do {
      dirty = false; cursor = 0;
      state = component.exports({ changed: () => { notifications++; } });
      for (const effect of pending.splice(0)) effect();
    } while (dirty);
    return state;
  };
  const settle = async () => {
    for (let i = 0; i < 50; i++) {
      await new Promise(resolve => setImmediate(resolve)); render();
      if (!state.task.busy && !state.list.task.busy) return state;
    }
    assert.fail("Synthetic request did not settle");
  };
  const seedDraft = () => {
    state.setOwner("synthetic-draft-owner"); state.setName("synthetic-draft-name");
    state.setExpiry("2099-02-02T00:00"); state.setScopes([copy(draftScope)]);
    button(render(), "Revoke identity").onClick(); render();
    state.setConfirm(model.identityConfirmation(identity)); state.setIssueAck(true);
    // Exercise local sensitive-display clearing without issuing/revealing any token.
    state.setCredential("NONCREDENTIAL-LOCAL-STATE-SENTINEL"); state.setIssuedId("synthetic-display-id");
    return render();
  };
  render();
  return { render, settle, seedDraft, calls, get notifications() { return notifications; },
    respond: (next: typeof handler) => { handler = next; },
    event: (name: string) => { for (const listener of listeners.get(name) ?? []) listener(); },
    ready: async () => { await settle(); return seedDraft(); },
  };
}

function reset(state: State) {
  assert.equal(state.credential, null); assert.equal(state.issuedId, "");
  assert.equal(state.owner, ""); assert.equal(state.name, ""); assert.equal(state.expiry, "");
  assert.deepEqual(copy(state.scopes), [{ mountId: "", prefix: "", actions: ["list"] }]);
  assert.equal(state.selected, null); assert.equal(state.confirm, "");
  assert.equal(state.issueAck, false); assert.equal(state.result, "");
}

for (const status of [401, 403]) {
  for (const task of ["operation", "list"]) {
    for (const stage of ["preflight", "operation", "postflight"]) {
      test(`actual identity ${task} clears all local state on ${status} at ${stage}`, async () => {
        const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
        let sessions = 0;
        ui.respond(async url => {
          if (url === "/api/auth/session") {
            sessions++;
            return stage === "preflight" || (stage === "postflight" && sessions === 2)
              ? new Response("malformed", { status }) : json(admin);
          }
          return stage === "operation" ? new Response("malformed", { status })
            : json(task === "list" ? { items: [identity], nextCursor: null } : { revoked: true });
        });
        if (task === "list") before.list.refresh(); else before.revoke();
        const after = await ui.settle(); reset(after);
        assert.match((task === "list" ? after.list.task : after.task).error, /Fresh authorization denied/);
        assert.equal(ui.calls.length - start, stage === "preflight" ? 1 : stage === "operation" ? 2 : 3);
        if (task === "list") assert.equal(after.list.page, null);
        assert.equal(ui.notifications, 0);
      });
    }
    test(`identity ${task} ${status} clears without awaiting stalled denial cancellation`, async () => {
      const ui = harness(); const before = await ui.ready(); let cancellations = 0;
      ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(new ReadableStream({
        cancel() { cancellations++; return new Promise(() => {}); },
      }), { status }));
      if (task === "list") before.list.refresh(); else before.revoke();
      reset(await ui.settle()); assert.equal(cancellations, 1); assert.equal(ui.notifications, 0);
    });
  }
  test(`independent identity-list ${status} clears prior successful revoke display`, async () => {
    const ui = harness(); let before = await ui.ready();
    ui.respond(async (url, init) => json(url === "/api/auth/session" ? admin
      : init?.method === "DELETE" ? { revoked: true } : { items: [identity], nextCursor: null }));
    before.revoke(); before = await ui.settle(); assert.match(before.result, /is revoked/);
    assert.equal(ui.notifications, 1); before = ui.seedDraft();
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(null, { status }));
    before.list.refresh(); reset(await ui.settle()); assert.equal(ui.notifications, 1);
  });
}

test("identity semantic fresh-admin withdrawal clears before and after metadata work", async () => {
  for (const task of ["list", "operation"]) for (const postflight of [false, true]) {
    const ui = harness(); const before = await ui.ready(); let sessions = 0;
    ui.respond(async url => {
      if (url !== "/api/auth/session") return json(task === "list" ? { items: [identity], nextCursor: null } : { revoked: true });
      sessions++; return json(postflight && sessions === 1 ? admin : { ...admin, engineAdmin: false });
    });
    if (task === "list") before.list.refresh(); else before.revoke();
    reset(await ui.settle()); assert.equal(ui.notifications, 0);
  }
});

test("captured exact ID/owner/expiry confirmation blocks incomplete revocation", async () => {
  for (const confirmation of ["", `revoke ${identity.id}`, model.identityConfirmation({ ...identity, ownerId: "other" }),
    model.identityConfirmation({ ...identity, expiresAt: "2099-01-02T00:00:00.000Z" })]) {
    const ui = harness(); let before = await ui.ready(); before.setConfirm(confirmation); before = ui.render();
    assert.equal(button(before, "Confirm revocation").disabled, true);
    const start = ui.calls.length; before.revoke(); const after = await ui.settle();
    assert.equal(ui.calls.length - start, 1); assert.equal(ui.calls.at(-1)!.url, "/api/auth/session");
    assert.match(after.task.error, /Confirm the exact captured identity and expiry/);
    assert.deepEqual(copy(after.selected), identity); assert.equal(after.owner, before.owner);
    assert.equal(ui.notifications, 0);
  }
});

test("pending exact captured revoke sends once without body, freezes controls, then refreshes metadata", async () => {
  const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
  let release!: (response: Response) => void;
  ui.respond(async (url, init) => url === "/api/auth/session" ? json(admin)
    : init?.method === "DELETE" ? new Promise(resolve => { release = resolve; })
    : json({ items: [identity], nextCursor: null }));
  assert.equal(button(before, "Confirm revocation").disabled, false);
  button(before, "Confirm revocation").onClick(); button(before, "Confirm revocation").onClick();
  for (let i = 0; i < 20 && !release; i++) await new Promise(resolve => setImmediate(resolve));
  assert(release); const pending = ui.render();
  assert.equal(pending.task.busy, true); assert.equal(pending.view.props.disabled, true);
  assert.equal(button(pending, "Confirm revocation").disabled, true);
  assert.equal(button(pending, "Cancel revocation").disabled, true);
  assert.deepEqual(copy(pending.selected), identity);
  assert.equal(ui.calls.length - start, 2);
  assert.equal(ui.calls.at(-1)!.method, "DELETE"); assert.equal(ui.calls.at(-1)!.body, undefined);
  release(json({ revoked: true })); const after = await ui.settle();
  assert.equal(after.task.busy, false); assert.equal(after.selected, null); assert.equal(after.confirm, "");
  assert.match(after.result, /is revoked/); assert.equal(ui.notifications, 1);
  assert.equal(ui.calls.filter(call => call.method === "DELETE").length, 1);
  assert.equal(after.owner, before.owner); assert.deepEqual(copy(after.scopes), copy(before.scopes));
});

for (const status of [409, 503]) test(`ordinary identity ${status} retains draft/selection and sends no retry`, async () => {
  const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : json({ error: "synthetic-refusal" }, status));
  before.revoke(); const after = await ui.settle();
  assert.equal(after.task.busy, false); assert(after.task.error);
  assert.deepEqual(copy(after.selected), identity); assert.equal(after.owner, before.owner);
  assert.equal(after.name, before.name); assert.equal(after.expiry, before.expiry);
  assert.deepEqual(copy(after.scopes), copy(before.scopes));
  assert.equal(after.credential, null); assert.equal(after.issuedId, "");
  assert.equal(after.issueAck, false); assert.equal(after.confirm, "");
  assert.equal(ui.calls.length - start, 2); assert.equal(ui.notifications, 0);
});

test("cancel captured revocation preserves the issue draft without a request", async () => {
  const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
  button(before, "Cancel revocation").onClick(); const after = ui.render();
  assert.equal(after.selected, null); assert.equal(after.confirm, "");
  assert.equal(after.owner, before.owner); assert.deepEqual(copy(after.scopes), copy(before.scopes));
  assert.equal(ui.calls.length, start); assert.equal(ui.notifications, 0);
});

test("existing page-hide generation fence rejects a delayed identity revoke result", async () => {
  const ui = harness(); const before = await ui.ready(); let release!: (response: Response) => void;
  ui.respond(async url => url === "/api/auth/session" ? json(admin)
    : new Promise<Response>(resolve => { release = resolve; }));
  before.revoke();
  for (let i = 0; i < 20 && !release; i++) await new Promise(resolve => setImmediate(resolve));
  assert(release); ui.event("pagehide");
  try {
    reset(ui.render());
  } finally {
    release(json({ revoked: true }));
    await ui.settle();
  }
  const after = ui.render(); reset(after);
  assert.equal(after.task.error, ""); assert.equal(ui.notifications, 0);
  assert.equal(ui.calls.filter(call => call.method === "DELETE").length, 1);
});
