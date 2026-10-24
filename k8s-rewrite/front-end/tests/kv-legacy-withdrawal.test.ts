import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as model from "../src/components/secrets/kv-administration-model";

// Production hooks/handlers/JSX with a scoped state/element receiver. Fetch is
// synthetic legacy/session metadata only; no handler, server, DB or credential.
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ["useTask", "usePage", "Legacy"];
const selected = parsed.statements.filter(statement =>
  ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
assert.equal(selected.length, names.length);
const printer = ts.createPrinter();
const declarations = selected.map(statement => {
  const fn = statement as ts.FunctionDeclaration;
  if (fn.name!.text !== "Legacy") return fn.getText(parsed);
  const returned = fn.body!.statements.at(-1)!;
  assert(ts.isReturnStatement(returned) && returned.expression);
  const receiver = ts.createSourceFile("receiver.ts", `function receive() {
    return { principal, alias, change, impact, aliasAck, configAck, confirm, expected, result,
      list, task, load, preview, grant, commit, setAlias, setAliasAck, setConfigAck, setConfirm, view: null };
  }`, ts.ScriptTarget.Latest, true);
  const state = ((receiver.statements[0] as ts.FunctionDeclaration).body!.statements[0] as ts.ReturnStatement)
    .expression as ts.ObjectLiteralExpression;
  const result = ts.factory.updateObjectLiteralExpression(state, [
    ...state.properties.slice(0, -1), ts.factory.createPropertyAssignment("view", returned.expression),
  ]);
  return printer.printNode(ts.EmitHint.Unspecified, ts.factory.updateFunctionDeclaration(
    fn, fn.modifiers, fn.asteriskToken, fn.name, fn.typeParameters, fn.parameters, fn.type,
    ts.factory.updateBlock(fn.body!, [...fn.body!.statements.slice(0, -1), ts.factory.createReturnStatement(result)]),
  ), parsed);
});
const output = ts.transpileModule(declarations.join("\n") + "\nmodule.exports = Legacy;", {
  fileName: filename,
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

type Element = { type: string; props: Record<string, unknown> & { children?: unknown } };
type Task = { busy: boolean; error: string };
type State = {
  principal: model.LegacyPrincipal | null; alias: string; change: Record<string, unknown> | null;
  impact: model.ImpactSnapshot | null; aliasAck: boolean; configAck: boolean;
  confirm: string; expected: string; result: string; task: Task; view: Element;
  list: { task: Task; page: model.Page<model.Grant> | null; controls: Element; refresh: () => void };
  load: () => void; preview: (input: Record<string, unknown>, confirmation: string, cursor?: string) => void;
  grant: () => void; commit: () => void; setAlias: (value: string) => void;
  setAliasAck: (value: boolean) => void; setConfigAck: (value: boolean) => void;
  setConfirm: (value: string) => void;
};
const pathId = "00000000-0000-4000-8000-000000000001";
const admin = { authenticated: true, username: "synthetic-admin", role: "write", engineAdmin: true };
const principal: model.LegacyPrincipal = { id: "legacy-lookup", revision: 7, enabled: true, grantCount: 101 };
const grant: model.Grant = { id: "synthetic-grant", pathId, alias: "synthetic-alias",
  namespace: "synthetic-namespace", name: "synthetic-name", key: "synthetic-key" };
const change = { kind: "principal", enabled: false, revision: principal.revision };
const expected = "legacy-lookup revision=7 enabled=false";
const impactRow = (alias: string): model.ImpactRow => ({ alias, namespace: grant.namespace,
  name: grant.name, key: grant.key, pathId, path: "synthetic/path", pathRevision: 3,
  mountRevision: 2, beforeAllowed: true, afterAllowed: false, basis: "synthetic" });
const impact: model.ImpactPage = { required: true, fingerprint: "synthetic-fingerprint", revision: 7,
  affectedAliasCount: 1, nonsecretConfigurationAffected: true, nextCursor: null, items: [impactRow(grant.alias)] };
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
    url === "/api/auth/session" ? admin : url === "/api/kv/legacy" ? principal :
      url === "/api/kv/legacy/preview" ? impact : url.startsWith("/api/kv/legacy/grants") ?
        { items: [grant], nextCursor: "synthetic/cursor+one" } :
        { id: pathId, revision: 3, namespace: grant.namespace, name: grant.name, method: init?.method });
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
  const component = { exports: undefined as unknown as (props: { pathId: string; changed: () => void }) => State };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { ...model, module: component, exports: {}, useState, useRef, useCallback, useEffect,
    fetch: async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      assert((url === "/api/auth/session" && method === "GET") ||
        (url === "/api/kv/legacy" && ["GET", "PATCH"].includes(method)) ||
        (url === "/api/kv/legacy/preview" && method === "POST") ||
        (url.startsWith("/api/kv/legacy/grants") && ["GET", "POST", "DELETE"].includes(method)) ||
        (url === `/api/kv/paths/${pathId}` && method === "GET"), "Unexpected synthetic request");
      calls.push({ url, method, body: init?.body as string | undefined, cache: init?.cache });
      return handler(url, init);
    },
    Error, queueMicrotask, route: (id: string) => `/api/kv/paths/${id}`,
    Button: "Button", Table: "Table", TaskState: "TaskState", Field: "Field", Impact: "Impact", Exact: "Exact",
    inputClass: "", boxClass: "", window: events, document: { ...events, visibilityState: "visible" },
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
  });
  const render = () => {
    let passes = 0;
    do {
      assert(++passes < 30, "Synthetic render did not converge"); dirty = false; cursor = 0;
      state = component.exports({ pathId, changed: () => { notifications++; } });
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
      await settle(); state.setAlias(grant.alias); render(); state.preview(change, expected);
      await settle(); state.setAliasAck(true); state.setConfigAck(true); state.setConfirm(expected); return render();
    },
  };
}
function reset(state: State) {
  assert.equal(state.principal, null); assert.equal(state.alias, ""); assert.equal(state.change, null);
  assert.equal(state.impact, null); assert.equal(state.aliasAck, false); assert.equal(state.configAck, false);
  assert.equal(state.confirm, ""); assert.equal(state.expected, ""); assert.equal(state.result, "");
}

for (const status of [401, 403]) {
  for (const channel of ["operation", "list"]) {
    for (const stage of ["preflight", "request", "postflight"]) {
      test(`actual legacy ${channel} task clears captured state on malformed ${status} at ${stage}`, async () => {
        const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
        assert(before.principal && before.impact?.complete && before.aliasAck && before.configAck && before.confirm);
        let sessions = 0;
        ui.respond(async (url, init) => {
          if (url === "/api/auth/session") {
            sessions++;
            if (stage === "preflight" || (stage === "postflight" && sessions === 2))
              return new Response("malformed", { status });
            return json(admin);
          }
          return stage === "request" ? new Response("malformed", { status }) : ui.standard(url, init);
        });
        if (channel === "operation") before.preview(change, expected); else before.list.refresh();
        const after = await ui.settle(); reset(after);
        assert.match((channel === "operation" ? after.task : after.list.task).error, /Fresh authorization denied/);
        assert.equal(ui.calls.length - start, stage === "preflight" ? 1 : stage === "request" ? 2 : 3);
        assert.equal(ui.notifications, 0);
      });
    }
  }
  test(`actual legacy commit clears capture on ${status} with one captured request and no retry`, async () => {
    const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(null, { status }));
    before.commit(); const after = await ui.settle(); reset(after);
    assert.equal(ui.calls.length - start, 2); assert.equal(ui.notifications, 0);
    const sent = ui.calls.at(-1)!;
    assert.equal(sent.url, "/api/kv/legacy"); assert.equal(sent.method, "PATCH");
    assert.deepEqual(JSON.parse(sent.body!), { enabled: false, revision: 7,
      legacyImpact: { fingerprint: impact.fingerprint, aliases: [grant.alias],
        confirmLegacyImpact: true, confirmConfigurationImpact: true } });
  });
}
for (const channel of ["operation", "list"]) {
  test(`actual legacy ${channel} authorization withdrawal does not wait for a stalled denial body`, async () => {
    const ui = harness(); const before = await ui.ready(); let cancelled = false;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(new ReadableStream({
      pull: () => new Promise(() => {}), cancel: () => { cancelled = true; return new Promise(() => {}); },
    }), { status: 403 }));
    if (channel === "operation") before.preview(change, expected); else before.list.refresh();
    reset(await ui.settle()); assert.equal(cancelled, true);
  });
}
for (const status of [409, 503]) {
  test(`actual legacy ${status} retains draft/captured target but invalidates preview and confirmation`, async () => {
    const ui = harness(); const before = await ui.ready(); const start = ui.calls.length;
    ui.respond(async url => json(url === "/api/auth/session" ? admin : {}, url === "/api/auth/session" ? 200 : status));
    before.commit(); const after = await ui.settle();
    assert.deepEqual(copy(after.principal), principal); assert.equal(after.alias, grant.alias);
    assert.deepEqual(copy(after.change), change); assert.equal(after.expected, expected);
    assert.equal(after.impact, null); assert.equal(after.aliasAck, false); assert.equal(after.configAck, false);
    assert.equal(after.confirm, ""); assert.equal(ui.calls.length - start, 2); assert.equal(ui.notifications, 0);
  });
}
for (const event of ["pagehide", "bortus-session-ended"]) {
  test(`actual legacy ${event} clears state and fences a held late preview`, async () => {
    const ui = harness(); const before = await ui.ready(); let release: ((value: Response) => void) | undefined;
    ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Promise(resolve => { release = resolve; }));
    before.preview(change, expected); await new Promise(resolve => setImmediate(resolve));
    assert(release); reset(ui.event(event)); release(json(impact)); reset(await ui.settle());
    assert.equal(ui.notifications, 0);
  });
}
test("actual legacy success display clears on independent grant-list denial", async () => {
  const ui = harness(); const before = await ui.ready(); before.commit(); const done = await ui.settle();
  assert.match(done.result, /exact legacy authorization change committed/); assert.equal(ui.notifications, 1);
  done.setAlias("another synthetic alias"); ui.render();
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(null, { status: 403 }));
  done.list.refresh(); reset(await ui.settle()); assert.equal(ui.notifications, 1);
});
test("actual legacy grant pages preserve empty-page next cursor and reset history after denial", async () => {
  const ui = harness(); await ui.ready();
  ui.respond(async url => json(url === "/api/auth/session" ? admin : { items: [], nextCursor: "synthetic/next+two" }));
  let state = ui.render(); button(state.list.controls, "Next page").onClick(); state = await ui.settle();
  assert.equal(state.list.page?.items.length, 0); assert.equal(button(state.list.controls, "Next page").disabled, false);
  assert.equal(button(state.list.controls, "Previous page").disabled, false);
  assert.equal(ui.calls.filter(call => call.url.includes("?cursor=")).at(-1)?.url,
    "/api/kv/legacy/grants?cursor=synthetic%2Fcursor%2Bone");
  ui.respond(async url => url === "/api/auth/session" ? json(admin) : new Response(null, { status: 401 }));
  state.list.refresh(); state = await ui.settle(); reset(state); assert.equal(state.list.page, null);
  assert.equal(button(state.list.controls, "Previous page").disabled, true);
});
test("actual legacy complete 101-alias capture gates commit and preserves every exact alias/config acknowledgment", async () => {
  const ui = harness(); await ui.settle();
  const rows = Array.from({ length: 101 }, (_, i) => impactRow(`synthetic-alias-${i}`));
  ui.respond(async (url, init) => url === "/api/kv/legacy/preview" ? json({ ...impact,
    affectedAliasCount: 101, items: JSON.parse(init!.body as string).cursor ? rows.slice(100) : rows.slice(0, 100),
    nextCursor: JSON.parse(init!.body as string).cursor ? null : "synthetic-impact-cursor" }) : ui.standard(url, init));
  let state = ui.render(); state.preview(change, expected); state = await ui.settle();
  state.setAliasAck(true); state.setConfigAck(true); state.setConfirm(expected); state = ui.render();
  assert.equal(button(state.view, "Commit captured legacy change").disabled, true);
  const next = children(state.view).find(node => node.type === "Impact")!.props.next as () => void;
  next(); state = await ui.settle(); assert.equal(state.impact?.complete, true);
  assert.equal(state.impact?.aliases.length, 101); assert.equal(state.impact?.page.items.length, 1);
  state.setConfigAck(false); state = ui.render(); assert.equal(button(state.view, "Commit captured legacy change").disabled, true);
  state.setConfigAck(true); state = ui.render(); assert.equal(button(state.view, "Commit captured legacy change").disabled, false);
  state.commit(); await ui.settle();
  const sent = JSON.parse(ui.calls.find(call => call.method === "PATCH")!.body!);
  assert.deepEqual(sent.legacyImpact.aliases, rows.map(row => row.alias));
  assert.equal(sent.legacyImpact.confirmConfigurationImpact, true); assert.equal(ui.notifications, 1);
  assert(ui.calls.every(call => call.cache === "no-store"));
});
test("actual legacy repeated impact cursor is rejected without commit or automatic retry", async () => {
  const ui = harness(); await ui.settle();
  let page = 0;
  ui.respond(async (url, init) => url === "/api/kv/legacy/preview" ? json({ ...impact,
    affectedAliasCount: 3, items: [impactRow(`synthetic-${++page}`)], nextCursor: "synthetic-repeat" }) : ui.standard(url, init));
  let state = ui.render(); state.preview(change, expected); state = await ui.settle();
  state.preview(change, expected, state.impact!.page.nextCursor!); state = await ui.settle();
  assert.equal(state.impact, null); assert.match(state.task.error, /Impact paging changed/);
  assert.equal(ui.calls.filter(call => call.method === "PATCH").length, 0); assert.equal(page, 2);
});
