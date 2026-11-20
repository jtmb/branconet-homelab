import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as model from "../src/components/secrets/kv-administration-model";

// Evaluate the production hooks and policy state transitions, without React DOM,
// a browser, server, native backend or database. Only the final JSX return is
// replaced with a state/handler receiver; all request and settlement code runs.
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ["useTask", "usePage", "Policies"];
const selected = parsed.statements.filter(statement =>
  ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
assert.equal(selected.length, names.length);
const receiver = ts.createSourceFile("receiver.ts", `function receive() {
  return { editing, mode, fields, impact, aliasAck, configAck, confirm, result,
    list, task, select, update, preview, commit, setAliasAck, setConfigAck, setConfirm };
}`, ts.ScriptTarget.Latest, true);
const returnState = (receiver.statements[0] as ts.FunctionDeclaration).body!.statements[0];
const printer = ts.createPrinter();
const declarations = selected.map(statement => {
  const fn = statement as ts.FunctionDeclaration;
  if (fn.name!.text !== "Policies") return fn.getText(parsed);
  assert(ts.isReturnStatement(fn.body!.statements.at(-1)!));
  return printer.printNode(ts.EmitHint.Unspecified, ts.factory.updateFunctionDeclaration(
    fn, fn.modifiers, fn.asteriskToken, fn.name, fn.typeParameters, fn.parameters, fn.type,
    ts.factory.updateBlock(fn.body!, [...fn.body!.statements.slice(0, -1), returnState]),
  ), parsed);
});
const output = ts.transpileModule(declarations.join("\n") + "\nmodule.exports = Policies;", {
  fileName: filename,
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

type Task = { busy: boolean; error: string };
type State = {
  editing: model.Policy | null; mode: string; fields: model.PolicyFields;
  impact: model.ImpactSnapshot | null; aliasAck: boolean; configAck: boolean;
  confirm: string; result: string; task: Task;
  list: { task: Task; page: model.Page<model.Policy> | null; refresh: () => void };
  select: (policy: model.Policy, action: "update" | "delete") => void;
  preview: () => void; commit: () => void;
  setAliasAck: (value: boolean) => void; setConfigAck: (value: boolean) => void;
  setConfirm: (value: string) => void;
};
const admin = { authenticated: true, username: "synthetic-admin", role: "write", engineAdmin: true };
const policy: model.Policy = {
  id: "synthetic-policy", revision: 7, principal: "legacy-lookup", mountId: "synthetic-mount",
  prefix: "synthetic/path", effect: "deny", actions: ["list", "read"],
};
const impact: model.ImpactPage = {
  required: true, fingerprint: "synthetic-fingerprint", affectedAliasCount: 1,
  nonsecretConfigurationAffected: true, nextCursor: null,
  items: [{ alias: "synthetic-alias", namespace: "synthetic-namespace", name: "synthetic-name",
    key: "synthetic-key", pathId: "synthetic-path", path: "synthetic/path", pathRevision: 3,
    mountRevision: 2, beforeAllowed: true, afterAllowed: false, basis: "synthetic" }],
};
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

function harness() {
  const slots: unknown[] = [], pending: (() => void)[] = [];
  const listeners = new Map<string, Set<() => void>>();
  let cursor = 0, dirty = false;
  let state: State;
  let handler: (url: string, init?: RequestInit) => Promise<Response> = async url =>
    json(url === "/api/auth/session" ? admin : url.endsWith("/preview") ? impact : { items: [policy], nextCursor: null });
  const calls: { url: string; method: string; body?: string }[] = [];
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
  const changed = (old: unknown[] | undefined, next: unknown[]) =>
    !old || old.length !== next.length || next.some((value, index) => !Object.is(value, old[index]));
  const useCallback = (callback: unknown, deps: unknown[]) => {
    const index = cursor++, old = slots[index] as { deps: unknown[]; callback: unknown } | undefined;
    if (changed(old?.deps, deps)) slots[index] = { deps, callback };
    return (slots[index] as { callback: unknown }).callback;
  };
  const useEffect = (effect: () => void, deps: unknown[]) => {
    const index = cursor++, old = slots[index] as { deps: unknown[] } | undefined;
    if (changed(old?.deps, deps)) { slots[index] = { deps }; pending.push(effect); }
  };
  const events = {
    addEventListener: (name: string, callback: () => void) => {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name)!.add(callback);
    },
    removeEventListener: (name: string, callback: () => void) => listeners.get(name)?.delete(callback),
  };
  const component = { exports: undefined as unknown as (props: { changed: () => void }) => State };
  let notifications = 0;
  runInNewContext(output, { ...model, module: component, exports: {}, useState, useRef, useCallback, useEffect,
    fetch: async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET", body: init?.body as string | undefined });
      return handler(url, init);
    },
    Error, Button: "Button", window: events, document: { ...events, visibilityState: "visible" },
    require: (name: string) => {
      assert.equal(name, "react/jsx-runtime");
      return { jsx: () => null, jsxs: () => null };
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
  render();
  return { render, settle, calls, get notifications() { return notifications; },
    respond: (next: typeof handler) => { handler = next; },
    event: (name: string) => { for (const listener of listeners.get(name) ?? []) listener(); },
    ready: async () => {
      await settle(); state.select(policy, "update"); render(); state.preview();
      await settle(); state.setAliasAck(true); state.setConfigAck(true);
      state.setConfirm(model.policyConfirmation(policy)); return render();
    },
  };
}

function reset(state: State) {
  assert.equal(state.editing, null);
  assert.equal(state.mode, "create");
  assert.deepEqual(copy(state.fields), { principal: "", mountId: null, prefix: "", effect: "allow", actions: ["list"] });
  assert.equal(state.impact, null);
  assert.equal(state.aliasAck, false);
  assert.equal(state.configAck, false);
  assert.equal(state.confirm, "");
  assert.equal(state.result, "");
}

for (const status of [401, 403]) {
  for (const stage of ["preflight", "operation", "postflight"]) {
    test(`actual policy hooks clear captured state on ${status} at ${stage}`, async () => {
      const ui = harness(); const before = await ui.ready();
      assert(before.impact?.complete && before.aliasAck && before.configAck && before.confirm);
      const start = ui.calls.length; let sessions = 0;
      ui.respond(async url => {
        if (url === "/api/auth/session") {
          sessions++;
          if (stage === "preflight" || (stage === "postflight" && sessions === 2)) return new Response("malformed", { status });
          return json(admin);
        }
        return stage === "operation" ? new Response("malformed", { status }) : json(impact);
      });
      before.preview(); const after = await ui.settle(); reset(after);
      assert.match(after.task.error, /Fresh authorization denied/);
      assert.equal(ui.calls.length - start, stage === "preflight" ? 1 : stage === "operation" ? 2 : 3);
      assert.equal(ui.notifications, 0);
    });
  }
  test(`actual policy commit clears draft on ${status} without retry or callback`, async () => {
    const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(null, { status }));
    before.commit(); const after = await ui.settle(); reset(after);
    assert.match(after.task.error, /Fresh authorization denied/);
    assert.equal(ui.calls.length - start, 2);
    const sent = JSON.parse(ui.calls.at(-1)!.body!);
    assert.equal(sent.revision, policy.revision);
    assert.deepEqual(sent.legacyImpact.aliases, ["synthetic-alias"]);
    assert.equal(sent.legacyImpact.confirmConfigurationImpact, true);
    assert.equal(ui.notifications, 0);
  });
  test(`policy-list ${status} clears both draft and prior success display`, async () => {
    const ui = harness(); let before = await ui.ready();
    ui.respond(async url => json(url === "/api/auth/session" ? admin : url.endsWith("/preview") ? impact
      : url === "/api/kv/policies" ? { items: [policy], nextCursor: null } : policy));
    before.commit(); before = await ui.settle(); assert.match(before.result, /committed/);
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response("malformed", { status }));
    before.list.refresh(); let after = await ui.settle(); reset(after);
    assert.equal(after.list.page, null); assert.match(after.list.task.error, /Fresh authorization denied/);
    // Also retain a captured edit at the moment the independent list task denies.
    after.select(policy, "delete"); after = ui.render(); after.list.refresh();
    after = await ui.settle(); reset(after);
  });
  test(`policy ${status} discards state without awaiting stalled denial cancellation`, async () => {
    const ui = harness(); const before = await ui.ready(); let cancellations = 0;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(new ReadableStream({
      cancel() { cancellations++; return new Promise(() => {}); },
    }), { status }));
    before.preview(); const after = await ui.settle(); reset(after);
    assert.equal(cancellations, 1); assert.match(after.task.error, /Fresh authorization denied/);
  });
}

test("fresh session authority loss resets policies before and after work", async () => {
  for (const postflight of [false, true]) {
    const ui = harness(); const before = await ui.ready(); let sessions = 0;
    ui.respond(async url => {
      if (url !== "/api/auth/session") return json(impact);
      sessions++;
      return json(postflight && sessions === 1 ? admin : { ...admin, engineAdmin: false });
    });
    before.preview(); reset(await ui.settle());
  }
});

test("policy 409 preserves the draft and selection, invalidates acknowledgments and sends once", async () => {
  const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : json({ error: "synthetic-conflict" }, 409));
  before.commit(); const after = await ui.settle();
  assert.deepEqual(copy(after.fields), copy(before.fields));
  assert.deepEqual(copy(after.editing), policy); assert.equal(after.mode, "update");
  assert.equal(after.impact, null); assert.equal(after.aliasAck, false);
  assert.equal(after.configAck, false); assert.equal(after.confirm, "");
  assert.match(after.task.error, /stale.*Refresh and confirm again; no retry/);
  assert.equal(ui.calls.length - start, 2); assert.equal(ui.notifications, 0);
});

test("existing page-hide generation fence rejects a delayed policy reply", async () => {
  const ui = harness(); const before = await ui.ready();
  let release!: (response: Response) => void;
  ui.respond(async url => url === "/api/auth/session" ? json(admin)
    : new Promise<Response>(resolve => { release = resolve; }));
  before.preview();
  for (let i = 0; i < 20 && !release; i++) await new Promise(resolve => setImmediate(resolve));
  assert(release); ui.event("pagehide"); reset(ui.render());
  release(json(impact)); const after = await ui.settle(); reset(after);
  assert.equal(after.task.error, ""); assert.equal(ui.notifications, 0);
});
